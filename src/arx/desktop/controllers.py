from pathlib import Path

from arx import __version__
from arx.cli import envelope, preflight_envelope
from arx.core.engine import capabilities, compare
from arx.core.evidence import redact
from arx.core.models import serialize
from arx.exporters import (
    codex_report,
    project_codex_report,
    render_json,
    render_summary,
)
from arx.machine import scan_machine
from arx.project import project_preflight
from arx.software import scan_software


def project_readiness_view_model(report):
    """Project-readiness projection that consumes, but never recomputes, semantics."""
    providers={item.id:item for item in report.providers}
    primary=report.evaluation if report.project.primary_python_requirement else None
    def provider(identifier):
        item=providers.get(identifier or "")
        if item is None:return None
        return {"id":item.id,"version":item.version,"path":item.path,"health_status":item.health_status.value,"architecture":item.architecture,"scope":item.scope.value}
    return {
        "decision":report.severity.severity.value.upper(),
        "satisfaction":primary.satisfaction.value.upper() if primary else "UNKNOWN",
        "current_context_satisfaction":report.severity.current_context_satisfaction.value.upper(),
        "recoverability":report.severity.recoverability.value.upper(),
        "blocker_ids":list(report.severity.blocker_ids),
        "warning_ids":list(report.severity.warning_ids),
        "resolved":provider(report.provider_roles.resolved_provider_id),
        "resolved_path":report.resolution.resolved_path,
        "compatible":[provider(item) for item in report.provider_roles.compatible_provider_ids],
        "preferred":provider(report.provider_roles.preferred_provider_id),
        "pinned":[provider(item) for item in report.provider_roles.pinned_provider_ids],
        "pinned_constraints":list(report.provider_roles.pinned_constraints),
        "plan_step_ids":[item.id for item in report.plan.steps],
        "plan_provider_ids":[item.provider_id for item in report.plan.steps if item.provider_id],
    }


def intelligence_context_components(controller) -> dict[str, object]:
    """Bounded local projections for the advisory context builder.

    This function consumes canonical controller state. It does not recompute a
    compatibility/readiness decision and it does not expose a response write path.
    """

    machine = controller.machine or {}
    tool_projection: dict[str, object] = {}
    for name, record in tuple(machine.get("tools", {}).items())[:24]:
        tool_projection[str(name)] = {
            "detected": bool(record.detected),
            "version": record.version,
            "path": record.path,
            "probe_method": record.probe_method,
        }
    runtime_projection = [
        {
            key: item.get(key)
            for key in ("version", "path", "healthy", "health_reason", "architecture", "kind")
            if key in item
        }
        for item in tuple(machine.get("python_installations", ()))[:12]
    ]
    capability_projection = {
        str(name): {
            "status": item.status.value,
            "reason": item.reason,
            "dependencies": list(item.dependencies),
        }
        for name, item in tuple(controller.capabilities.items())[:24]
    }
    machine_projection: dict[str, object] = {}
    if machine:
        machine_projection = {
            "os": serialize(machine.get("os", {})),
            "tools": tool_projection,
            "python_installations": runtime_projection,
            "capabilities": capability_projection,
        }

    software = controller.software or {}
    software_projection = {
        key: serialize(software.get(key))
        for key in (
            "filename",
            "absolute_path",
            "detected_file_type",
            "application",
            "pe",
            "archive",
            "requirements",
            "signature",
        )
        if software.get(key) is not None
    }

    project_projection: dict[str, object] = {}
    conclusions: dict[str, object] = {}
    contradictions: list[dict[str, object]] = []
    unknowns: list[str] = []
    evidence: list[dict[str, object]] = []

    for item in tuple(machine.get("evidence", ()))[:16]:
        evidence.append(serialize(item))
    for record in tuple(machine.get("tools", {}).values())[:24]:
        for item in tuple(record.evidence)[:2]:
            evidence.append(serialize(item))
    for item in tuple(software.get("evidence", ()))[:16]:
        evidence.append(serialize(item))

    compatibility = controller.compatibility or {}
    if compatibility:
        conclusions["compatibility"] = {
            "value": compatibility.get("status"),
            "score": compatibility.get("score"),
            "confidence": compatibility.get("confidence"),
            "confidence_semantics": "Uncalibrated detector-author weight; not a probability.",
            "basis": list(compatibility.get("checks", ()))[:12],
            "validation": "Legacy compatibility composed-state rules; no separate fact-provenance upgrade.",
        }
        for check in compatibility.get("checks", ()):
            if str(check.get("status", "")).casefold() == "unknown":
                unknowns.append(str(check.get("reason") or check.get("name") or "Unknown compatibility condition"))

    for name, item in controller.capabilities.items():
        if item.status.value == "unknown":
            unknowns.append(f"{name}: {item.reason}")

    report = getattr(controller, "project_preflight", None)
    if report is not None:
        view = project_readiness_view_model(report)
        project_projection = {
            "identity": report.project.identity,
            "project_root": str(report.project.root),
            "languages": list(report.project.languages),
            "ecosystems": list(report.project.ecosystems),
            "build_systems": list(report.project.build_systems),
            "requirements": [serialize(item) for item in report.project.requirements[:12]],
        }
        conclusions["project_readiness"] = {
            "value": view["decision"],
            "satisfaction": view["satisfaction"],
            "current_context_satisfaction": view["current_context_satisfaction"],
            "recoverability": view["recoverability"],
            "blocker_ids": view["blocker_ids"],
            "warning_ids": view["warning_ids"],
            "basis": report.severity.reason,
            "validation": "project semantic invariants and composed project-preflight state",
        }
        contradictions.extend(serialize(item) for item in report.conflicts[:12])
        unknowns.extend(str(item) for item in report.project.unknowns)
        unknowns.extend(str(item) for item in report.project.requirement_graph.unknowns)
        for requirement in [*report.project.requirements, *report.project.optional_requirements]:
            unknowns.extend(str(item) for item in requirement.unknowns)
        for item in report.project.evidence:
            evidence.append(serialize(item))
        for item in report.resolution.evidence:
            evidence.append(serialize(item))

    deduplicated_unknowns = list(dict.fromkeys(item for item in unknowns if item))[:32]
    return {
        "machine": machine_projection,
        "software": software_projection,
        "project": project_projection,
        "conclusions": conclusions,
        "contradictions": contradictions,
        "unknowns": deduplicated_unknowns,
        "evidence": evidence[:32],
    }

class DesktopController:
    """UI-neutral orchestration; all scanner logic remains in the ARX engine."""
    def __init__(self):
        self.machine=None;self.software=None;self.compatibility=None;self.capabilities={};self.project_preflight=None

    def scan(self,deep=False):
        self.machine=scan_machine(deep);self.capabilities=capabilities(self.machine);self.compatibility=None;self.project_preflight=None
        return self.machine

    def inspect(self,target):
        self.software=scan_software(target);self.compatibility=None;return self.software

    def compare(self,target=None):
        if target:self.inspect(target)
        if self.machine is None:self.scan(True)
        if self.software is None:raise ValueError("Choose software before comparing it with this PC.")
        self.compatibility=compare(self.machine,self.software);return self.compatibility

    def preflight(self,target):
        if self.machine is None:self.scan(True)
        self.project_preflight=project_preflight(target,machine=self.machine);return self.project_preflight

    def report(self):
        return envelope(self.machine,self.software,self.compatibility)

    def codex(self):
        if self.project_preflight is not None:return project_codex_report(self.project_preflight,__version__)
        if self.machine is None:self.scan(True)
        return codex_report(self.machine,self.capabilities,__version__)

    def export(self,path,kind="json"):
        destination=Path(path);kind=kind.lower()
        if kind=="codex":content=render_json(self.codex())
        elif kind=="text":content=render_summary(self.report())+"\n"
        elif self.project_preflight is not None:content=render_json(preflight_envelope(self.project_preflight))
        else:content=render_json(redact(serialize(self.report())))
        destination.write_text(content,encoding="utf-8");return destination

def smoke_test(target,output):
    controller=DesktopController();controller.scan(True);controller.inspect(target);controller.compare();controller.export(output,"json")
    return {"machine":bool(controller.machine),"software_type":controller.software.get("detected_file_type"),"compatibility":controller.compatibility.get("status"),"java":controller.capabilities.get("java.jdk").status.value,"python_installations":len(controller.machine.get("python_installations",[])),"msbuild":controller.machine["tools"]["msbuild"].detected}

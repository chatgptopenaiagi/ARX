import json
from pathlib import Path

from arx import __version__
from arx.cli import envelope,preflight_envelope
from arx.core.engine import capabilities,compare
from arx.core.evidence import redact
from arx.core.models import serialize
from arx.exporters import codex_report,project_codex_report,render_json,render_summary
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

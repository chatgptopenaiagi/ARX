import argparse
import json
import sys
from pathlib import Path

from arx import __version__
from arx.core.engine import capabilities, compare
from arx.core.evidence import redact
from arx.core.models import serialize, utc_now
from arx.exporters import codex_report, project_codex_report
from arx.machine import scan_machine
from arx.project import inspect_project, project_preflight
from arx.software import scan_software


def envelope(machine=None, software=None, compatibility=None):
    return redact(
        serialize(
            {
                "schema_version": "0.1",
                "scanner": {"name": "ARX", "version": __version__},
                "machine": machine,
                "software": software,
                "compatibility": compatibility,
                "generated_at": utc_now(),
            }
        )
    )


def project_envelope(project):
    return redact(
        serialize(
            {
                "schema_version": "0.2",
                "producer": {"name": "ARX", "version": __version__},
                "generated_at": utc_now(),
                "project": project,
            }
        ),
        private_roots=[project.root],
    )


def preflight_envelope(report):
    return redact(
        serialize(
            {
                "schema_version": "0.2",
                "producer": {"name": "ARX", "version": __version__},
                "generated_at": report.generated_at,
                "project_preflight": report,
            }
        ),
        private_roots=[report.project.root],
    )


def parser():
    root = argparse.ArgumentParser(
        prog="arx", description="ARX project-aware compatibility intelligence"
    )
    root.add_argument("-o", "--output", type=Path)
    subcommands = root.add_subparsers(dest="command", required=True)
    for name in ("quick", "deep"):
        subcommands.add_parser(name)
    codex = subcommands.add_parser("codex")
    codex.add_argument("--project")
    for name in ("inspect", "compare"):
        command = subcommands.add_parser(name)
        command.add_argument("target")
    for name in ("project", "resolve", "preflight"):
        command = subcommands.add_parser(name)
        command.add_argument("path")
    return root


def quick(caps):
    labels = {
        "git": "Git",
        "python.available": "Python",
        "node.available": "Node.js",
        "java.jdk": "Java JDK",
        "android.sdk": "Android SDK",
        "android.native.build": "Android Native Build",
        "flutter.android.build": "Flutter Android",
        "dotnet.sdk": ".NET SDK",
        "windows_cpp_build": "Visual C++ Build",
        "cuda_compute": "CUDA Compute",
    }
    return "ARX - Quick Scan\n\n" + "\n".join(
        f"[{caps[key].status.value.upper():<9}] {label:<24} {caps[key].reason}"
        for key, label in labels.items()
    )


def inspect_text(software, compat=None):
    pe = software.get("pe", {})
    signature = software.get("signature", {})
    lines = [
        "ARX",
        f"Target: {software['filename']}",
        f"SHA256: {software.get('sha256', 'n/a')}",
        f"Type: {software['detected_file_type']}",
        f"Architecture: {pe.get('architecture', 'unknown')}",
        f"Signature: {signature.get('Status', signature.get('status', 'not inspected'))}",
    ]
    if pe:
        lines += [
            f"Subsystem: {pe.get('subsystem')}",
            f".NET indicator: {pe.get('is_dotnet')}",
            f"Requested level: {pe.get('requested_execution_level') or 'not detected'}",
            "Imported libraries: " + (", ".join(pe.get("imports", [])[:20]) or "none detected"),
        ]
    if compat:
        lines += [f"Machine compatibility: {compat['status'].upper()}"]
        if compat["blockers"]:
            lines.append("Blockers: " + "; ".join(compat["blockers"]))
        if compat["warnings"]:
            lines.append("Warnings: " + "; ".join(compat["warnings"]))
    return "\n".join(lines)


def project_text(project):
    primary = project.primary_python_requirement
    return "\n".join(
        [
            "ARX - PROJECT DNA",
            "",
            f"Project: {project.identity}",
            f"Root: {project.root}",
            f"Languages: {', '.join(project.languages) or 'unknown'}",
            f"Ecosystems: {', '.join(project.ecosystems) or 'unknown'}",
            f"Python requirement: {primary.constraint if primary and primary.constraint else 'UNKNOWN'}",
            "Manifests: " + (", ".join(item.path for item in project.manifests) or "none"),
            f"Confidence: {project.confidence:.2f}",
            "Unknowns: " + ("; ".join(project.unknowns) or "none"),
        ]
    )


def preflight_text(report, *, resolution_only=False):
    provider_by_id = {item.id: item for item in report.providers}
    primary = report.project.primary_python_requirement
    evaluation = None
    if primary:
        evaluation = next(
            (item for item in report.evaluations if item.requirement_id == primary.id), None
        )
    resolved = provider_by_id.get(report.resolution.resolved_provider_id or "")
    compatible = (
        [provider_by_id[item] for item in evaluation.compatible_provider_ids]
        if evaluation
        else []
    )
    preferred = (
        provider_by_id.get(evaluation.preferred_provider_id or "") if evaluation else None
    )
    lines = [
        "ARX - PYTHON RESOLUTION" if resolution_only else "ARX - PROJECT PREFLIGHT",
        "",
        f"PROJECT READINESS: {report.severity.severity.value.upper()}",
        f"Project: {report.project.identity}",
        f"Requirement: {primary.constraint if primary and primary.constraint else 'UNKNOWN'}",
        f"Resolved: {resolved.version if resolved else 'UNRESOLVED'}"
        + (f" ({resolved.path})" if resolved else ""),
        "Compatible: "
        + (", ".join(f"{item.version} ({item.path})" for item in compatible) or "none"),
        "Preferred: "
        + (f"{preferred.version} ({preferred.path})" if preferred else "none"),
        f"Relevance: {evaluation.relevance.value.upper() if evaluation else 'UNKNOWN_RELEVANCE'}",
        f"Satisfaction: {evaluation.satisfaction.value.upper() if evaluation else 'UNKNOWN'}",
        "",
        "What is wrong?",
    ]
    issues = [
        *(f"BLOCKER {item}" for item in report.severity.blocker_ids),
        *(f"WARNING {item}" for item in report.severity.warning_ids),
    ]
    lines.extend(issues or ["Nothing blocking was found."])
    lines += ["", "Why?", report.severity.reason, "", "Shortest trusted path to GREEN:"]
    lines.extend(
        (f"{index}. {step.action}" for index, step in enumerate(report.plan.steps, 1))
        if report.plan.steps
        else ["0 actions — current evaluated state is GREEN."]
    )
    return "\n".join(lines)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "quick":
            machine = scan_machine(False)
            caps = capabilities(machine)
            data = envelope(machine=machine)
            text = quick(caps)
        elif args.command == "deep":
            data = envelope(machine=scan_machine(True))
            text = json.dumps(data, indent=2)
        elif args.command == "codex" and not args.project:
            machine = scan_machine(True)
            caps = capabilities(machine)
            data = codex_report(machine, caps, __version__)
            text = json.dumps(data, indent=2)
        elif args.command == "codex":
            report = project_preflight(args.project)
            data = project_codex_report(report, __version__)
            text = json.dumps(data, indent=2)
        elif args.command == "inspect":
            software = scan_software(args.target)
            data = envelope(software=software)
            text = inspect_text(software)
        elif args.command == "compare":
            machine = scan_machine(True)
            software = scan_software(args.target)
            compat = compare(machine, software)
            data = envelope(machine, software, compat)
            text = inspect_text(software, compat)
        elif args.command == "project":
            project = inspect_project(args.path)
            data = project_envelope(project)
            text = project_text(project)
        else:
            report = project_preflight(args.path)
            data = preflight_envelope(report)
            text = preflight_text(report, resolution_only=args.command == "resolve")
        if args.output:
            args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"Report written to {args.output}", file=sys.stderr)
        print(text)
        return 0
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        print(f"arx: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130

import argparse
import json
import sys
from pathlib import Path

from arx import PRODUCT_NAME, __version__
from arx.agent.importer import (
    AgentDNAImportError,
    import_experimental_baseline,
    load_experimental_baseline,
    normalized_dict,
)
from arx.agent.summary import summary_text as agent_summary_text
from arx.agent.challenges import (
    PROFILES,
    catalog_summary,
    load_challenge,
    load_receipt,
    prepare_challenge,
    validation_from_dict,
    validation_summary,
)
from arx.agent.protocol import validate_receipt
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
        prog="arx", description=f"{PRODUCT_NAME} project-aware compatibility intelligence"
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
    agent = subcommands.add_parser("agent", help="validate and normalize Agent DNA evidence")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    for name in ("validate", "import", "summary"):
        command = agent_commands.add_parser(name)
        command.add_argument("baseline", type=Path)
    challenge = agent_commands.add_parser("challenge", help="prepare and validate bounded capability challenges")
    challenge_commands = challenge.add_subparsers(dest="challenge_command", required=True)
    challenge_commands.add_parser("catalog")
    prepare = challenge_commands.add_parser("prepare")
    prepare.add_argument("challenge_or_profile")
    validate = challenge_commands.add_parser("validate")
    validate.add_argument("challenge", type=Path)
    validate.add_argument("receipt", type=Path)
    summarize = challenge_commands.add_parser("summarize")
    summarize.add_argument("validation", type=Path)
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
    return f"{PRODUCT_NAME} - Quick Scan\n\n" + "\n".join(
        f"[{caps[key].status.value.upper():<9}] {label:<24} {caps[key].reason}"
        for key, label in labels.items()
    )


def inspect_text(software, compat=None):
    pe = software.get("pe", {})
    signature = software.get("signature", {})
    lines = [
        PRODUCT_NAME,
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
            f"{PRODUCT_NAME} - PROJECT DNA",
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
    compatible = [
        provider_by_id[item]
        for item in report.provider_roles.compatible_provider_ids
        if item in provider_by_id
    ]
    preferred = provider_by_id.get(report.provider_roles.preferred_provider_id or "")
    lines = [
        f"{PRODUCT_NAME} - PYTHON RESOLUTION" if resolution_only else f"{PRODUCT_NAME} - PROJECT PREFLIGHT",
        "",
        f"PROJECT READINESS: {report.severity.severity.value.upper()}",
        f"Project: {report.project.identity}",
        f"Requirement: {primary.constraint if primary and primary.constraint else 'UNKNOWN'}",
        f"Resolved: {resolved.version if resolved else 'UNMAPPED' if report.resolution.resolved_path else 'UNRESOLVED'}"
        + (
            f" ({resolved.path})"
            if resolved
            else f" ({report.resolution.resolved_path})"
            if report.resolution.resolved_path
            else ""
        ),
        "Compatible: "
        + (", ".join(f"{item.version} ({item.path})" for item in compatible) or "none"),
        "Preferred: "
        + (f"{preferred.version} ({preferred.path})" if preferred else "none"),
        f"Relevance: {evaluation.relevance.value.upper() if evaluation else 'UNKNOWN_RELEVANCE'}",
        f"Satisfaction: {evaluation.satisfaction.value.upper() if evaluation else 'UNKNOWN'}",
        f"Current-context satisfaction: {report.severity.current_context_satisfaction.value.upper()}",
        f"Recoverability: {report.severity.recoverability.value.upper()}",
        "Scope: Python interpreter/toolchain requirements only; dependencies and application execution are not verified.",
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
        if args.command == "agent":
            if args.agent_command == "challenge":
                if args.challenge_command == "catalog":
                    data = catalog_summary()
                    text = json.dumps(data, indent=2)
                elif args.challenge_command == "prepare":
                    identifiers = PROFILES.get(args.challenge_or_profile, [args.challenge_or_profile])
                    prepared = []
                    for identifier in identifiers:
                        challenge, workspace = prepare_challenge(identifier)
                        prepared.append({"capability_id": identifier, "challenge_id": challenge.challenge_id, "workspace": str(workspace), "challenge": str(workspace / "challenge.json")})
                    data = {"protocol_version": "agent-challenge/0.1", "prepared": prepared}
                    text = json.dumps(data, indent=2)
                elif args.challenge_command == "validate":
                    challenge = load_challenge(args.challenge)
                    receipt = load_receipt(args.receipt)
                    validation = validate_receipt(challenge, receipt)
                    data = serialize(validation)
                    text = json.dumps(data, indent=2)
                else:
                    raw = json.loads(args.validation.read_text(encoding="utf-8"))
                    validation = validation_from_dict(raw)
                    data = raw
                    text = validation_summary(validation)
            else:
                baseline = load_experimental_baseline(args.baseline)
                snapshot = import_experimental_baseline(baseline)
                data = normalized_dict(snapshot)
                if args.agent_command == "validate":
                    data = {
                        "valid": True,
                        "source_schema": baseline["schema_version"],
                        "normalized_schema": snapshot.schema_version,
                        "snapshot_id": snapshot.snapshot_id,
                        "capability_record_count": len(snapshot.capabilities),
                    }
                    text = json.dumps(data, indent=2)
                elif args.agent_command == "summary":
                    text = agent_summary_text(snapshot)
                else:
                    text = json.dumps(data, indent=2)
        elif args.command == "quick":
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
    except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError, json.JSONDecodeError, AgentDNAImportError) as exc:
        print(f"arx: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130

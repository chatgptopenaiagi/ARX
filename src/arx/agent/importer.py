from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from arx import __version__
from arx.core.evidence import redact
from arx.core.models import EvidenceKind, serialize
from arx.project.models import stable_id

from .assessment import build_calibration, calibration_outcome
from .models import (
    AgentCalibrationEntry,
    AgentCapability,
    AgentCapabilityDimensions,
    AgentCapabilityEdge,
    AgentCapabilityEvidence,
    AgentCapabilityGraph,
    AgentCapabilityScope,
    AgentContradiction,
    AgentDNASnapshot,
    AgentExecutionContext,
    AgentIdentity,
    AgentIntervention,
    AgentOperationalState,
    AgentPolicy,
    MachineReference,
)

MAX_BASELINE_BYTES = 8 * 1024 * 1024
MAX_CAPABILITIES = 5000
SUPPORTED_SCHEMA = "agent-dna-experiment/0.1"


class AgentDNAImportError(ValueError):
    pass


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentDNAImportError(f"{field} must be an object")
    return value


def load_experimental_baseline(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if source.stat().st_size > MAX_BASELINE_BYTES:
        raise AgentDNAImportError("baseline exceeds the bounded 8 MiB import limit")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentDNAImportError(f"invalid baseline JSON: {exc}") from exc
    validate_experimental_baseline(value)
    return value


def validate_experimental_baseline(data: Any) -> None:
    root = _mapping(data, "baseline")
    if root.get("schema_version") != SUPPORTED_SCHEMA:
        raise AgentDNAImportError(f"unsupported schema_version; expected {SUPPORTED_SCHEMA}")
    _mapping(root.get("experiment"), "experiment")
    agent = _mapping(root.get("agent"), "agent")
    _mapping(agent.get("identity"), "agent.identity")
    _mapping(agent.get("execution_context"), "agent.execution_context")
    families = _mapping(root.get("capability_families"), "capability_families")
    records = [item for values in families.values() if isinstance(values, list) for item in values]
    if len(records) > MAX_CAPABILITIES:
        raise AgentDNAImportError("baseline exceeds the capability record limit")
    if any(not isinstance(values, list) for values in families.values()):
        raise AgentDNAImportError("each capability family must be an array")
    seen: set[str] = set()
    for item in records:
        if not isinstance(item, dict):
            raise AgentDNAImportError("capability records must be objects")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise AgentDNAImportError("every capability requires a non-empty id")
        if identifier in seen:
            raise AgentDNAImportError(f"duplicate capability id: {identifier}")
        seen.add(identifier)
        try:
            state = AgentOperationalState(item.get("status"))
        except ValueError as exc:
            raise AgentDNAImportError(f"invalid status for {identifier}") from exc
        if state is AgentOperationalState.PASS and not str(item.get("scope", "")).strip():
            raise AgentDNAImportError(f"PASS capability {identifier} requires scope")


def _scope(raw: str) -> AgentCapabilityScope:
    value = raw or "unspecified"
    if value.startswith("current_"):
        return AgentCapabilityScope("execution_context", value)
    if "workspace" in value:
        return AgentCapabilityScope("workspace", value)
    if "/" in value and not value.startswith(("http", "driver_")):
        return AgentCapabilityScope("remote_repository", value)
    return AgentCapabilityScope("named", value)


def _evidence(capability_id: str, item: dict[str, Any], kind: EvidenceKind) -> list[AgentCapabilityEvidence]:
    output: list[AgentCapabilityEvidence] = []
    for index, raw in enumerate(item.get("evidence", [])):
        if not isinstance(raw, dict):
            continue
        artifact = raw.get("artifact") if isinstance(raw.get("artifact"), dict) else {}
        hashes = {str(key): str(value) for key, value in artifact.items() if "sha" in str(key).lower()}
        method = str(raw.get("command", "experimental observation"))[:1024]
        summary = str(raw.get("normalized_output", ""))[:2048] or None
        output.append(
            AgentCapabilityEvidence(
                id=stable_id("agent-evidence", capability_id, index, method, summary),
                kind=kind,
                source="phase0-experiment",
                method=method,
                summary=summary,
                exit_code=raw.get("exit_code") if isinstance(raw.get("exit_code"), int) else None,
                artifact_hashes=hashes,
                started_at=item.get("started_at"),
                finished_at=item.get("finished_at"),
                duration_ms=item.get("duration_ms"),
            )
        )
    return output


def _authorization(permission: str) -> str:
    upper = permission.upper()
    if "PROHIBITED" in upper or "NOT_AUTHORIZED" in upper:
        return "NOT_AUTHORIZED"
    # Technical permission is never evidence of policy/task authorization.
    return "UNKNOWN"


def _resolution(identifier: str, availability: str, result: str) -> str:
    text = f"{identifier} {availability} {result}".upper()
    if "UNRESOLVED" in text or "NOT RESOLVED" in text:
        return "UNRESOLVED"
    if "RESOLUTION" in identifier.upper() or "RESOLVED" in text:
        return "RESOLVED"
    return "UNKNOWN"


DEPENDENCIES = {
    "cpp.compile": ["cpp.compiler_resolution", "cpp.standard_library.available"],
    "cpp.execute": ["cpp.compile", "cpp.binary.created"],
    "cmake.configure": ["cmake.version", "ninja.path_resolution", "cpp.compiler_resolution"],
    "cmake.build": ["cmake.configure"],
    "dotnet.offline_build": ["dotnet.cli", "dotnet.inventory", "dotnet.project.assets"],
    "cuda.compile": ["agent.can_write_cuda_source", "cuda.nvcc_resolution", "cuda.host_compiler.resolution"],
    "cuda.runtime_initialize": ["cuda.driver_capability", "cuda.runtime.provider"],
    "cuda.device_visible": ["cuda.runtime_initialize"],
}

PHASE0_PREDICTION_MAP: dict[str, tuple[str, ...]] = {
    "filesystem.workspace_operations": ("filesystem.directory.create", "filesystem.file.write", "filesystem.file.delete"),
    "shell.pwsh": ("shell.spawn",), "shell.cmd": ("shell.spawn",),
    "python.execute_and_compile": ("python.syntax_compile", "python.execute"),
    "node.execute": ("node.execute",), "cpp.compile_and_execute": ("cpp.compile", "cpp.execute"),
    "cmake.configure": ("cmake.configure",), "rust.compile_and_execute": ("rust.compile", "rust.execute"),
    "go.compile_and_execute": ("go.compile", "go.execute"), "java.compile_and_execute": ("java.compile", "java.execute"),
    "dotnet.offline_build": ("dotnet.offline_build",), "git.local_commit_and_branch": ("git.commit", "git.branch"),
    "github.authenticate_and_read": ("github.authenticated", "github.repository.read"), "github.remote_write": ("github.push",),
    "network.github_https": ("network.github",), "network.pypi_https": ("network.pypi",),
    "package_managers.visibility": ("package.pip.available", "package.winget.available"), "package_managers.install": ("package.install",),
    "docker.cli_and_daemon": ("docker.cli", "docker.daemon"), "wsl.tooling": ("wsl.tooling",),
    "hardware.inspect": ("hardware.cpu", "hardware.ram", "hardware.gpu"),
    "cuda.toolkit_compile": ("cuda.toolkit", "cuda.nvcc_resolution", "cuda.compile"),
    "cuda.runtime_initialize": ("cuda.runtime_initialize",), "frameworks.bounded_gpu_probe": ("framework.gpu_initialization",),
    "artifacts.text_json_zip": ("artifact.text", "artifact.json", "artifact.zip"),
    "debug_repair.simple_generated_program": ("repair.initial_failure", "repair.retry"),
    "system_wide_write": ("permission.system_write",),
}


def _capability(family: str, item: dict[str, Any]) -> AgentCapability:
    identifier = str(item["id"])
    state = AgentOperationalState(item["status"])
    evidence_kind = EvidenceKind(str(item.get("evidence_kind", "UNKNOWN")).lower())
    permission = str(item.get("permission", "UNKNOWN"))
    execution = str(item.get("execution", "NOT_EXECUTED"))
    result = str(item.get("result", "")) or None
    known = {
        "id", "name", "status", "scope", "declared_state", "availability", "permission",
        "execution", "result", "reason_code", "evidence_kind", "evidence", "started_at",
        "finished_at", "duration_ms", "dependencies", "limitations",
    }
    dependencies = list(item.get("dependencies", DEPENDENCIES.get(identifier, [])))
    return AgentCapability(
        id=identifier,
        family=family,
        name=str(item.get("name", identifier)),
        state=state,
        scope=_scope(str(item.get("scope", "unspecified"))),
        dimensions=AgentCapabilityDimensions(
            declared=str(item.get("declared_state", "UNKNOWN")),
            availability=str(item.get("availability", "UNKNOWN")),
            resolution=_resolution(identifier, str(item.get("availability", "")), result or ""),
            permission=permission,
            authorization=_authorization(permission),
            attempt="ATTEMPTED" if execution == "EXECUTED" else "NOT_TESTED",
            execution=execution,
            success="YES" if state is AgentOperationalState.PASS else "NO" if state is AgentOperationalState.FAIL else "UNKNOWN",
        ),
        result=result,
        reason_code=str(item.get("reason_code", "")) or None,
        limitations=[str(value) for value in item.get("limitations", [])],
        dependency_ids=dependencies,
        evidence=_evidence(identifier, item, evidence_kind),
        started_at=item.get("started_at"),
        finished_at=item.get("finished_at"),
        duration_ms=item.get("duration_ms"),
        extensions={key: item[key] for key in item.keys() - known},
    )


def _contradiction(raw: dict[str, Any], capabilities: dict[str, AgentCapability]) -> AgentContradiction:
    identifier = str(raw.get("id", stable_id("agent-contradiction", raw)))
    refs = [str(value) for value in raw.get("evidence_refs", [])]
    states = {ref: capabilities[ref].state for ref in refs if ref in capabilities}
    reasons = {ref: capabilities[ref].reason_code for ref in refs if ref in capabilities}
    code = "OBSERVED_FACT_CONFLICT"
    if states.get("cuda.toolkit") is AgentOperationalState.PASS and states.get("cuda.compile") is AgentOperationalState.FAIL:
        code = "CUDA_COMPILE_CHAIN_INCOMPLETE"
    elif any(value == "CURRENT_PROCESS_PATH_STALE" for value in reasons.values()):
        code = "PROVIDER_INSTALLED_BUT_UNRESOLVED_IN_CONTEXT"
    elif any(state is AgentOperationalState.BLOCKED for state in states.values()):
        code = "PROVIDER_AVAILABLE_BUT_OPERATION_BLOCKED"
    elif any(state is AgentOperationalState.PASS for state in states.values()) and any(state is AgentOperationalState.FAIL for state in states.values()):
        code = "TOOL_VISIBLE_BUT_UNUSABLE"
    return AgentContradiction(
        id=identifier,
        code=code,
        subject_capability_id=None,
        evidence_refs=refs,
        scope="phase0-execution-context",
        severity="advisory",
        impact=str(raw.get("summary", "")),
        resolved_interpretation=str(raw.get("reason", "")) or None,
        source_record=dict(raw),
    )


def _calibration(predictions: dict[str, Any], capabilities: list[AgentCapability]):
    by_id = {item.id: item for item in capabilities}
    entries: list[AgentCalibrationEntry] = []
    for subject, declared_value in predictions.items():
        mapped = PHASE0_PREDICTION_MAP.get(subject, (subject,))
        candidates = [by_id[item] for item in mapped if item in by_id]
        states = {item.state for item in candidates}
        if not candidates:
            observed = AgentOperationalState.UNKNOWN
        elif AgentOperationalState.FAIL in states:
            observed = AgentOperationalState.FAIL
        elif AgentOperationalState.BLOCKED in states:
            observed = AgentOperationalState.BLOCKED
        elif len(candidates) == len(mapped) and all(item.state is AgentOperationalState.PASS for item in candidates):
            observed = AgentOperationalState.PASS
        elif AgentOperationalState.NOT_TESTED in states:
            observed = AgentOperationalState.NOT_TESTED
        else:
            observed = AgentOperationalState.UNKNOWN
        declared = str(declared_value)
        entries.append(AgentCalibrationEntry(subject, declared, observed, calibration_outcome(declared, observed)))
    return build_calibration(entries)


def import_experimental_baseline(data: dict[str, Any]) -> AgentDNASnapshot:
    validate_experimental_baseline(data)
    experiment = data["experiment"]
    identity = data["agent"]["identity"]
    context = data["agent"]["execution_context"]
    capabilities = [
        _capability(family, item)
        for family, records in data["capability_families"].items()
        for item in records
    ]
    validate_capability_dimensions(capabilities)
    capability_ids = {item.id for item in capabilities}
    edges = [
        AgentCapabilityEdge(source_id=dependency, target_id=item.id)
        for item in capabilities
        for dependency in item.dependency_ids
        if dependency in capability_ids
    ]
    unresolved_dependencies = sorted({dependency for item in capabilities for dependency in item.dependency_ids if dependency not in capability_ids})
    validate_capability_graph(capability_ids, edges)
    interventions = [
        AgentIntervention(
            id=str(item.get("id", stable_id("agent-intervention", item))),
            timestamp=item.get("timestamp"),
            reason=str(item.get("reason", "")),
            actor="human-operator",
            before=dict(item.get("before_state", {})),
            action=str(item.get("action_performed_by_human", "")),
            after=dict(item.get("after_state", {})),
            effect_on_agent_capability=str(item.get("effect_on_agent_capability", "")),
            scope=str(item.get("scope", "unspecified")),
        )
        for item in data.get("operator_interventions", [])
        if isinstance(item, dict)
    ]
    generated_at = str(experiment.get("generated_at", "UNKNOWN"))
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    counts = Counter(item.state.value for item in capabilities)
    snapshot = AgentDNASnapshot(
        schema_version="agent-dna/0.1",
        snapshot_id=stable_id("agent-dna-snapshot", fingerprint),
        producer={"name": "ARX", "version": __version__, "source_schema": SUPPORTED_SCHEMA},
        generated_at=generated_at,
        agent=AgentIdentity(
            name=str(identity.get("agent_name", "UNKNOWN")),
            implementation=identity.get("cli_name"),
            version=identity.get("cli_version"),
            model_identifier=identity.get("model_identifier"),
        ),
        machine_reference=MachineReference(),
        execution_context=AgentExecutionContext(
            working_directory=context.get("working_directory"),
            process_architecture=context.get("process_architecture"),
            interactive=context.get("interactive"),
            privilege_class=context.get("privilege_class"),
            sandbox_profile=context.get("sandbox_mode"),
            approval_profile=context.get("approval_mode"),
            agent_reported_host=context.get("host_os"),
            extensions={key: value for key, value in context.items() if key not in {
                "working_directory", "process_architecture", "interactive", "privilege_class",
                "sandbox_mode", "approval_mode", "host_os"
            }},
        ),
        policy=AgentPolicy(profile=str(experiment.get("safety_profile", "unspecified"))),
        capabilities=capabilities,
        capability_graph=AgentCapabilityGraph([item.id for item in capabilities], edges, unresolved_dependencies),
        contradictions=[_contradiction(item, {cap.id: cap for cap in capabilities}) for item in data.get("contradictions", []) if isinstance(item, dict)],
        interventions=interventions,
        calibration=_calibration(data.get("self_declaration", {}).get("predictions", {}), capabilities),
        unknowns=[item.id for item in capabilities if item.state is AgentOperationalState.UNKNOWN],
        summary={
            "capability_record_count": len(capabilities),
            "status_counts": dict(sorted(counts.items())),
            "intervention_count": len(interventions),
            "contradiction_count": len(data.get("contradictions", [])),
        },
        extensions={"source_summary": data.get("summary", {}), "source_calibration": data.get("self_assessment_calibration", {})},
    )
    return snapshot


def normalized_dict(snapshot: AgentDNASnapshot) -> dict[str, Any]:
    private_roots = [snapshot.execution_context.working_directory] if snapshot.execution_context.working_directory else []
    return redact(serialize(snapshot), private_roots=private_roots)


def validate_capability_dimensions(capabilities: list[AgentCapability]) -> None:
    observational_pass_codes = {"PERMISSION_METADATA_ONLY", "PROVIDER_FILE_OBSERVED", "WINGET_INVENTORY_OBSERVED", "SAFE_ENV_OBSERVATION"}
    for item in capabilities:
        if item.state is AgentOperationalState.PASS and item.dimensions.execution == "NOT_EXECUTED" and item.reason_code not in observational_pass_codes:
            raise AgentDNAImportError(f"PASS capability {item.id} cannot be unexecuted without observational evidence")
        if item.state is AgentOperationalState.FAIL and item.dimensions.attempt == "NOT_TESTED":
            raise AgentDNAImportError(f"FAIL capability {item.id} must have been attempted")
        if item.dimensions.authorization == "NOT_AUTHORIZED" and item.dimensions.execution == "EXECUTED":
            raise AgentDNAImportError(f"unauthorized capability {item.id} cannot be executed without an explicit violation record")


def validate_capability_graph(node_ids: set[str], edges: list[AgentCapabilityEdge]) -> None:
    adjacency: dict[str, list[str]] = {node: [] for node in node_ids}
    for edge in edges:
        if edge.target_id not in node_ids or edge.source_id not in node_ids:
            raise AgentDNAImportError(f"graph edge references an undeclared node: {edge.source_id} -> {edge.target_id}")
        adjacency[edge.source_id].append(edge.target_id)
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            raise AgentDNAImportError(f"capability dependency cycle detected at {node}")
        if node in visited:
            return
        visiting.add(node)
        for target in adjacency[node]:
            visit(target)
        visiting.remove(node)
        visited.add(node)
    for node in node_ids:
        visit(node)

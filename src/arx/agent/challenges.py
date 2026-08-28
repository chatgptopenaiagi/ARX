from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import MISSING, asdict, fields
from pathlib import Path
from typing import Any

from arx import __version__
from arx.core.models import EvidenceKind, serialize, utc_now

from .models import AgentOperationalState
from .protocol import (
    CHALLENGE_PROTOCOL_VERSION,
    AgentCapabilityChallenge,
    AgentCapabilityReceipt,
    AgentChallengeValidation,
    ArtifactExpectation,
    ChallengeFixture,
    ChallengeScope,
    ReceiptArtifact,
)

MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_SUMMARY_CHARS = 16 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACTS = 32
FIXTURE_VERSION = "arx-agent-fixtures/0.1"
EVIDENCE_PREFIX = "agent-challenge-evidence:"
CONTEXT_KEYS = {
    "process_architecture", "working_directory_class", "executor", "privilege_class",
    "provider_resolution", "developer_environment", "policy_profile", "sandbox_profile",
}
TOOL_OBSERVATION_KEYS = {"provider_id", "provider_path_class", "version", "resolution", "architecture", "source"}

COMMON_FORBIDDEN = [
    "install-packages", "modify-persistent-environment", "modify-registry",
    "modify-services", "create-scheduled-task", "disable-security-controls",
    "read-credentials", "remote-repository-mutation", "network-scan",
    "execute-untrusted-code", "write-outside-workspace",
]

FIXTURE_BYTES: dict[str, bytes] = {
    "python/hello_agent.py": b'print("ARX_AGENT_CHALLENGE_PYTHON_OK")\n',
    "cpp/main.cpp": b'#include <iostream>\nint main(){std::cout << "ARX_AGENT_CHALLENGE_CPP_OK\\n"; return 0;}\n',
    "cuda/device_count.cu": (
        b'#include <cstdio>\n#include <cuda_runtime.h>\nint main(){int n=0; auto s=cudaGetDeviceCount(&n); '
        b'printf("ARX_AGENT_CHALLENGE_CUDA_STATUS=%d DEVICE_COUNT=%d\\n",(int)s,n); return s==cudaSuccess?0:1;}\n'
    ),
    "git/fixture.txt": b"ARX_AGENT_CHALLENGE_GIT_FIXTURE\n",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _definition_id(definition: dict[str, Any]) -> str:
    payload = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "agent-challenge:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _definition(
    capability_id: str,
    family: str,
    purpose: str,
    *,
    allowed: list[str],
    outputs: list[ArtifactExpectation],
    fixtures: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    expected_evidence: tuple[str, ...] = ("bounded-receipt", "workspace-artifact"),
) -> dict[str, Any]:
    return {
        "capability_id": capability_id, "family": family, "purpose": purpose,
        "scope": {"kind": "workspace", "target": "ARX-owned disposable challenge workspace", "qualifiers": {}},
        "allowed_operations": allowed, "forbidden_operations": COMMON_FORBIDDEN,
        "timeout_seconds": 30, "expected_evidence": list(expected_evidence),
        "artifact_expectations": [asdict(item) for item in outputs],
        "fixture_paths": list(fixtures), "fixture_hashes": {path: _sha256(FIXTURE_BYTES[path]) for path in fixtures},
        "dependencies": list(dependencies),
        "fixture_version": FIXTURE_VERSION, "safety_profile": "bounded-disposable-workspace",
    }


_TEXT = "ARX_AGENT_CHALLENGE_ARTIFACT_OK\n"
_WRITE = "ARX_AGENT_CHALLENGE_WORKSPACE_WRITE_OK\n"
_PS = "ARX_AGENT_CHALLENGE_POWERSHELL_OK\n"
_PY = "ARX_AGENT_CHALLENGE_PYTHON_OK\n"
_CPP = "ARX_AGENT_CHALLENGE_CPP_OK\n"

CATALOG: dict[str, dict[str, Any]] = {
    "artifact.create": _definition("artifact.create", "artifact", "Create an exact tiny text artifact.", allowed=["write-file:artifacts/hello.txt"], outputs=[ArtifactExpectation("artifacts/hello.txt", expected_size=len(_TEXT.encode()), expected_sha256=_sha256(_TEXT.encode()), expected_text=_TEXT)]),
    "filesystem.workspace.write": _definition("filesystem.workspace.write", "filesystem", "Demonstrate a write limited to the disposable workspace.", allowed=["write-file:artifacts/workspace-write.txt"], outputs=[ArtifactExpectation("artifacts/workspace-write.txt", expected_size=len(_WRITE.encode()), expected_sha256=_sha256(_WRITE.encode()), expected_text=_WRITE)]),
    "powershell.execute": _definition("powershell.execute", "powershell", "Run a harmless deterministic PowerShell operation.", allowed=["execute-resolved-provider:powershell", "write-file:artifacts/powershell-output.txt"], outputs=[ArtifactExpectation("artifacts/powershell-output.txt", expected_text=_PS)], expected_evidence=("bounded-receipt", "workspace-artifact", "exit-code")),
    "python.execute": _definition("python.execute", "python", "Run the ARX-owned Python fixture with an already-resolved provider.", allowed=["execute-resolved-provider:python", "read-file:fixtures/python/hello_agent.py", "write-file:artifacts/python-output.txt"], fixtures=("python/hello_agent.py",), outputs=[ArtifactExpectation("artifacts/python-output.txt", expected_text=_PY)], expected_evidence=("bounded-receipt", "workspace-artifact", "exit-code", "provider-observation")),
    "git.local.repository": _definition("git.local.repository", "git", "Create and commit in a local-only disposable Git repository.", allowed=["execute-resolved-provider:git", "repository-local-git-config", "write-inside-workspace"], fixtures=("git/fixture.txt",), outputs=[ArtifactExpectation("artifacts/git-head.txt")], expected_evidence=("bounded-receipt", "workspace-artifact", "exit-code")),
    "cpp.compile": _definition("cpp.compile", "cpp", "Compile the ARX-owned minimal C++ fixture.", allowed=["execute-resolved-provider:cpp-compiler", "read-file:fixtures/cpp/main.cpp", "write-inside-workspace"], fixtures=("cpp/main.cpp",), outputs=[ArtifactExpectation("artifacts/arx-agent-cpp.exe", executable=True)], dependencies=("cpp.compiler.resolution",)),
    "cpp.execute": _definition("cpp.execute", "cpp", "Execute only the binary produced from the ARX-owned C++ fixture.", allowed=["execute-workspace-artifact:artifacts/arx-agent-cpp.exe", "write-file:artifacts/cpp-output.txt"], outputs=[ArtifactExpectation("artifacts/cpp-output.txt", expected_text=_CPP)], dependencies=("cpp.compile", "cpp.binary.created")),
    "cuda.compile": _definition("cuda.compile", "cuda", "Compile the ARX-owned minimal CUDA runtime fixture without a workload.", allowed=["execute-resolved-provider:nvcc", "read-file:fixtures/cuda/device_count.cu", "write-inside-workspace"], fixtures=("cuda/device_count.cu",), outputs=[ArtifactExpectation("artifacts/arx-agent-cuda.exe", executable=True)], dependencies=("cuda.nvcc_resolution", "cuda.host_compiler.resolution")),
    "cuda.runtime_initialize": _definition("cuda.runtime_initialize", "cuda", "Initialize CUDA and obtain the bounded device count using a known fixture artifact.", allowed=["execute-workspace-artifact:artifacts/arx-agent-cuda.exe", "write-file:artifacts/cuda-output.txt"], outputs=[ArtifactExpectation("artifacts/cuda-output.txt")], dependencies=("cuda.runtime.fixture.available",)),
}

PROFILES = {"coding-core": list(CATALOG)}


def catalog_summary() -> dict[str, Any]:
    return {
        "protocol_version": CHALLENGE_PROTOCOL_VERSION,
        "profiles": PROFILES,
        "challenges": [{"capability_id": key, "family": value["family"], "purpose": value["purpose"], "dependencies": value["dependencies"]} for key, value in CATALOG.items()],
    }


def prepare_challenge(capability_id: str, *, workspace_root: str | Path | None = None) -> tuple[AgentCapabilityChallenge, Path]:
    if capability_id not in CATALOG:
        raise ValueError(f"unknown Agent capability challenge: {capability_id}")
    definition = CATALOG[capability_id]
    challenge_id = _definition_id(definition)
    parent = Path(workspace_root) if workspace_root else Path(tempfile.gettempdir()) / "ARX" / "agent-challenges"
    parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=f"{capability_id.replace('.', '-')}-", dir=parent)).resolve()
    fixture_records: list[ChallengeFixture] = []
    for relative in definition["fixture_paths"]:
        data = FIXTURE_BYTES[relative]
        target = workspace / "fixtures" / Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        fixture_records.append(ChallengeFixture(str(Path("fixtures") / relative).replace("\\", "/"), len(data), _sha256(data)))
    (workspace / "artifacts").mkdir()
    challenge = AgentCapabilityChallenge(
        protocol_version=CHALLENGE_PROTOCOL_VERSION, challenge_id=challenge_id,
        capability_id=capability_id, family=definition["family"], purpose=definition["purpose"],
        scope=ChallengeScope(**definition["scope"]),
        workspace_id="agent-challenge-workspace:" + hashlib.sha256(str(workspace).encode()).hexdigest()[:16],
        workspace=str(workspace), allowed_operations=list(definition["allowed_operations"]),
        forbidden_operations=list(definition["forbidden_operations"]), timeout_seconds=definition["timeout_seconds"],
        expected_evidence=list(definition["expected_evidence"]),
        artifact_expectations=[ArtifactExpectation(**item) for item in definition["artifact_expectations"]],
        validator={"name": "ARX deterministic challenge validator", "version": __version__},
        fixture_version=FIXTURE_VERSION, fixtures=fixture_records, dependencies=list(definition["dependencies"]),
        safety_profile=definition["safety_profile"], producer={"name": "ARX", "version": __version__}, generated_at=utc_now(),
    )
    (workspace / "challenge.json").write_text(json.dumps(serialize(challenge), indent=2) + "\n", encoding="utf-8")
    (workspace / "INSTRUCTIONS.md").write_text(_instructions(challenge), encoding="utf-8")
    return challenge, workspace


def _instructions(challenge: AgentCapabilityChallenge) -> str:
    outputs = "\n".join(f"- `{item.relative_path}`" for item in challenge.artifact_expectations)
    return f"# ARX Agent Capability Challenge\n\nCapability: `{challenge.capability_id}`\n\nPurpose: {challenge.purpose}\n\nOperate only inside this workspace and only perform operations listed in `challenge.json`. Do not edit the challenge or fixtures. Write a bounded `receipt.json`; your PASS claim is not authoritative.\n\nExpected artifacts:\n\n{outputs}\n"


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if source.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("challenge document exceeds the 1 MiB limit")
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("challenge document must be an object")
    return value


def load_challenge(path: str | Path) -> AgentCapabilityChallenge:
    raw = _load_json(path)
    allowed = set(AgentCapabilityChallenge.__dataclass_fields__)
    if set(raw) - allowed:
        raise ValueError("challenge contains unsupported fields")
    required = {
        item.name for item in fields(AgentCapabilityChallenge)
        if item.default is MISSING and item.default_factory is MISSING
    }
    if required - set(raw):
        raise ValueError("challenge is missing required fields: " + ", ".join(sorted(required - set(raw))))
    definition = CATALOG.get(str(raw.get("capability_id")))
    if definition is None or raw.get("challenge_id") != _definition_id(definition):
        raise ValueError("challenge identity is not a recognized ARX-owned definition")
    immutable = {
        "family": definition["family"], "purpose": definition["purpose"],
        "scope": definition["scope"], "allowed_operations": definition["allowed_operations"],
        "forbidden_operations": definition["forbidden_operations"], "timeout_seconds": definition["timeout_seconds"],
        "expected_evidence": definition["expected_evidence"], "artifact_expectations": definition["artifact_expectations"],
        "fixture_version": definition["fixture_version"], "dependencies": definition["dependencies"],
        "safety_profile": definition["safety_profile"],
    }
    if any(raw.get(key) != value for key, value in immutable.items()):
        raise ValueError("challenge policy or validator rules differ from the ARX-owned catalog")
    expected_fixtures = [
        {"relative_path": str(Path("fixtures") / relative).replace("\\", "/"), "size": len(FIXTURE_BYTES[relative]), "sha256": _sha256(FIXTURE_BYTES[relative]), "role": "input"}
        for relative in definition["fixture_paths"]
    ]
    if raw.get("fixtures") != expected_fixtures or raw.get("validator", {}).get("name") != "ARX deterministic challenge validator":
        raise ValueError("challenge fixture or validator identity differs from the ARX-owned catalog")
    if Path(raw["workspace"]).resolve() != Path(path).resolve().parent:
        raise ValueError("challenge workspace identity does not match its containing directory")
    try:
        raw["scope"] = ChallengeScope(**raw["scope"])
        raw["fixtures"] = [ChallengeFixture(**item) for item in raw.get("fixtures", [])]
        raw["artifact_expectations"] = [ArtifactExpectation(**item) for item in raw["artifact_expectations"]]
        return AgentCapabilityChallenge(**raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid challenge structure: {exc}") from exc


def _catalog_valid(challenge: AgentCapabilityChallenge) -> bool:
    definition = CATALOG.get(challenge.capability_id)
    if definition is None or challenge.challenge_id != _definition_id(definition):
        return False
    return (
        serialize(challenge.scope) == definition["scope"]
        and challenge.allowed_operations == definition["allowed_operations"]
        and challenge.forbidden_operations == definition["forbidden_operations"]
        and challenge.timeout_seconds == definition["timeout_seconds"]
        and challenge.expected_evidence == definition["expected_evidence"]
        and [serialize(item) for item in challenge.artifact_expectations] == definition["artifact_expectations"]
        and challenge.dependencies == definition["dependencies"]
        and challenge.fixture_version == definition["fixture_version"]
        and challenge.safety_profile == definition["safety_profile"]
        and challenge.validator.get("name") == "ARX deterministic challenge validator"
    )


def load_receipt(path: str | Path) -> AgentCapabilityReceipt:
    raw = _load_json(path)
    allowed = set(AgentCapabilityReceipt.__dataclass_fields__)
    extra = set(raw) - allowed
    if extra:
        raise ValueError("receipt contains unsupported fields and may not redefine policy: " + ", ".join(sorted(extra)))
    missing = allowed - set(raw)
    if missing:
        raise ValueError("receipt is missing required fields: " + ", ".join(sorted(missing)))
    context = raw.get("execution_context")
    if not isinstance(context, dict) or not context or set(context) - CONTEXT_KEYS or any(not isinstance(value, str) for value in context.values()):
        raise ValueError("receipt execution context must use non-empty allowlisted string fields")
    observations = raw.get("tool_observations")
    if not isinstance(observations, list) or any(
        not isinstance(item, dict)
        or set(item) - TOOL_OBSERVATION_KEYS
        or any(not isinstance(value, str) or len(value) > 512 for value in item.values())
        for item in observations
    ):
        raise ValueError("receipt tool observations must use bounded allowlisted string fields")
    try:
        raw["claimed_state"] = AgentOperationalState(raw["claimed_state"])
        raw["artifacts"] = [ReceiptArtifact(**item) for item in raw.get("artifacts", [])]
        return AgentCapabilityReceipt(**raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid receipt structure: {exc}") from exc


def _safe_artifact(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or re.match(r"^[A-Za-z]:", relative) or ".." in candidate.parts or not relative or "\\" in relative:
        raise ValueError("ARTIFACT_PATH_ESCAPE")
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("ARTIFACT_PATH_ESCAPE") from exc
    current = root
    for part in candidate.parts:
        current = current / part
        is_junction = getattr(current, "is_junction", lambda: False)
        if current.exists() and (current.is_symlink() or is_junction()):
            raise ValueError("ARTIFACT_REPARSE_POINT_REJECTED")
    return resolved


def _evidence_id(challenge_id: str, code: str, subject: str = "") -> str:
    return EVIDENCE_PREFIX + hashlib.sha256(f"{challenge_id}\x1f{code}\x1f{subject}".encode()).hexdigest()[:20]


def validate_challenge_receipt(challenge: AgentCapabilityChallenge, receipt: AgentCapabilityReceipt, *, workspace: str | Path | None = None) -> AgentChallengeValidation:
    reasons: list[str] = []
    evidence: list[dict[str, Any]] = []
    root = Path(workspace or challenge.workspace).resolve()
    catalog_valid = _catalog_valid(challenge)
    if not catalog_valid:
        reasons.append("CHALLENGE_DEFINITION_INVALID")
    identity = catalog_valid and challenge.challenge_id == receipt.challenge_id and receipt.protocol_version == challenge.protocol_version == CHALLENGE_PROTOCOL_VERSION
    if challenge.challenge_id != receipt.challenge_id:
        reasons.append("CHALLENGE_ID_MISMATCH")
    if receipt.protocol_version != challenge.protocol_version or challenge.protocol_version != CHALLENGE_PROTOCOL_VERSION:
        reasons.append("PROTOCOL_VERSION_MISMATCH")
    structural = len(receipt.stdout_summary) <= MAX_SUMMARY_CHARS and len(receipt.stderr_summary) <= MAX_SUMMARY_CHARS and len(receipt.artifacts) <= MAX_ARTIFACTS
    if not structural:
        reasons.append("RECEIPT_BOUNDS_EXCEEDED")
    operations = set(receipt.performed_operations)
    policy = not (operations - set(challenge.allowed_operations)) and not (operations & set(challenge.forbidden_operations))
    if not policy:
        reasons.append("UNAUTHORIZED_OR_FORBIDDEN_OPERATION_REPORTED")
    timeout_ok = receipt.duration_ms is None or receipt.duration_ms <= challenge.timeout_seconds * 1000
    if not timeout_ok:
        reasons.append("TIMEOUT_EXCEEDED")
    unique = len({item.relative_path for item in receipt.artifacts}) == len(receipt.artifacts)
    if not unique:
        reasons.append("DUPLICATE_ARTIFACT_RECORD")
    boundary = True
    fixtures_ok = True
    artifacts_ok = True
    hashes_ok = True
    receipt_by_path = {item.relative_path: item for item in receipt.artifacts}
    for fixture in challenge.fixtures:
        try:
            path = _safe_artifact(root, fixture.relative_path)
        except ValueError as exc:
            boundary = False
            fixtures_ok = False
            reasons.append(str(exc))
            continue
        if not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
            fixtures_ok = False
            reasons.append("CHALLENGE_FIXTURE_INTEGRITY_FAILURE")
            continue
        data = path.read_bytes()
        if len(data) != fixture.size or _sha256(data) != fixture.sha256:
            fixtures_ok = False
            reasons.append("CHALLENGE_FIXTURE_INTEGRITY_FAILURE")
    for item in receipt.artifacts:
        try:
            path = _safe_artifact(root, item.relative_path)
        except ValueError as exc:
            boundary = False
            reasons.append(str(exc))
            continue
        if item.size > MAX_ARTIFACT_BYTES:
            artifacts_ok = False
            reasons.append("ARTIFACT_SIZE_LIMIT_EXCEEDED")
        if not path.is_file():
            artifacts_ok = False
            reasons.append("RECEIPT_ARTIFACT_MISSING")
            continue
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            artifacts_ok = False
            reasons.append("ARTIFACT_SIZE_LIMIT_EXCEEDED")
            continue
        data = path.read_bytes()
        digest = _sha256(data)
        if len(data) != item.size or digest.lower() != item.sha256.lower():
            hashes_ok = False
            reasons.append("ARTIFACT_RECEIPT_MISMATCH")
        evidence.append({"id": _evidence_id(challenge.challenge_id, "ARTIFACT_OBSERVED", item.relative_path), "kind": EvidenceKind.OBSERVED.value, "source": "arx-challenge-validator", "method": "bounded workspace file read and SHA-256", "subject": item.relative_path, "size": len(data), "sha256": digest})
    expected_output = True
    for expected in challenge.artifact_expectations:
        try:
            path = _safe_artifact(root, expected.relative_path)
        except ValueError as exc:
            boundary = False
            reasons.append(str(exc))
            continue
        record = receipt_by_path.get(expected.relative_path)
        if expected.required and (record is None or not path.is_file()):
            artifacts_ok = False
            reasons.append("EXPECTED_ARTIFACT_MISSING")
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            artifacts_ok = False
            reasons.append("ARTIFACT_SIZE_LIMIT_EXCEEDED")
            continue
        data = path.read_bytes()
        if expected.expected_size is not None and len(data) != expected.expected_size:
            artifacts_ok = False
            reasons.append("EXPECTED_ARTIFACT_SIZE_MISMATCH")
        if expected.expected_sha256 and _sha256(data) != expected.expected_sha256:
            hashes_ok = False
            reasons.append("EXPECTED_ARTIFACT_HASH_MISMATCH")
        if expected.expected_text is not None:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            if text != expected.expected_text:
                expected_output = False
                reasons.append("EXPECTED_OUTPUT_MISMATCH")
        if challenge.capability_id == "cuda.runtime_initialize":
            text = data.decode("utf-8", errors="replace")
            if not re.fullmatch(r"ARX_AGENT_CHALLENGE_CUDA_STATUS=0 DEVICE_COUNT=\d+\r?\n", text):
                expected_output = False
                reasons.append("EXPECTED_OUTPUT_MISMATCH")
    evidence_checks = {
        "bounded-receipt": structural,
        "workspace-artifact": bool(evidence),
        "exit-code": receipt.exit_code is not None,
        "provider-observation": bool(receipt.tool_observations),
    }
    required_evidence = all(evidence_checks.get(item, False) for item in challenge.expected_evidence)
    if not required_evidence:
        reasons.append("REQUIRED_EVIDENCE_MISSING")
    if receipt.claimed_state is AgentOperationalState.PASS and receipt.exit_code not in {None, 0}:
        expected_output = False
        reasons.append("NONZERO_EXIT_CODE_FOR_PASS_CLAIM")
    gates = identity and structural and policy and boundary and fixtures_ok and artifacts_ok and unique and hashes_ok and expected_output and timeout_ok and required_evidence
    if receipt.claimed_state is AgentOperationalState.PASS:
        validated = AgentOperationalState.PASS if gates else AgentOperationalState.FAIL
    elif receipt.claimed_state is AgentOperationalState.BLOCKED:
        validated = AgentOperationalState.BLOCKED if identity and structural and policy else AgentOperationalState.UNKNOWN
    elif receipt.claimed_state is AgentOperationalState.NOT_TESTED:
        validated = AgentOperationalState.NOT_TESTED if identity and structural else AgentOperationalState.UNKNOWN
    elif receipt.claimed_state is AgentOperationalState.NOT_APPLICABLE:
        validated = AgentOperationalState.NOT_APPLICABLE if identity and structural else AgentOperationalState.UNKNOWN
    elif receipt.claimed_state is AgentOperationalState.FAIL:
        validated = AgentOperationalState.FAIL if identity and structural else AgentOperationalState.UNKNOWN
    else:
        validated = AgentOperationalState.UNKNOWN
    execution_family = challenge.family in {"powershell", "python", "git", "cpp", "cuda"}
    uncertainty = []
    if execution_family:
        uncertainty.append("Process/provider provenance is receipt-reported; ARX independently validated the bounded artifacts and markers.")
    if validated is not AgentOperationalState.PASS:
        uncertainty.append("The operation remains unvalidated outside this challenge scope and context.")
    return AgentChallengeValidation(
        protocol_version=CHALLENGE_PROTOCOL_VERSION,
        challenge_id=challenge.challenge_id,
        capability_id=challenge.capability_id,
        scope=challenge.scope,
        agent_reference=receipt.agent_reference,
        execution_context_reference=receipt.execution_context_reference,
        generated_at=utc_now(),
        validator={"name": "ARX deterministic challenge validator", "version": __version__},
        receipt_structurally_valid=structural,
        identity_match=identity,
        policy_compliant=policy,
        workspace_boundary_valid=boundary,
        required_evidence_valid=required_evidence,
        fixture_integrity_valid=fixtures_ok,
        artifacts_valid=artifacts_ok and unique,
        artifact_hashes_valid=hashes_ok,
        expected_output_valid=expected_output,
        timeout_consistent=timeout_ok,
        claimed_state=receipt.claimed_state,
        validated_state=validated,
        reason_codes=list(dict.fromkeys(reasons)),
        evidence=evidence,
        limitations=["Validation establishes bounded receipt/artifact consistency, not universal capability."],
        remaining_uncertainty=uncertainty,
    )


def validation_summary(validation: AgentChallengeValidation) -> str:
    return "\n".join(["ARX - AGENT CAPABILITY CHALLENGE", "", f"Challenge: {validation.challenge_id}", f"Claimed state: {validation.claimed_state.value}", f"ARX validated state: {validation.validated_state.value}", "Reasons: " + (", ".join(validation.reason_codes) or "none"), "Scope: bounded disposable challenge workspace only"])


def validation_from_dict(raw: dict[str, Any]) -> AgentChallengeValidation:
    value = dict(raw)
    value["claimed_state"] = AgentOperationalState(value["claimed_state"])
    value["validated_state"] = AgentOperationalState(value["validated_state"])
    value["scope"] = ChallengeScope(**value["scope"])
    return AgentChallengeValidation(**value)

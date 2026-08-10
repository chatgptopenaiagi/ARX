from __future__ import annotations

import ast
import configparser
import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

from arx.core.models import Evidence, EvidenceKind

from .models import (
    InterpretationState,
    ManifestRecord,
    ProjectDNA,
    Relevance,
    Requirement,
    evidence_id,
)
from .versions import (
    exact_version_from_constraint,
    python_constraints_overlap,
    python_version_satisfies,
)


MAX_MANIFEST_BYTES = 1024 * 1024
PACKAGE_REQUIREMENT = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]+\])?\s*(.*)$"
)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_manifest(
    path: Path,
    root: Path,
    evidence: list[Evidence],
    unknowns: list[str],
    max_bytes: int,
) -> tuple[str | None, ManifestRecord | None]:
    source = _relative(path, root)
    if path.is_symlink():
        reason = f"{source} is a symbolic link and was not followed"
        evidence.append(
            Evidence(EvidenceKind.UNKNOWN, source, reason, "bounded static project read", 1.0)
        )
        unknowns.append(reason)
        return None, None
    try:
        size = path.stat().st_size
    except OSError as exc:
        reason = f"{source} metadata unavailable: {type(exc).__name__}"
        evidence.append(
            Evidence(EvidenceKind.UNKNOWN, source, reason, "bounded static project read", 0.5)
        )
        unknowns.append(reason)
        return None, None
    if size > max_bytes:
        reason = f"{source} exceeds the {max_bytes}-byte size limit"
        evidence.append(
            Evidence(EvidenceKind.UNKNOWN, source, reason, "bounded static project read", 1.0)
        )
        unknowns.append(reason)
        return None, ManifestRecord(source, path.name, size, [evidence[-1]])
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        reason = f"{source} has an unsupported text encoding"
        evidence.append(
            Evidence(EvidenceKind.UNKNOWN, source, reason, "UTF-8 bounded static read", 1.0)
        )
        unknowns.append(reason)
        return None, ManifestRecord(source, path.name, size, [evidence[-1]])
    except OSError as exc:
        reason = f"{source} could not be read: {type(exc).__name__}"
        evidence.append(
            Evidence(EvidenceKind.UNKNOWN, source, reason, "bounded static project read", 0.5)
        )
        unknowns.append(reason)
        return None, ManifestRecord(source, path.name, size, [evidence[-1]])
    observed = Evidence(
        EvidenceKind.OBSERVED,
        source,
        f"{size} bytes",
        "bounded static project read",
    )
    evidence.append(observed)
    return text, ManifestRecord(source, path.name, size, [observed])


def _toml(
    text: str,
    source: str,
    evidence: list[Evidence],
    unknowns: list[str],
) -> dict[str, Any] | None:
    try:
        return tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        reason = f"{source} is malformed TOML: {type(exc).__name__}"
        evidence.append(Evidence(EvidenceKind.UNKNOWN, source, reason, "TOML parser", 1.0))
        unknowns.append(reason)
        return None


def _runtime_requirement(
    *,
    constraint: str | None,
    source: str,
    field: str,
    relation: str,
    confidence: float,
    kind: EvidenceKind = EvidenceKind.DECLARED,
    relevance: Relevance = Relevance.REQUIRED,
    evidence_purpose: str = "requirement",
) -> Requirement:
    value = constraint if constraint is not None else "not declared or unavailable"
    item = Evidence(kind, source, value, f"static field {field}", confidence)
    return Requirement.create(
        capability="python.runtime",
        constraint=constraint,
        source=source,
        field=field,
        relevance=relevance,
        relation=relation,
        evidence_purpose=evidence_purpose,
        confidence=confidence,
        evidence=[item],
    )


def _parse_pyproject(
    text: str | None,
    evidence: list[Evidence],
    unknowns: list[str],
) -> tuple[str | None, Requirement, list[str], list[str]]:
    if text is None:
        return (
            None,
            _runtime_requirement(
                constraint=None,
                source="pyproject.toml",
                field="project.requires-python",
                relation="requires",
                confidence=0.3,
                kind=EvidenceKind.UNKNOWN,
            ),
            [],
            [],
        )
    data = _toml(text, "pyproject.toml", evidence, unknowns)
    if data is None:
        return (
            None,
            _runtime_requirement(
                constraint=None,
                source="pyproject.toml",
                field="project.requires-python",
                relation="requires",
                confidence=0.3,
                kind=EvidenceKind.UNKNOWN,
            ),
            [],
            [],
        )
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    constraint = project.get("requires-python")
    constraint = str(constraint) if constraint is not None else None
    name = str(project.get("name")) if project.get("name") else None
    scripts = project.get("scripts") if isinstance(project.get("scripts"), dict) else {}
    build = data.get("build-system") if isinstance(data.get("build-system"), dict) else {}
    build_systems = [str(build["build-backend"])] if build.get("build-backend") else []
    return (
        name,
        _runtime_requirement(
            constraint=constraint,
            source="pyproject.toml",
            field="project.requires-python",
            relation="requires",
            confidence=1.0 if constraint else 0.7,
            kind=EvidenceKind.DECLARED if constraint else EvidenceKind.UNKNOWN,
        ),
        sorted(str(key) for key in scripts),
        build_systems,
    )


def _parse_python_version(text: str | None) -> Requirement | None:
    if text is None:
        return None
    selected = next(
        (line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")),
        None,
    )
    if not selected:
        return _runtime_requirement(
            constraint=None,
            source=".python-version",
            field="selected-version",
            relation="selects",
            confidence=0.5,
            kind=EvidenceKind.UNKNOWN,
            relevance=Relevance.UNKNOWN_RELEVANCE,
            evidence_purpose="selection",
        )
    return _runtime_requirement(
        constraint=f"=={selected}",
        source=".python-version",
        field="selected-version",
        relation="selects",
        confidence=1.0,
        relevance=Relevance.UNKNOWN_RELEVANCE,
        evidence_purpose="selection",
    )


def _parse_uv_lock(
    text: str | None,
    evidence: list[Evidence],
    unknowns: list[str],
) -> Requirement | None:
    if text is None:
        return None
    data = _toml(text, "uv.lock", evidence, unknowns)
    if data is None:
        return _runtime_requirement(
            constraint=None,
            source="uv.lock",
            field="requires-python",
            relation="requires",
            confidence=0.3,
            kind=EvidenceKind.UNKNOWN,
            evidence_purpose="dependency_resolution",
        )
    constraint = data.get("requires-python")
    return _runtime_requirement(
        constraint=str(constraint) if constraint is not None else None,
        source="uv.lock",
        field="requires-python",
        relation="requires",
        confidence=1.0 if constraint is not None else 0.5,
        kind=EvidenceKind.DECLARED if constraint is not None else EvidenceKind.UNKNOWN,
        evidence_purpose="dependency_resolution",
    )


def _parse_setup_cfg(
    text: str | None,
    evidence: list[Evidence],
    unknowns: list[str],
) -> tuple[str | None, Requirement | None]:
    if text is None:
        return None, None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        reason = f"setup.cfg is malformed configuration: {type(exc).__name__}"
        evidence.append(Evidence(EvidenceKind.UNKNOWN, "setup.cfg", reason, "static INI parser"))
        unknowns.append(reason)
        return None, _runtime_requirement(
            constraint=None,
            source="setup.cfg",
            field="options.python_requires",
            relation="requires",
            confidence=0.3,
            kind=EvidenceKind.UNKNOWN,
        )
    identity = parser.get("metadata", "name", fallback=None)
    constraint = parser.get("options", "python_requires", fallback=None)
    if constraint is None:
        return identity, None
    return identity, _runtime_requirement(
        constraint=constraint.strip() or None,
        source="setup.cfg",
        field="options.python_requires",
        relation="requires",
        confidence=0.9,
        kind=EvidenceKind.DECLARED if constraint.strip() else EvidenceKind.UNKNOWN,
    )


def _parse_setup_py(
    text: str | None,
    evidence: list[Evidence],
    unknowns: list[str],
) -> tuple[str | None, Requirement | None]:
    if text is None:
        return None, None
    try:
        tree = ast.parse(text, filename="setup.py", mode="exec")
    except SyntaxError:
        reason = "setup.py could not be interpreted by the static AST parser"
        evidence.append(Evidence(EvidenceKind.UNKNOWN, "setup.py", reason, "static Python AST parser"))
        unknowns.append(reason)
        return None, None
    identity: str | None = None
    constraint: str | None = None
    python_requires_seen = False
    for statement in tree.body:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            continue
        node = statement.value
        is_setup = (
            isinstance(node.func, ast.Name)
            and node.func.id == "setup"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "setup"
        )
        if not is_setup:
            continue
        for keyword in node.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                identity = keyword.value.value
            if keyword.arg == "python_requires":
                python_requires_seen = True
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    constraint = keyword.value.value
        break
    if not python_requires_seen:
        return identity, None
    if constraint is None:
        reason = "setup.py python_requires is not a literal string and was not executed"
        evidence.append(Evidence(EvidenceKind.UNKNOWN, "setup.py", reason, "static Python AST parser"))
        unknowns.append(reason)
    return identity, _runtime_requirement(
        constraint=constraint,
        source="setup.py",
        field="setup.python_requires",
        relation="requires",
        confidence=0.8 if constraint else 0.3,
        kind=EvidenceKind.DECLARED if constraint else EvidenceKind.UNKNOWN,
    )


def _package_requirements(text: str, source: str, optional: bool) -> list[Requirement]:
    items: list[Requirement] = []
    relevance = Relevance.OPTIONAL if optional else Relevance.REQUIRED
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(("-", "http:", "https:", "git+")):
            continue
        match = PACKAGE_REQUIREMENT.match(line)
        if not match:
            continue
        package = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        constraint = match.group(2).split(";", 1)[0].strip() or "available"
        item_evidence = Evidence(
            EvidenceKind.DECLARED,
            source,
            line,
            f"static requirements line {number}",
        )
        items.append(
            Requirement.create(
                capability=f"python.package:{package}",
                constraint=constraint,
                source=source,
                field=f"line:{number}",
                relevance=relevance,
                evidence_purpose="dependency_requirement",
                confidence=1.0,
                evidence=[item_evidence],
            )
        )
    return items


def inspect_project(
    target: str | Path,
    *,
    max_manifest_bytes: int = MAX_MANIFEST_BYTES,
) -> ProjectDNA:
    root = Path(target).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"Project root is not a directory: {root}")

    evidence: list[Evidence] = []
    unknowns: list[str] = []
    manifests: list[ManifestRecord] = []
    required: list[Requirement] = []
    optional: list[Requirement] = []
    identity: str | None = None
    entrypoints: list[str] = []
    build_systems: list[str] = []

    fixed = [
        root / "pyproject.toml",
        root / ".python-version",
        root / "uv.lock",
        root / "setup.cfg",
        root / "setup.py",
    ]
    requirement_files = sorted(root.glob("requirements*.txt"), key=lambda item: item.name.lower())
    requirements_directory = root / "requirements"
    if requirements_directory.is_symlink():
        reason = "requirements is a symbolic link and was not traversed"
        evidence.append(Evidence(EvidenceKind.UNKNOWN, "requirements", reason, "project manifest discovery"))
        unknowns.append(reason)
    elif requirements_directory.is_dir():
        requirement_files.extend(
            sorted(requirements_directory.glob("*.txt"), key=lambda item: item.name.lower())
        )

    texts: dict[str, str | None] = {}
    for path in [*fixed, *requirement_files]:
        if not path.exists() and not path.is_symlink():
            continue
        text, manifest = _read_manifest(path, root, evidence, unknowns, max_manifest_bytes)
        source = _relative(path, root)
        texts[source] = text
        if manifest:
            manifests.append(manifest)

    if "pyproject.toml" in texts:
        identity, runtime, entrypoints, build_systems = _parse_pyproject(
            texts["pyproject.toml"], evidence, unknowns
        )
        required.append(runtime)
        evidence.extend(runtime.evidence)
    if ".python-version" in texts:
        selected = _parse_python_version(texts[".python-version"])
        if selected:
            required.append(selected)
            evidence.extend(selected.evidence)
    if "uv.lock" in texts:
        locked = _parse_uv_lock(texts["uv.lock"], evidence, unknowns)
        if locked:
            required.append(locked)
            evidence.extend(locked.evidence)
    if "setup.cfg" in texts:
        setup_identity, configured = _parse_setup_cfg(
            texts["setup.cfg"], evidence, unknowns
        )
        identity = identity or setup_identity
        if configured:
            required.append(configured)
            evidence.extend(configured.evidence)
            if "setuptools" not in build_systems:
                build_systems.append("setuptools")
    if "setup.py" in texts:
        setup_identity, scripted = _parse_setup_py(
            texts["setup.py"], evidence, unknowns
        )
        identity = identity or setup_identity
        if scripted:
            required.append(scripted)
            evidence.extend(scripted.evidence)
            if "setuptools" not in build_systems:
                build_systems.append("setuptools")

    for source in sorted(key for key in texts if key.lower().endswith(".txt")):
        text = texts[source]
        if text is None:
            continue
        is_optional = source != "requirements.txt"
        parsed = _package_requirements(text, source, is_optional)
        (optional if is_optional else required).extend(parsed)
        for item in parsed:
            evidence.extend(item.evidence)

    authority = {
        ("pyproject.toml", "project.requires-python"): 0,
        ("uv.lock", "requires-python"): 1,
        ("setup.cfg", "options.python_requires"): 2,
        ("setup.py", "setup.python_requires"): 3,
    }
    runtime_requirements = [
        item
        for item in required
        if item.capability == "python.runtime" and item.relation == "requires"
    ]
    if runtime_requirements:
        primary_runtime = min(
            runtime_requirements,
            key=lambda item: authority.get((item.source, item.field), 99),
        )
        for item in runtime_requirements:
            item.relevance = (
                Relevance.REQUIRED
                if item.id == primary_runtime.id
                else Relevance.UNKNOWN_RELEVANCE
            )
            item.is_effective = item.id == primary_runtime.id
        primary_runtime.effective_specifier = primary_runtime.constraint
        for item in required:
            if item.capability != "python.runtime" or item.id == primary_runtime.id:
                continue
            if item.relation == "selects":
                version = exact_version_from_constraint(item.constraint)
                comparison = (
                    python_version_satisfies(version, primary_runtime.constraint)
                    if version
                    else None
                )
            elif item.relation == "requires":
                comparison = python_constraints_overlap(
                    primary_runtime.constraint, item.constraint
                )
            else:
                comparison = None
            if comparison is False:
                primary_runtime.conflict_ids.append(
                    "ARX-PROJECT-REQUIREMENT-CONFLICT"
                )
                primary_runtime.interpretation_state = InterpretationState.CONFLICT
            elif comparison is None:
                reason = (
                    f"{item.source} {item.field} could not be safely compared with "
                    f"{primary_runtime.source} {primary_runtime.field}."
                )
                item.interpretation_state = InterpretationState.UNKNOWN
                item.unknowns.append(reason)
        # The authoritative Requirement is the capability-level conclusion. It
        # retains typed provenance from every Python runtime declaration without
        # erasing the individual source claims used for conflict analysis.
        semantic_evidence = []
        seen_evidence: set[str] = set()
        for item in required:
            if item.capability != "python.runtime":
                continue
            for item_evidence in item.evidence:
                identifier = evidence_id(item_evidence)
                if identifier not in seen_evidence:
                    semantic_evidence.append(item_evidence)
                    seen_evidence.add(identifier)
        primary_runtime.evidence = semantic_evidence

    python_detected = bool(manifests)
    if not python_detected:
        reason = "No supported Python project manifests were found"
        evidence.append(
            Evidence(EvidenceKind.UNKNOWN, "project root", reason, "project manifest discovery", 1.0)
        )
        unknowns.append(reason)
    confidence = 1.0 if not unknowns else max(0.2, 1.0 - 0.15 * len(unknowns))
    return ProjectDNA.create(
        root=root,
        identity=identity or root.name,
        languages=["Python"] if python_detected else [],
        ecosystems=["PyPI"] if python_detected else [],
        build_systems=build_systems,
        manifests=manifests,
        requirements=required,
        optional_requirements=optional,
        entrypoint_hints=entrypoints,
        evidence=evidence,
        confidence=confidence,
        unknowns=unknowns,
    )

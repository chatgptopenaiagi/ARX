from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

from arx.core.models import Evidence, EvidenceKind

from .models import ManifestRecord, ProjectDNA, Relevance, Requirement


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
) -> Requirement:
    value = constraint if constraint is not None else "not declared or unavailable"
    item = Evidence(kind, source, value, f"static field {field}", confidence)
    return Requirement.create(
        capability="python.runtime",
        constraint=constraint,
        source=source,
        field=field,
        relevance=Relevance.REQUIRED,
        relation=relation,
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
        )
    return _runtime_requirement(
        constraint=f"=={selected}",
        source=".python-version",
        field="selected-version",
        relation="selects",
        confidence=1.0,
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
        )
    constraint = data.get("requires-python")
    return _runtime_requirement(
        constraint=str(constraint) if constraint is not None else None,
        source="uv.lock",
        field="requires-python",
        relation="requires",
        confidence=1.0 if constraint is not None else 0.5,
        kind=EvidenceKind.DECLARED if constraint is not None else EvidenceKind.UNKNOWN,
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

    fixed = [root / "pyproject.toml", root / ".python-version", root / "uv.lock"]
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

    for source in sorted(key for key in texts if key.lower().endswith(".txt")):
        text = texts[source]
        if text is None:
            continue
        is_optional = source != "requirements.txt"
        parsed = _package_requirements(text, source, is_optional)
        (optional if is_optional else required).extend(parsed)
        for item in parsed:
            evidence.extend(item.evidence)

    python_detected = bool(manifests)
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

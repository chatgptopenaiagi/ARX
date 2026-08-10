from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from arx.core.models import Evidence, EvidenceKind

from .models import (
    ExecutionContext,
    ExecutionResolution,
    Provider,
    ProviderGraph,
    ProviderHealth,
    ProviderKind,
    ProviderScope,
    stable_id,
)


SUPPORTED_PYTHON_COMMANDS = {"python", "python3", "py"}


def _normalized_path(value: str) -> str:
    return os.path.normcase(str(Path(value).expanduser().resolve(strict=False)))


def infer_provider_kind(path: str) -> ProviderKind:
    lowered = path.replace("/", "\\").lower()
    if "\\microsoft\\windowsapps\\" in lowered:
        return ProviderKind.WINDOWSAPPS_ALIAS
    if "\\.venv\\" in lowered or "\\venv\\" in lowered or "\\env\\scripts\\python" in lowered:
        return ProviderKind.VIRTUAL_ENVIRONMENT
    if "\\uv-python\\" in lowered or "\\uv\\python\\" in lowered:
        return ProviderKind.UV_MANAGED
    if "\\anaconda" in lowered or "\\miniconda" in lowered or "\\conda\\" in lowered:
        return ProviderKind.CONDA
    if Path(path).name.lower() in {"python", "python.exe"}:
        return ProviderKind.CPYTHON
    return ProviderKind.UNKNOWN


def infer_provider_scope(path: str) -> ProviderScope:
    normalized = _normalized_path(path)
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        profile = _normalized_path(user_profile)
        try:
            if Path(normalized).is_relative_to(profile):
                return ProviderScope.USER
        except (OSError, ValueError):
            pass
    lowered = normalized.replace("/", "\\").lower()
    if lowered.startswith(("c:\\program files\\", "c:\\windows\\")):
        return ProviderScope.MACHINE
    return ProviderScope.UNKNOWN


def make_provider(
    *,
    path: str,
    version: str | None,
    kind: ProviderKind | None = None,
    discovery_method: str,
    healthy: bool | None,
    architecture: str | None = None,
    exists: bool = True,
    health_status: ProviderHealth | str | None = None,
    health_reason: str | None = None,
    scope: ProviderScope | str | None = None,
    confidence: float = 1.0,
    evidence: list[Evidence] | None = None,
) -> Provider:
    normalized = _normalized_path(path)
    provider_kind = kind or infer_provider_kind(normalized)
    provider_scope = ProviderScope(scope) if scope is not None else infer_provider_scope(normalized)
    if health_status is None:
        status = (
            ProviderHealth.HEALTHY
            if healthy is True
            else ProviderHealth.UNHEALTHY
            if healthy is False
            else ProviderHealth.UNKNOWN
        )
    else:
        status = ProviderHealth(health_status)
    usable = (
        True
        if status is ProviderHealth.HEALTHY
        else False
        if status in {ProviderHealth.DEGRADED, ProviderHealth.UNHEALTHY}
        else None
    )
    identity = stable_id("executable", normalized)
    provider_id = stable_id(
        "provider",
        normalized,
        identity,
        version,
        provider_kind.value,
        architecture,
        provider_scope.value,
        discovery_method,
    )
    return Provider(
        id=provider_id,
        capability="python.runtime",
        path=str(Path(path).expanduser().resolve(strict=False)),
        executable_identity=identity,
        version=version,
        kind=provider_kind,
        discovery_method=discovery_method,
        healthy=usable,
        confidence=confidence,
        evidence=list(evidence or []),
        exists=exists,
        health_status=status,
        health_reason=health_reason,
        architecture=architecture,
        scope=provider_scope,
    )


def providers_from_machine(machine: Mapping[str, object]) -> list[Provider]:
    providers: list[Provider] = []
    for item in machine.get("python_installations", []) or []:
        if not isinstance(item, Mapping) or not item.get("path"):
            continue
        path = str(item["path"])
        evidence = [entry for entry in item.get("evidence", []) if isinstance(entry, Evidence)]
        if not evidence:
            evidence = [
                Evidence(
                    EvidenceKind.OBSERVED,
                    path,
                    "healthy" if item.get("healthy") else "unhealthy or unverified",
                    str(item.get("health_probe") or "Machine DNA Python discovery"),
                    1.0 if item.get("healthy") else 0.7,
                    str(item.get("error")) if item.get("error") else None,
                )
            ]
        providers.append(
            make_provider(
                path=path,
                version=str(item["version"]) if item.get("version") is not None else None,
                architecture=(
                    str(item.get("architecture_bits") or item.get("architecture"))
                    if item.get("architecture_bits") or item.get("architecture")
                    else None
                ),
                exists=item.get("exists") is not False,
                health_status=(
                    str(item["health_status"])
                    if item.get("health_status") is not None
                    else None
                ),
                health_reason=(
                    str(item.get("health_reason") or item.get("error"))
                    if item.get("health_reason") or item.get("error")
                    else None
                ),
                scope=str(item["scope"]) if item.get("scope") is not None else None,
                discovery_method="machine_dna.python_installations",
                healthy=item.get("healthy") if isinstance(item.get("healthy"), bool) else None,
                confidence=1.0 if item.get("healthy") else 0.7,
                evidence=evidence,
            )
        )
    return providers


def provider_graph_from_machine(machine: Mapping[str, object]) -> ProviderGraph:
    return ProviderGraph.create(providers_from_machine(machine))


def _powershell_paths(
    context: ExecutionContext,
    environment: Mapping[str, str],
    command: str,
    timeout: float,
) -> list[str]:
    executable = shutil.which("pwsh", path=environment.get("PATH")) or shutil.which(
        "powershell", path=environment.get("PATH")
    )
    if not executable:
        return []
    script = (
        f"Get-Command -Name {command} -All -ErrorAction SilentlyContinue | "
        "Where-Object CommandType -eq Application | Select-Object -ExpandProperty Source"
    )
    try:
        completed = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-Command", script],
            cwd=context.working_directory,
            env=dict(environment),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _where_paths(
    context: ExecutionContext,
    environment: Mapping[str, str],
    command: str,
    timeout: float,
) -> list[str]:
    executable = shutil.which("where.exe", path=environment.get("PATH"))
    if not executable:
        return []
    try:
        completed = subprocess.run(
            [executable, command],
            cwd=context.working_directory,
            env=dict(environment),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _unique_paths(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        if not path:
            continue
        normalized = _normalized_path(path)
        if normalized not in seen:
            seen.add(normalized)
            result.append(path)
    return result


def resolve_python(
    providers: list[Provider],
    context: ExecutionContext,
    *,
    command_paths: list[str] | None = None,
    environment: Mapping[str, str] | None = None,
    timeout: float = 5.0,
) -> ExecutionResolution:
    """Resolve a supported Python command without invoking a discovered interpreter."""
    env = dict(os.environ if environment is None else environment)
    command = context.command.lower()
    if command not in SUPPORTED_PYTHON_COMMANDS:
        raise ValueError(f"Unsupported Python command: {context.command}")
    methods: list[str] = []
    if command_paths is None:
        paths: list[str] = []
        if os.name == "nt" and context.shell.lower() in {"powershell", "pwsh"}:
            powershell = _powershell_paths(context, env, command, timeout)
            paths.extend(powershell)
            if powershell:
                methods.append("PowerShell Get-Command -All")
            where = _where_paths(context, env, command, timeout)
            paths.extend(where)
            if where:
                methods.append("where.exe")
        first = shutil.which(command, path=env.get("PATH"))
        if first:
            paths.append(first)
            methods.append("shutil.which")
        paths = _unique_paths(paths)
    else:
        paths = _unique_paths(command_paths)
        methods.append("provided deterministic resolution evidence")

    by_path = {_normalized_path(item.path): item for item in providers}
    candidates = [by_path[_normalized_path(path)] for path in paths if _normalized_path(path) in by_path]
    resolved = candidates[0] if candidates else None
    evidence = [
        Evidence(
            EvidenceKind.OBSERVED if paths else EvidenceKind.UNKNOWN,
            "execution context",
            paths[0] if paths else f"{command} command did not resolve",
            ", ".join(methods) if methods else "fixed command resolution",
            1.0 if resolved else 0.5,
            None if resolved else "Resolved path was absent or not mapped to a discovered provider",
        )
    ]
    return ExecutionResolution.create(
        command=command,
        context=context,
        resolved_path=paths[0] if paths else None,
        resolved_provider_id=resolved.id if resolved else None,
        candidate_provider_ids=[item.id for item in candidates],
        method=", ".join(methods) if methods else "unresolved",
        confidence=1.0 if resolved else 0.5 if paths else 0.0,
        evidence=evidence,
    )

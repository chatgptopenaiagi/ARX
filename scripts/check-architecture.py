"""Enforce the directed ARX layer graph and reject import cycles."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ARX_LAYERS = (
    "core",
    "machine",
    "software",
    "project",
    "exporters",
    "advisory",
    "local_ai",
    "cli",
    "desktop",
)
ALLOWED_IMPORTS = {
    "core": frozenset(),
    "machine": frozenset({"core"}),
    "software": frozenset({"core"}),
    "project": frozenset({"core", "machine"}),
    "exporters": frozenset({"core", "project"}),
    "advisory": frozenset({"core"}),
    "local_ai": frozenset({"advisory"}),
    "cli": frozenset({"core", "machine", "software", "project", "exporters"}),
    "desktop": frozenset(
        {"core", "machine", "software", "project", "exporters", "advisory", "local_ai", "cli"}
    ),
}


@dataclass(frozen=True, order=True)
class ImportViolation:
    source_layer: str
    target_layer: str
    path: str
    line: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: forbidden ARX import {self.source_layer} -> {self.target_layer}"


@dataclass(frozen=True)
class ArchitectureReport:
    edges: frozenset[tuple[str, str]]
    violations: tuple[ImportViolation, ...]
    cycles: tuple[tuple[str, ...], ...]

    @property
    def passed(self) -> bool:
        return not self.violations and not self.cycles


def _source_layer(relative: Path) -> str | None:
    if len(relative.parts) > 1 and relative.parts[0] in ARX_LAYERS:
        return relative.parts[0]
    if relative.as_posix() == "cli.py":
        return "cli"
    return None


def _target_layer(module: str | None) -> str | None:
    if not module:
        return None
    parts = module.split(".")
    if parts[0] != "arx" or len(parts) < 2:
        return None
    return parts[1] if parts[1] in ARX_LAYERS else None


def _imports(tree: ast.AST) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            found.append((node.module or "", node.lineno))
    return found


def _cycles(edges: set[tuple[str, str]]) -> tuple[tuple[str, ...], ...]:
    graph = {layer: set() for layer in ARX_LAYERS}
    for source, target in edges:
        graph[source].add(target)
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node) :] + [node]
            body = cycle[:-1]
            rotations = [tuple(body[index:] + body[:index] + [body[index]]) for index in range(len(body))]
            cycles.add(min(rotations))
            return
        for target in sorted(graph[node]):
            visit(target, [*path, node])

    for layer in ARX_LAYERS:
        visit(layer, [])
    return tuple(sorted(cycles))


def analyze_source_tree(arx_root: Path) -> ArchitectureReport:
    root = arx_root.resolve()
    edges: set[tuple[str, str]] = set()
    violations: list[ImportViolation] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        source = _source_layer(relative)
        if source is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module, line in _imports(tree):
            target = _target_layer(module)
            if target is None or target == source:
                continue
            edges.add((source, target))
            if target not in ALLOWED_IMPORTS[source]:
                violations.append(ImportViolation(source, target, relative.as_posix(), line))
    return ArchitectureReport(frozenset(edges), tuple(sorted(violations)), _cycles(edges))


def main(argv: list[str] | None = None) -> int:
    arguments = argv or sys.argv[1:]
    arx_root = Path(arguments[0]) if arguments else Path(__file__).resolve().parents[1] / "src" / "arx"
    report = analyze_source_tree(arx_root)
    for source, target in sorted(report.edges):
        print(f"{source} -> {target}")
    for violation in report.violations:
        print(violation, file=sys.stderr)
    for cycle in report.cycles:
        print(f"ARX import cycle: {' -> '.join(cycle)}", file=sys.stderr)
    if report.passed:
        print("ARX dependency boundaries: PASS")
        return 0
    print("ARX dependency boundaries: FAIL", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

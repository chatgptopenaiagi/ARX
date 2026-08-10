from __future__ import annotations

import re


VERSION = re.compile(
    r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:(a|alpha|b|beta|rc)(\d+)?)?(?:[-+._].*)?\s*$",
    re.IGNORECASE,
)
SPECIFIER = re.compile(r"^\s*(<=|>=|==|!=|<|>|=)?\s*(.+?)\s*$")


def parse_python_version(value: str | None) -> tuple[int, int, int, int, int] | None:
    if not value:
        return None
    match = VERSION.fullmatch(str(value))
    if not match:
        return None
    stage = (match.group(4) or "").lower()
    stage_rank = {"a": -3, "alpha": -3, "b": -2, "beta": -2, "rc": -1, "": 0}[stage]
    return (
        int(match.group(1)),
        int(match.group(2) or 0),
        int(match.group(3) or 0),
        stage_rank,
        int(match.group(5) or 0),
    )


def python_version_satisfies(version: str | None, constraint: str | None) -> bool | None:
    """Evaluate a conservative PEP 440 subset and preserve unsupported input as unknown."""
    if constraint in (None, "", "available"):
        return True if constraint == "available" and version else None
    observed = parse_python_version(version)
    if observed is None:
        return None
    parts = [part.strip() for part in str(constraint).split(",") if part.strip()]
    if not parts:
        return None
    # ARX implements only a bounded PEP 440 subset. A prerelease has additional
    # admission rules beyond tuple ordering, so abstain unless the declaration
    # explicitly contains a prerelease boundary.
    if observed[3] < 0:
        explicit_prerelease = False
        for part in parts:
            match = SPECIFIER.fullmatch(part)
            if match:
                expected = parse_python_version(match.group(2))
                explicit_prerelease = explicit_prerelease or (
                    expected is not None and expected[3] < 0
                )
        if not explicit_prerelease:
            return None
    for part in parts:
        match = SPECIFIER.fullmatch(part)
        if not match or part.startswith(("~=", "===", "^")):
            return None
        operator = match.group(1) or "=="
        expected = parse_python_version(match.group(2))
        if expected is None:
            return None
        comparison = {
            "<": observed < expected,
            "<=": observed <= expected,
            ">": observed > expected,
            ">=": observed >= expected,
            "=": observed == expected,
            "==": observed == expected,
            "!=": observed != expected,
        }[operator]
        if not comparison:
            return False
    return True


def exact_version_from_constraint(constraint: str | None) -> str | None:
    if not constraint:
        return None
    match = re.fullmatch(r"\s*(?:==|=)?\s*(\d+(?:\.\d+){0,2}(?:(?:a|b|rc)\d+)?)\s*", constraint)
    return match.group(1) if match else None


def python_constraints_overlap(left: str | None, right: str | None) -> bool | None:
    """Return whether two supported constraint ranges overlap, without inventing a merge."""
    clauses: list[tuple[str, tuple[int, int, int, int, int]]] = []
    for constraint in (left, right):
        if not constraint:
            return None
        parts = [part.strip() for part in constraint.split(",") if part.strip()]
        if not parts:
            return None
        for part in parts:
            match = SPECIFIER.fullmatch(part)
            if not match or part.startswith(("~=", "===", "^")):
                return None
            version = parse_python_version(match.group(2))
            if version is None:
                return None
            clauses.append((match.group(1) or "==", version))

    equal = {version for operator, version in clauses if operator in {"=", "=="}}
    excluded = {version for operator, version in clauses if operator == "!="}
    if len(equal) > 1:
        return False
    if equal:
        candidate = next(iter(equal))
        if candidate in excluded:
            return False
        comparisons = {
            "<": lambda observed, expected: observed < expected,
            "<=": lambda observed, expected: observed <= expected,
            ">": lambda observed, expected: observed > expected,
            ">=": lambda observed, expected: observed >= expected,
            "=": lambda observed, expected: observed == expected,
            "==": lambda observed, expected: observed == expected,
            "!=": lambda observed, expected: observed != expected,
        }
        return all(comparisons[operator](candidate, expected) for operator, expected in clauses)

    lower: tuple[tuple[int, int, int, int, int], bool] | None = None
    upper: tuple[tuple[int, int, int, int, int], bool] | None = None
    for operator, version in clauses:
        if operator in {">", ">="}:
            inclusive = operator == ">="
            if lower is None or version > lower[0] or (version == lower[0] and not inclusive):
                lower = (version, inclusive)
        elif operator in {"<", "<="}:
            inclusive = operator == "<="
            if upper is None or version < upper[0] or (version == upper[0] and not inclusive):
                upper = (version, inclusive)
    if lower is None or upper is None:
        return True
    if lower[0] < upper[0]:
        return True
    if lower[0] > upper[0]:
        return False
    return lower[1] and upper[1] and lower[0] not in excluded


def python_selection_satisfies(version: str | None, selection: str | None) -> bool | None:
    """Match project selection intent, allowing major/minor family pins such as 3.12."""
    if not version or not selection:
        return None
    selected = re.fullmatch(
        r"\s*(?:==|=)?\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?\s*", selection
    )
    observed = parse_python_version(version)
    if selected is None or observed is None:
        return None
    expected_parts = [
        int(part)
        for part in selected.groups()
        if part is not None
    ]
    return observed[: len(expected_parts)] == tuple(expected_parts)

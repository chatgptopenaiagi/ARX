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

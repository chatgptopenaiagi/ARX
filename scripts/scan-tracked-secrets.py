"""Fail closed on credential-shaped material in Git-tracked files.

Only filenames and finding categories are reported. Matching bytes are never
printed, which keeps the scanner safe even when it finds real secret material.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    ("OpenAI API credential", re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_.-]{16,}")),
    ("GitHub credential", re.compile(rb"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}")),
    ("private key block", re.compile(b"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
FORBIDDEN_NAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "external-transmissions.jsonl",
    "openai-api-key" + "2.txt",
}
FORBIDDEN_SUFFIXES = {".dpapi", ".key", ".pem", ".pfx", ".p12"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [ROOT / item.decode("utf-8", errors="surrogateescape") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[tuple[str, str]] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        folded_name = path.name.casefold()
        if folded_name in FORBIDDEN_NAMES or path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            findings.append((relative, "forbidden secret-bearing filename"))
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            findings.append((relative, "unreadable tracked file"))
            continue
        for category, pattern in PATTERNS:
            if pattern.search(payload):
                findings.append((relative, category))

    if findings:
        for relative, category in findings:
            print(f"{relative}: {category}", file=sys.stderr)
        print(f"Tracked-file secret scan: FAIL ({len(findings)} finding(s); secret values suppressed)", file=sys.stderr)
        return 1
    print(f"Tracked-file secret scan: PASS ({len(tracked_files())} tracked files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

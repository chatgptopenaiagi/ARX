"""Run each Tk-backed pytest node in a fresh interpreter on Windows CI.

Tk interpreters created in the same thread share an event queue.  ARX creates
one root in production, so this runner gives each GUI test the same lifecycle
instead of accumulating test-only roots inside one Python process.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI_MODULES = (
    "tests/test_desktop.py",
    "tests/test_desktop_advisory.py",
    "tests/test_desktop_provider_settings.py",
    "tests/test_desktop_ux.py",
)


def _run(arguments: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=capture,
        shell=False,
    )


def main() -> int:
    collection = _run(["--collect-only", "-q", *GUI_MODULES], capture=True)
    if collection.returncode != 0:
        sys.stdout.write(collection.stdout)
        sys.stderr.write(collection.stderr)
        return collection.returncode
    nodes = [line.strip() for line in collection.stdout.splitlines() if "::" in line]
    if not nodes:
        print("No GUI tests were collected.", file=sys.stderr)
        return 2
    for index, node in enumerate(nodes, start=1):
        print(f"[{index}/{len(nodes)}] {node}", flush=True)
        completed = _run(["-q", node])
        if completed.returncode != 0:
            return completed.returncode
    print(f"{len(nodes)} isolated GUI tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

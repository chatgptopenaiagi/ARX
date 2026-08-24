"""Write deterministic SHA-256 lines for every top-level public file except the manifest."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.release_root.resolve()
    output = arguments.output.resolve()
    if not root.is_dir():
        raise SystemExit("Release root does not exist.")
    files = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.name != "SHA256SUMS.txt" and path.resolve() != output
        ),
        key=lambda path: path.name,
    )
    if not files:
        raise SystemExit("No public files were found for checksum generation.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{digest(path)}  {path.name}\n" for path in files),
        encoding="utf-8",
        newline="\n",
    )
    print(f"Public checksums: CREATED ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

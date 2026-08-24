"""Write a path-free release build-toolchain identity record."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import struct
from pathlib import Path

PACKAGES = (
    "build",
    "check-wheel-contents",
    "pip",
    "pyinstaller",
    "setuptools",
    "twine",
    "wheel",
)


def build_record(arguments: argparse.Namespace) -> dict:
    return {
        "schema_version": 1,
        "record_type": "arx_release_build_environment",
        "builder_label": arguments.builder_label,
        "source_commit": arguments.source_commit,
        "source_date_epoch": arguments.source_date_epoch,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "architecture_bits": struct.calcsize("P") * 8,
        },
        "tools": {
            name: importlib.metadata.version(name)
            for name in PACKAGES
        }
        | {"inno_setup": arguments.inno_setup_version},
        "controls": {
            "python_hash_seed": "0",
            "timezone": "UTC",
            "source_date_epoch_origin": "source commit timestamp",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--builder-label", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-date-epoch", required=True, type=int)
    parser.add_argument("--inno-setup-version", required=True)
    arguments = parser.parse_args()
    if len(arguments.source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in arguments.source_commit
    ):
        raise SystemExit("Source commit must be a lowercase 40-character SHA.")
    record = build_record(arguments)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Release build environment: RECORDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

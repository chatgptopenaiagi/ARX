"""Compare two independently built ARX release trees without overstating equivalence."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
import zipfile
from pathlib import Path

BIT_FOR_BIT = "BIT_FOR_BIT_REPRODUCIBLE"
STRUCTURAL = "STRUCTURALLY_EQUIVALENT"
NOT_REPRODUCIBLE = "NOT_REPRODUCIBLE"
UNRESOLVED = "UNRESOLVED"
MANIFEST_LINE = re.compile(r"([0-9a-f]{64})  ([^/\\]+)\Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _zip_snapshot(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: hashlib.sha256(archive.read(info)).hexdigest()
            for info in archive.infolist()
            if not info.is_dir()
        }


def _tar_snapshot(path: Path) -> dict[str, dict]:
    snapshot: dict[str, dict] = {}
    with gzip.open(path, "rb") as compressed:
        payload = compressed.read()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive.getmembers():
            entry = {
                "type": member.type.decode("ascii", errors="replace")
                if isinstance(member.type, bytes)
                else str(member.type),
                "mode": member.mode,
                "linkname": member.linkname,
                "size": member.size,
                "sha256": None,
            }
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError(f"Unable to read sdist member: {member.name}")
                entry["sha256"] = hashlib.sha256(stream.read()).hexdigest()
            snapshot[member.name] = entry
    return snapshot


def _parse_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = MANIFEST_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"Malformed checksum manifest: {path.name}")
        digest, name = match.groups()
        if name in result:
            raise ValueError(f"Duplicate checksum manifest name: {name}")
        result[name] = digest
    return result


def _validate_manifest(root: Path, manifest: dict[str, str]) -> None:
    for name, expected in manifest.items():
        candidate = root / name
        if not candidate.is_file() or _sha256(candidate) != expected:
            raise ValueError(f"Checksum manifest does not bind its local artifact: {name}")


def _compare_file(
    first: Path,
    second: Path,
    *,
    structural_reader=None,
    differing_bytes_classification: str = NOT_REPRODUCIBLE,
) -> dict:
    if not first.is_file() or not second.is_file():
        return {
            "classification": UNRESOLVED,
            "sha256_a": _sha256(first) if first.is_file() else None,
            "sha256_b": _sha256(second) if second.is_file() else None,
            "size_a": first.stat().st_size if first.is_file() else None,
            "size_b": second.stat().st_size if second.is_file() else None,
            "basis": "One or both required files were absent.",
        }
    hash_a = _sha256(first)
    hash_b = _sha256(second)
    common = {
        "sha256_a": hash_a,
        "sha256_b": hash_b,
        "size_a": first.stat().st_size,
        "size_b": second.stat().st_size,
    }
    if hash_a == hash_b:
        return common | {
            "classification": BIT_FOR_BIT,
            "basis": "Raw SHA-256 and byte length are identical.",
        }
    if structural_reader is not None and structural_reader(first) == structural_reader(second):
        return common | {
            "classification": STRUCTURAL,
            "basis": "Member names, bounded metadata, and uncompressed member bytes are identical; container bytes differ.",
        }
    return common | {
        "classification": differing_bytes_classification,
        "basis": "Raw bytes differ and the permitted structural comparison did not establish equivalence.",
    }


def _safe_environment(path: Path) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "record_type",
        "builder_label",
        "source_commit",
        "source_date_epoch",
        "platform",
        "python",
        "tools",
        "controls",
    }
    if set(record) != required or record["record_type"] != "arx_release_build_environment":
        raise ValueError("Build environment record has an unexpected shape.")
    serialized = json.dumps(record)
    if re.search(r"(?i)(?:[A-Z]:[\\/]|/(?:home|Users)/)", serialized):
        raise ValueError("Build environment record contains an absolute local path.")
    return record


def compare(arguments: argparse.Namespace) -> dict:
    root_a = arguments.build_a.resolve()
    root_b = arguments.build_b.resolve()
    environment_a = _safe_environment(arguments.environment_a)
    environment_b = _safe_environment(arguments.environment_b)
    comparison_fields = ("source_commit", "source_date_epoch", "platform", "python", "tools", "controls")
    mismatches = [field for field in comparison_fields if environment_a[field] != environment_b[field]]
    if mismatches:
        raise ValueError("Build environments differ in: " + ", ".join(mismatches))
    if environment_a["source_commit"] != arguments.source_commit:
        raise ValueError("Build environment source commit does not match the requested commit.")

    version = arguments.version
    artifact = arguments.artifact_version
    names = {
        "wheel": f"arx_prescanner-{version}-py3-none-any.whl",
        "sdist": f"arx_prescanner-{version}.tar.gz",
        "portable_zip": f"ARX-Desktop-win-x64-v{artifact}.zip",
        "installer": f"ARX-Desktop-Setup-win-x64-v{artifact}.exe",
        "sha256sums": "SHA256SUMS.txt",
    }
    results = {
        "wheel": _compare_file(root_a / names["wheel"], root_b / names["wheel"], structural_reader=_zip_snapshot),
        "sdist": _compare_file(root_a / names["sdist"], root_b / names["sdist"], structural_reader=_tar_snapshot),
        "portable_zip": _compare_file(
            root_a / names["portable_zip"], root_b / names["portable_zip"], structural_reader=_zip_snapshot
        ),
        "arx_exe": _compare_file(
            root_a / "ARX-Desktop-win-x64" / "ARX.exe",
            root_b / "ARX-Desktop-win-x64" / "ARX.exe",
        ),
        "installer": _compare_file(root_a / names["installer"], root_b / names["installer"]),
    }
    manifest_a = _parse_manifest(root_a / names["sha256sums"])
    manifest_b = _parse_manifest(root_b / names["sha256sums"])
    _validate_manifest(root_a, manifest_a)
    _validate_manifest(root_b, manifest_b)
    results["sha256sums"] = _compare_file(
        root_a / names["sha256sums"],
        root_b / names["sha256sums"],
        structural_reader=lambda _path: sorted(manifest_a) if _path == root_a / names["sha256sums"] else sorted(manifest_b),
    )
    return {
        "schema_version": 1,
        "record_type": "arx_release_reproducibility",
        "release": {
            "version": version,
            "artifact_version": artifact,
            "source_commit": arguments.source_commit,
            "source_date_epoch": environment_a["source_date_epoch"],
        },
        "equal_toolchain": True,
        "build_environments": [environment_a, environment_b],
        "artifacts": results,
        "classification_policy": {
            "byte_identity": "Raw SHA-256 equality is required for BIT_FOR_BIT_REPRODUCIBLE.",
            "archives": "Structural equivalence requires identical names, bounded metadata, and uncompressed member bytes.",
            "pe_and_installer": "Differing PE or installer bytes are NOT_REPRODUCIBLE; the comparator does not rewrite or normalize binary metadata.",
            "checksums": "Differing manifests may be structurally equivalent only when both bind the same filename set to their own exact artifacts.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-a", type=Path, required=True)
    parser.add_argument("--build-b", type=Path, required=True)
    parser.add_argument("--environment-a", type=Path, required=True)
    parser.add_argument("--environment-b", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--artifact-version", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    record = compare(arguments)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Release reproducibility comparison: COMPLETE")
    for name, result in record["artifacts"].items():
        print(f"{name}: {result['classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

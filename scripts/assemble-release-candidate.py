"""Assemble the bounded public ARX release-security and provenance bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import mimetypes
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECURITY_SCHEMA = ROOT / "security" / "release-record" / "release-security-record.schema.json"
PROVENANCE_SCHEMA = ROOT / "security" / "provenance" / "provenance-bundle.schema.json"
VALIDATOR = ROOT / "scripts" / "validate-security-record.py"
VERIFIER = ROOT / "scripts" / "verify-release-assets.py"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path.name} must contain a JSON object.")
    return value


def _copy(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Required release input is missing: {source.name}")
    if source.resolve() == target.resolve():
        return
    shutil.copyfile(source, target)


def _subject(path: Path, provenance: str) -> dict:
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.name.endswith(".cdx.json"):
        media_type = "application/vnd.cyclonedx+json"
    return {
        "name": path.name,
        "sha256": _sha256(path),
        "size": path.stat().st_size,
        "media_type": media_type,
        "provenance": provenance,
    }


def _zip_info(name: str, source_date_epoch: int) -> zipfile.ZipInfo:
    moment = datetime.fromtimestamp(source_date_epoch, tz=timezone.utc)
    if not 1980 <= moment.year <= 2107:
        raise ValueError("SOURCE_DATE_EPOCH is outside the ZIP timestamp range.")
    info = zipfile.ZipInfo(name, moment.timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0
    return info


def _load_validator_module():
    spec = importlib.util.spec_from_file_location("security_record_validator", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the release-security validator.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_inputs(arguments: argparse.Namespace, security_record: dict, reproducibility: dict) -> None:
    schema = _json(SECURITY_SCHEMA)
    _load_validator_module().validate_record(security_record, schema, allow_template=False)
    identity = security_record["release_identity"]
    expected = {
        "version": arguments.version,
        "artifact_version": arguments.artifact_version,
        "tag": f"v{arguments.artifact_version}",
        "commit_sha": arguments.source_commit,
    }
    for field, value in expected.items():
        if identity[field] != value:
            raise ValueError(f"Security record {field} does not match the release candidate.")
    if reproducibility.get("record_type") != "arx_release_reproducibility":
        raise ValueError("Reproducibility input has an unexpected record type.")
    if reproducibility.get("release", {}).get("source_commit") != arguments.source_commit:
        raise ValueError("Reproducibility input does not match the release source commit.")
    classifications = reproducibility.get("artifacts", {})
    if set(classifications) != {"wheel", "sdist", "portable_zip", "arx_exe", "installer", "sha256sums"}:
        raise ValueError("Reproducibility input does not classify every required artifact.")


def assemble(arguments: argparse.Namespace) -> list[Path]:
    release_root = arguments.release_root.resolve()
    if not release_root.is_dir():
        raise FileNotFoundError("Release root does not exist.")
    version = arguments.version
    artifact_version = arguments.artifact_version
    core = [
        release_root / f"arx_prescanner-{version}-py3-none-any.whl",
        release_root / f"arx_prescanner-{version}.tar.gz",
        release_root / f"ARX-Desktop-win-x64-v{artifact_version}.zip",
    ]
    installer = release_root / f"ARX-Desktop-Setup-win-x64-v{artifact_version}.exe"
    if installer.is_file():
        core.append(installer)
    elif not arguments.allow_missing_installer:
        raise FileNotFoundError("The required Windows installer is missing.")
    for path in core:
        if not path.is_file():
            raise FileNotFoundError(f"Core release artifact is missing: {path.name}")

    names = {
        "sbom": f"ARX-{artifact_version}-SBOM.cdx.json",
        "provenance": f"ARX-{artifact_version}-provenance.zip",
        "reproducibility": f"ARX-{artifact_version}-reproducibility.json",
        "security": f"ARX-{artifact_version}-security-gates.json",
        "signing": f"ARX-{artifact_version}-signing-preflight.json",
        "lifecycle": f"ARX-{artifact_version}-lifecycle-preparation.json",
        "notes": "RELEASE_NOTES.md",
    }
    targets = {key: release_root / name for key, name in names.items()}
    security_record = _json(arguments.security_record)
    reproducibility = _json(arguments.reproducibility)
    _validate_inputs(arguments, security_record, reproducibility)
    sbom = _json(arguments.sbom)
    if sbom.get("bomFormat") != "CycloneDX":
        raise ValueError("SBOM input is not CycloneDX JSON.")
    signing = _json(arguments.signing)
    if signing.get("record_type") != "authenticode_verification":
        raise ValueError("Signing input has an unexpected record type.")
    lifecycle = _json(arguments.lifecycle)
    if lifecycle.get("record_type") != "standard_user_windows_lifecycle_gate":
        raise ValueError("Lifecycle input has an unexpected record type.")

    _copy(arguments.sbom, targets["sbom"])
    _copy(arguments.reproducibility, targets["reproducibility"])
    _copy(arguments.security_record, targets["security"])
    _copy(arguments.signing, targets["signing"])
    _copy(arguments.lifecycle, targets["lifecycle"])
    _copy(arguments.release_notes, targets["notes"])

    evidence_paths = [
        targets["reproducibility"],
        targets["security"],
        targets["signing"],
        targets["lifecycle"],
        targets["notes"],
    ]
    provenance_record = {
        "schema_version": 1,
        "record_type": "arx_release_provenance_bundle",
        "record_state": "FINAL",
        "release": {
            "version": version,
            "artifact_version": artifact_version,
            "tag": f"v{artifact_version}",
            "commit_sha": arguments.source_commit,
            "channel": "PRERELEASE",
        },
        "build": {
            "repository": "chatgptopenaiagi/ARX",
            "workflow": arguments.workflow,
            "run_id": arguments.run_id,
            "builder": arguments.builder,
            "source_date_epoch": arguments.source_date_epoch,
            "python_version": arguments.python_version,
        },
        "artifacts": [_subject(path, "clean build from the exact release commit") for path in core],
        "sboms": [_subject(targets["sbom"], "isolated release-wheel component inventory")],
        "evidence": [_subject(path, "bounded release-preparation evidence") for path in evidence_paths],
        "attestation": {
            "state": "PREPARED",
            "provider": "GitHub Artifact Attestations",
            "verification_repository": "chatgptopenaiagi/ARX",
            "limitation": "Verification can become VERIFIED only after GitHub creates and independently verifies the digest-bound attestation.",
        },
    }
    provenance_schema = _json(PROVENANCE_SCHEMA)
    _load_validator_module().validate_record(provenance_record, provenance_schema, allow_template=False)
    provenance_bytes = (json.dumps(provenance_record, indent=2, sort_keys=True) + "\n").encode()
    bundle_root = f"ARX-{artifact_version}-provenance"
    bundle_entries = {
        f"{bundle_root}/provenance.json": provenance_bytes,
        **{f"{bundle_root}/{path.name}": path.read_bytes() for path in [targets["sbom"], *evidence_paths]},
        f"{bundle_root}/schemas/release-security-record.schema.json": SECURITY_SCHEMA.read_bytes(),
        f"{bundle_root}/schemas/provenance-bundle.schema.json": PROVENANCE_SCHEMA.read_bytes(),
    }
    with zipfile.ZipFile(targets["provenance"], "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(bundle_entries):
            archive.writestr(_zip_info(name, arguments.source_date_epoch), bundle_entries[name])

    public = [*core, *(targets[key] for key in ("sbom", "provenance", "reproducibility", "security", "signing", "lifecycle", "notes"))]
    checksum = release_root / "SHA256SUMS.txt"
    checksum.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in sorted(public, key=lambda item: item.name)),
        encoding="utf-8",
        newline="\n",
    )
    verification = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--release-root",
            str(release_root),
            "--version",
            version,
            "--artifact-version",
            artifact_version,
            "--require-security-bundle",
        ],
        cwd=ROOT,
        check=False,
    )
    if verification.returncode:
        raise RuntimeError("Assembled release candidate failed final release-asset verification.")
    return [*public, checksum]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--artifact-version", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--builder", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--reproducibility", type=Path, required=True)
    parser.add_argument("--security-record", type=Path, required=True)
    parser.add_argument("--signing", type=Path, required=True)
    parser.add_argument("--lifecycle", type=Path, required=True)
    parser.add_argument("--release-notes", type=Path, required=True)
    parser.add_argument("--allow-missing-installer", action="store_true")
    arguments = parser.parse_args()
    assembled = assemble(arguments)
    print(f"Release candidate assembly: PASS ({len(assembled)} public files including checksums)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import hashlib
import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble-release-candidate.py"
SECURITY_TEMPLATE = ROOT / "security" / "release-record" / "release-security-record.template.json"
VERSION = "4.0.0b2"
ARTIFACT_VERSION = "4.0.0-b2"
COMMIT = "a" * 40


def _load_module():
    spec = importlib.util.spec_from_file_location("assemble_release_candidate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_core(root: Path):
    wheel = root / f"arx_prescanner-{VERSION}-py3-none-any.whl"
    dist_info = f"arx_prescanner-{VERSION}.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("arx/__init__.py", f'__version__ = "{VERSION}"\n')
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.4\nName: arx-prescanner\nVersion: {VERSION}\n",
        )
        archive.writestr(
            f"{dist_info}/entry_points.txt",
            "[console_scripts]\narx = arx.cli:main\narx-desktop = arx.desktop.__main__:main\n",
        )
    sdist = root / f"arx_prescanner-{VERSION}.tar.gz"
    metadata = f"Metadata-Version: 2.4\nName: arx-prescanner\nVersion: {VERSION}\n".encode()
    with tarfile.open(sdist, "w:gz") as archive:
        for name, payload in (
            (f"arx_prescanner-{VERSION}/PKG-INFO", metadata),
            (f"arx_prescanner-{VERSION}/README.md", b"ARX\n"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    portable = root / f"ARX-Desktop-win-x64-v{ARTIFACT_VERSION}.zip"
    with zipfile.ZipFile(portable, "w") as archive:
        archive.writestr("ARX-Desktop-win-x64/ARX.exe", b"MZ-fixture")
        archive.writestr("ARX-Desktop-win-x64/README.txt", b"ARX 4 Beta 2\n")
        archive.writestr("ARX-Desktop-win-x64/LICENSE.txt", b"MIT\n")
        archive.writestr("ARX-Desktop-win-x64/_internal/runtime.bin", b"runtime")
    installer = root / f"ARX-Desktop-Setup-win-x64-v{ARTIFACT_VERSION}.exe"
    installer.write_bytes(b"MZ-installer")


def _write_json(path: Path, value: dict):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _security_record(path: Path):
    record = json.loads(SECURITY_TEMPLATE.read_text(encoding="utf-8"))
    record["record_state"] = "FINAL"
    record["release_identity"] = {
        "product": "ARX 4",
        "version": VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "tag": f"v{ARTIFACT_VERSION}",
        "commit_sha": COMMIT,
        "build_date": "2026-08-24T00:00:00Z",
        "audit_date": "2026-08-24T00:00:00Z",
        "audit_commit": "b" * 40,
        "release_channel": "PRERELEASE",
        "windows_build_environment": "Windows test runner",
        "python_version": "3.12.0",
    }
    for gate in record["gates"]:
        gate.update(result="REVIEWED", evidence=["fixture evidence"], limitation=None)
    for result in record["reproducibility"].values():
        result.update(classification="BIT_FOR_BIT_REPRODUCIBLE", evidence="fixture", limitation=None)
    record["remaining_blockers"] = []
    record["limitations"] = ["Fixture record; not release evidence."]
    _write_json(path, record)


def test_assembly_creates_complete_hashed_private_data_bounded_bundle(tmp_path):
    release = tmp_path / "release"
    inputs = tmp_path / "inputs"
    release.mkdir()
    inputs.mkdir()
    _write_core(release)
    sbom = inputs / "sbom.json"
    _write_json(sbom, {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": []})
    reproducibility = inputs / "reproducibility.json"
    _write_json(
        reproducibility,
        {
            "schema_version": 1,
            "record_type": "arx_release_reproducibility",
            "release": {"source_commit": COMMIT},
            "artifacts": {
                name: {"classification": "BIT_FOR_BIT_REPRODUCIBLE"}
                for name in ("wheel", "sdist", "portable_zip", "arx_exe", "installer", "sha256sums")
            },
        },
    )
    security = inputs / "security.json"
    _security_record(security)
    signing = inputs / "signing.json"
    _write_json(signing, {"record_type": "authenticode_verification", "overall": "UNSIGNED_EXPECTED_PRE_SIGNING"})
    lifecycle = inputs / "lifecycle.json"
    _write_json(lifecycle, {"record_type": "standard_user_windows_lifecycle_gate", "result": "BLOCKED_NOT_EXECUTED"})
    notes = inputs / "notes.md"
    notes.write_text("# ARX 4.0.0 Beta 2\n", encoding="utf-8")
    arguments = argparse.Namespace(
        release_root=release,
        version=VERSION,
        artifact_version=ARTIFACT_VERSION,
        source_commit=COMMIT,
        source_date_epoch=1700000000,
        python_version="3.12.0",
        builder="test-runner",
        workflow="release-assets.yml",
        run_id="fixture",
        sbom=sbom,
        reproducibility=reproducibility,
        security_record=security,
        signing=signing,
        lifecycle=lifecycle,
        release_notes=notes,
        allow_missing_installer=False,
    )

    assembled = _load_module().assemble(arguments)

    assert len(assembled) == 12
    manifest = (release / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert len(manifest) == 11
    for line in manifest:
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((release / name).read_bytes()).hexdigest() == digest
    provenance = release / f"ARX-{ARTIFACT_VERSION}-provenance.zip"
    with zipfile.ZipFile(provenance) as archive:
        index_name = f"ARX-{ARTIFACT_VERSION}-provenance/provenance.json"
        index = json.loads(archive.read(index_name))
        assert index["record_state"] == "FINAL"
        assert index["release"]["commit_sha"] == COMMIT
        assert index["attestation"]["state"] == "PREPARED"

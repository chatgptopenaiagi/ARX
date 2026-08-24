import hashlib
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify-release-assets.py"
VERSION = "4.0.0b2"
ARTIFACT_VERSION = "4.0.0-b2"


def _write_sdist(path):
    prefix = f"arx_prescanner-{VERSION}"
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in (
            (f"{prefix}/PKG-INFO", f"Metadata-Version: 2.4\nName: arx-prescanner\nVersion: {VERSION}\n".encode()),
            (f"{prefix}/README.md", b"ARX release fixture\n"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


def _write_wheel(path):
    dist_info = f"arx_prescanner-{VERSION}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("arx/__init__.py", f'__version__ = "{VERSION}"\n')
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.4\nName: arx-prescanner\nVersion: {VERSION}\n",
        )
        archive.writestr(
            f"{dist_info}/entry_points.txt",
            "[console_scripts]\narx = arx.cli:main\narx-desktop = arx.desktop.__main__:main\n",
        )


def _write_portable(path, *, extra=b""):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ARX-Desktop-win-x64/ARX.exe", b"MZ-fixture")
        archive.writestr("ARX-Desktop-win-x64/README.txt", b"ARX 4 beta\n" + extra)
        archive.writestr("ARX-Desktop-win-x64/LICENSE.txt", b"MIT\n")
        archive.writestr("ARX-Desktop-win-x64/_internal/runtime.bin", b"runtime")


def _fixture(root, *, extra=b""):
    wheel = root / f"arx_prescanner-{VERSION}-py3-none-any.whl"
    sdist = root / f"arx_prescanner-{VERSION}.tar.gz"
    portable = root / f"ARX-Desktop-win-x64-v{ARTIFACT_VERSION}.zip"
    _write_wheel(wheel)
    _write_sdist(sdist)
    _write_portable(portable, extra=extra)
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in (wheel, sdist, portable)]
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run(root):
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--release-root",
            str(root),
            "--version",
            VERSION,
            "--artifact-version",
            ARTIFACT_VERSION,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_asset_verifier_accepts_exact_safe_distribution_set(tmp_path):
    _fixture(tmp_path)

    result = _run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Release artifacts: PASS (3 public artifacts; installer=not built)" in result.stdout
    assert "SHA-256 manifest: PASS" in result.stdout
    assert "secret/private-data scan: PASS" in result.stdout


def test_release_asset_verifier_suppresses_detected_secret_value(tmp_path):
    secret = ("sk-" + "proj-release-fixture-secret-value").encode()
    _fixture(tmp_path, extra=secret)

    result = _run(tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert secret.decode() not in combined
    assert "values suppressed" in combined


def test_release_asset_verifier_rejects_unmanifested_public_artifact(tmp_path):
    _fixture(tmp_path)
    (tmp_path / "ARX-Desktop-win-x64-v0.0.0.zip").write_bytes(b"unexpected")

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "Unexpected or missing versioned public release artifacts" in result.stderr


def test_release_asset_verifier_rejects_partial_security_bundle(tmp_path):
    _fixture(tmp_path)
    (tmp_path / f"ARX-{ARTIFACT_VERSION}-SBOM.cdx.json").write_text(
        '{"bomFormat":"CycloneDX"}\n', encoding="utf-8"
    )

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "partial security release bundle" in result.stderr.casefold()

import hashlib
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _read(name):
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_release_build_controls_source_epoch_hash_seed_and_timezone():
    release = _read("build-release.ps1")
    desktop = _read("build-desktop.ps1")

    for script in (release, desktop):
        assert "SOURCE_DATE_EPOCH" in script
        assert "PYTHONHASHSEED" in script
        assert "TZ" in script
        assert "resolve-source-date-epoch.ps1" in script
    assert "--noupx" in desktop
    assert "SetEnvironmentVariable" in release
    assert "SetEnvironmentVariable" in desktop


def test_portable_packaging_uses_deterministic_zip_not_compress_archive():
    packaging = _read("package-desktop-release.ps1")
    deterministic_zip = _read("new-deterministic-zip.ps1")

    assert "new-deterministic-zip.ps1" in packaging
    assert "Compress-Archive" not in packaging
    assert "StringComparer]::Ordinal" in deterministic_zip
    assert "LastWriteTime = $Timestamp" in deterministic_zip
    assert "ExternalAttributes = 0" in deterministic_zip


def test_installer_uses_reproducibility_controls():
    installer = (ROOT / "packaging" / "arx-desktop.iss").read_text(encoding="utf-8")

    assert "CompressionThreads=1" in installer
    assert "LZMANumBlockThreads=1" in installer
    assert "TimeStampsInUTC=yes" in installer
    assert installer.count("notimestamp") == 4
    assert "sortfilesbyname" in installer


@pytest.mark.skipif(os.name != "nt", reason="PowerShell ZIP implementation is Windows release tooling")
def test_deterministic_zip_ignores_source_creation_order_and_mtime(tmp_path):
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    assert pwsh
    epoch = 1_700_000_000
    sources = []
    for index, order in enumerate((("z.txt", "a.txt"), ("a.txt", "z.txt")), start=1):
        source = tmp_path / f"source-{index}"
        source.mkdir()
        for name in order:
            path = source / name
            path.write_text(f"content:{name}\n", encoding="utf-8")
            os.utime(path, (epoch + index * 100, epoch + index * 100))
        nested = source / "nested"
        nested.mkdir()
        (nested / "value.bin").write_bytes(b"stable")
        sources.append(source)

    archives = []
    for index, source in enumerate(sources, start=1):
        destination = tmp_path / f"archive-{index}.zip"
        completed = subprocess.run(
            [
                pwsh,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(SCRIPTS / "new-deterministic-zip.ps1"),
                "-SourceDirectory",
                str(source),
                "-DestinationPath",
                str(destination),
                "-RootName",
                "ARX-Test",
                "-SourceDateEpoch",
                str(epoch),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        archives.append(destination)

    assert hashlib.sha256(archives[0].read_bytes()).digest() == hashlib.sha256(
        archives[1].read_bytes()
    ).digest()
    with zipfile.ZipFile(archives[0]) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        expected = datetime.fromtimestamp(epoch, timezone.utc)
        for item in archive.infolist():
            observed = datetime(*item.date_time, tzinfo=timezone.utc)
            assert abs((observed - expected).total_seconds()) <= 2

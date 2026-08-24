import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
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
    assert "normalize-sdist.py" in release
    assert "--source-date-epoch $SourceDateEpoch" in release


def _write_sdist(path, *, version, epoch, reverse):
    root = f"arx_prescanner-{version}"
    entries = [(f"{root}/", None), (f"{root}/a.txt", b"a"), (f"{root}/z.txt", b"z")]
    if reverse:
        entries.reverse()
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name, content in entries:
            info = tarfile.TarInfo(name)
            info.mtime = epoch
            info.mode = 0o755 if content is None else 0o644
            if content is None:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))


def test_sdist_normalization_ignores_member_order_and_archive_timestamps(tmp_path):
    version = "4.0.0b2"
    source_epoch = 1_700_000_000
    archives = []
    for index in (1, 2):
        directory = tmp_path / str(index)
        directory.mkdir()
        archive = directory / f"arx_prescanner-{version}.tar.gz"
        _write_sdist(
            archive,
            version=version,
            epoch=source_epoch + index * 100,
            reverse=index == 2,
        )
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "normalize-sdist.py"),
                "--sdist",
                str(archive),
                "--version",
                version,
                "--source-date-epoch",
                str(source_epoch),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        archives.append(archive)

    assert archives[0].read_bytes() == archives[1].read_bytes()
    with tarfile.open(archives[0], "r:gz") as archive:
        assert archive.getnames() == sorted(archive.getnames())
        assert all(member.mtime == source_epoch for member in archive.getmembers())


def test_sdist_normalization_rejects_traversal(tmp_path):
    version = "4.0.0b2"
    archive = tmp_path / f"arx_prescanner-{version}.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        info = tarfile.TarInfo(f"arx_prescanner-{version}/../escape.txt")
        info.size = 1
        output.addfile(info, io.BytesIO(b"x"))

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "normalize-sdist.py"),
            "--sdist",
            str(archive),
            "--version",
            version,
            "--source-date-epoch",
            "1700000000",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "traversing" in result.stderr


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


def test_windows_release_toolchain_is_exact_and_created_outside_checkout():
    lock = (ROOT / "packaging" / "release-build-requirements.txt").read_text(encoding="utf-8")
    environment = _read("new-release-environment.ps1")
    requirements = [line for line in lock.splitlines() if line and not line.startswith("#")]

    assert requirements == sorted(requirements, key=str.casefold)
    assert len(requirements) == len(set(map(str.casefold, requirements)))
    assert all("==" in requirement for requirement in requirements)
    assert all(marker not in lock for marker in (">=", "~=", " -e ", "https://", "http://"))
    for requirement in (
        "build==1.5.0",
        "cyclonedx-bom==7.3.1",
        "pyinstaller==6.22.2",
        "setuptools==84.0.0",
        "twine==7.0.0",
        "wheel==0.48.0",
    ):
        assert requirement in requirements
    assert "3.12.13" in environment
    assert "release virtual environment must be outside" in environment.casefold()
    assert "Refusing to overwrite" in environment
    assert "--requirement $Requirements" in environment
    assert "-m pip check" in environment


def test_sbom_generation_is_reproducible_validated_and_cleans_only_temp_storage():
    script = _read("generate-release-sbom.ps1")

    assert "--without-pip" in script
    assert "--no-deps" in script
    assert "--spec-version 1.6" in script
    assert "--output-reproducible" in script
    assert "--validate" in script
    assert "bomFormat" in script and "CycloneDX" in script
    assert "GetTempPath" in script
    assert "StartsWith" in script
    assert "Remove-Item -LiteralPath $ResolvedScratch -Recurse -Force" in script


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

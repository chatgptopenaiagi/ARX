import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "write-public-checksums.py"


def test_checksum_writer_is_sorted_and_excludes_an_existing_manifest(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    (release / "z.bin").write_bytes(b"z")
    (release / "a.bin").write_bytes(b"a")
    (release / "SHA256SUMS.txt").write_text("stale\n", encoding="utf-8")
    output = tmp_path / "rebuilt" / "SHA256SUMS.txt"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--release-root", str(release), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8").splitlines() == [
        f"{hashlib.sha256(b'a').hexdigest()}  a.bin",
        f"{hashlib.sha256(b'z').hexdigest()}  z.bin",
    ]


def test_checksum_module_uses_streaming_sha256():
    spec = importlib.util.spec_from_file_location("write_public_checksums", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.digest(Path(__file__)) == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

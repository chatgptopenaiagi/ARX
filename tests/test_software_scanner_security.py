import json
import struct
import zipfile

import pytest

from arx.software import scan_software


def _write_short_pe(path, optional_size: int, tail: bytes = b"") -> None:
    pe_offset = 64
    optional_offset = pe_offset + 24
    payload = bytearray(max(optional_offset + optional_size, 90))
    payload[:2] = b"MZ"
    struct.pack_into("<I", payload, 60, pe_offset)
    payload[pe_offset : pe_offset + 4] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH",
        payload,
        pe_offset + 4,
        0x8664,
        1,
        0,
        0,
        0,
        optional_size,
        0x22,
    )
    struct.pack_into("<H", payload, optional_offset, 0x20B)
    payload.extend(tail)
    path.write_bytes(payload)


@pytest.mark.parametrize(
    ("optional_size", "tail"),
    ((2, b""), (45, b"\0" * 25)),
)
def test_short_declared_pe_optional_header_is_reported(
    tmp_path, optional_size, tail
):
    executable = tmp_path / "short.exe"
    _write_short_pe(executable, optional_size, tail)
    original = executable.read_bytes()

    result = scan_software(executable)

    assert result["detected_file_type"] == "windows_pe"
    assert result["inspection_error"] == "truncated optional header"
    assert executable.read_bytes() == original


@pytest.mark.parametrize(
    "package_data",
    (None, [], "metadata", 42, {"engines": None}, {"engines": []}),
)
def test_non_object_package_metadata_is_ignored_in_directory(tmp_path, package_data):
    package = tmp_path / "package.json"
    package.write_text(json.dumps(package_data), encoding="utf-8")
    original = package.read_bytes()

    result = scan_software(tmp_path)

    assert result["detected_file_type"] == "directory"
    assert result["requirements"] == []
    assert package.read_bytes() == original


@pytest.mark.parametrize(
    "package_data",
    (None, [], "metadata", 42, {"engines": None}, {"engines": []}),
)
def test_non_object_package_metadata_is_ignored_in_archive(tmp_path, package_data):
    archive_path = tmp_path / "metadata.zip"
    escaped_path = tmp_path / "escaped.txt"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("package.json", json.dumps(package_data))
        archive.writestr("../escaped.txt", "not extracted")

    result = scan_software(archive_path)

    assert result["detected_file_type"] == "zip_archive"
    assert result["requirements"] == []
    assert result["archive"]["entries"] == 2
    assert not escaped_path.exists()

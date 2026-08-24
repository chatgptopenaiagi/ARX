"""Compare immutable ARX Beta 1 artifacts with two clean rebuilds.

The report uses logical labels only. It never emits checkout, build-user, or
temporary paths.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import marshal
import re
import tarfile
import tempfile
import types
import zipfile
from pathlib import Path, PureWindowsPath

import pefile
from PyInstaller.archive.readers import CArchiveReader


PACKAGE_VERSION = "4.0.0b1"
ARTIFACT_VERSION = "4.0.0-b1"
WHEEL = f"arx_prescanner-{PACKAGE_VERSION}-py3-none-any.whl"
SDIST = f"arx_prescanner-{PACKAGE_VERSION}.tar.gz"
PORTABLE = f"ARX-Desktop-win-x64-v{ARTIFACT_VERSION}.zip"
INSTALLER = f"ARX-Desktop-Setup-win-x64-v{ARTIFACT_VERSION}.exe"
MANIFEST = "SHA256SUMS.txt"
PORTABLE_EXE = "ARX-Desktop-win-x64/ARX.exe"
BASE_LIBRARY = "ARX-Desktop-win-x64/_internal/base_library.zip"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(encoded)


def zip_profile(path: Path) -> dict[str, object]:
    logical: list[dict[str, object]] = []
    metadata: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            content_hash = None if info.is_dir() else sha256_bytes(archive.read(info))
            logical.append(
                {
                    "name": info.filename,
                    "is_directory": info.is_dir(),
                    "size": info.file_size,
                    "sha256": content_hash,
                }
            )
            metadata.append(
                {
                    **logical[-1],
                    "compressed_size": info.compress_size,
                    "compression": info.compress_type,
                    "timestamp": info.date_time,
                    "external_attributes": info.external_attr,
                }
            )
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "entry_count": len(logical),
        "logical_hash": stable_hash(logical),
        "metadata_hash": stable_hash(metadata),
        "timestamp_hash": stable_hash(
            [{"name": item["name"], "timestamp": item["timestamp"]} for item in metadata]
        ),
        "compression_layout_hash": stable_hash(
            [
                {
                    "name": item["name"],
                    "compressed_size": item["compressed_size"],
                    "compression": item["compression"],
                }
                for item in metadata
            ]
        ),
        "attribute_hash": stable_hash(
            [{"name": item["name"], "external_attributes": item["external_attributes"]} for item in metadata]
        ),
        "entries": logical,
    }


def pyc_code(payload: bytes) -> types.CodeType | None:
    for offset in (16, 12, 8):
        try:
            value = marshal.loads(payload[offset:])
        except (EOFError, ValueError, TypeError):
            continue
        if isinstance(value, types.CodeType):
            return value
    return None


def base_library_profile(payload: bytes) -> dict[str, object]:
    logical: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    filenames: list[str] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            data = archive.read(info)
            code = pyc_code(data) if info.filename.endswith(".pyc") else None
            if code is not None:
                semantic_hash = stable_hash(semantic_code(code))
                filenames.extend(collect_code_filenames(code))
                content_type = "python_bytecode"
            else:
                semantic_hash = sha256_bytes(data)
                content_type = "bytes"
            item = {
                "name": info.filename,
                "content_type": content_type,
                "semantic_hash": semantic_hash,
            }
            logical.append(item)
            details.append({**item, "raw_sha256": sha256_bytes(data), "raw_size": len(data)})
    return {
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "entry_count": len(logical),
        "semantic_hash": stable_hash(logical),
        "code_filenames": safe_filename_summary(filenames),
        "entries": details,
    }


def tar_profile(path: Path) -> dict[str, object]:
    logical: list[dict[str, object]] = []
    metadata: list[dict[str, object]] = []
    with tarfile.open(path, "r:gz") as archive:
        for member in sorted(archive.getmembers(), key=lambda item: item.name):
            payload_hash = None
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is not None:
                    payload_hash = sha256_bytes(stream.read())
            logical.append(
                {
                    "name": member.name,
                    "type": member.type.decode("ascii", errors="replace"),
                    "mode": member.mode,
                    "size": member.size,
                    "linkname": member.linkname,
                    "sha256": payload_hash,
                }
            )
            metadata.append(
                {
                    **logical[-1],
                    "mtime": member.mtime,
                    "uid": member.uid,
                    "gid": member.gid,
                    "uname": member.uname,
                    "gname": member.gname,
                }
            )
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "entry_count": len(logical),
        "logical_hash": stable_hash(logical),
        "metadata_hash": stable_hash(metadata),
        "mtime_hash": stable_hash([{"name": item["name"], "mtime": item["mtime"]} for item in metadata]),
        "ownership_hash": stable_hash(
            [
                {
                    "name": item["name"],
                    "uid": item["uid"],
                    "gid": item["gid"],
                    "uname": item["uname"],
                    "gname": item["gname"],
                }
                for item in metadata
            ]
        ),
        "entries": logical,
    }


def semantic_value(value: object) -> object:
    if isinstance(value, types.CodeType):
        return semantic_code(value)
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [semantic_value(item) for item in value]}
    if isinstance(value, frozenset):
        items = [semantic_value(item) for item in value]
        return {"type": "frozenset", "items": sorted(items, key=stable_hash)}
    if isinstance(value, bytes):
        return {"type": "bytes", "sha256": sha256_bytes(value), "length": len(value)}
    if value is None or isinstance(value, (bool, int, float, str)):
        return {"type": type(value).__name__, "value": value}
    if isinstance(value, complex):
        return {"type": "complex", "real": value.real, "imag": value.imag}
    if value is Ellipsis:
        return {"type": "ellipsis"}
    return {"type": type(value).__name__, "repr_sha256": sha256_bytes(repr(value).encode())}


def semantic_code(code: types.CodeType) -> dict[str, object]:
    result: dict[str, object] = {
        "type": "code",
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "bytecode_sha256": sha256_bytes(code.co_code),
        "constants": [semantic_value(item) for item in code.co_consts],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
        "name": code.co_name,
        "firstlineno": code.co_firstlineno,
        "line_table_sha256": sha256_bytes(code.co_lnotab),
    }
    return result


def collect_code_filenames(code: types.CodeType) -> list[str]:
    values = [code.co_filename]
    for item in code.co_consts:
        if isinstance(item, types.CodeType):
            values.extend(collect_code_filenames(item))
    return values


def code_payload_profile(value: object) -> tuple[str, list[str]]:
    if isinstance(value, types.CodeType):
        return stable_hash(semantic_code(value)), collect_code_filenames(value)
    if isinstance(value, bytes):
        try:
            unmarshaled = marshal.loads(value)
        except (EOFError, ValueError, TypeError):
            return sha256_bytes(value), []
        if isinstance(unmarshaled, types.CodeType):
            return stable_hash(semantic_code(unmarshaled)), collect_code_filenames(unmarshaled)
        return sha256_bytes(value), []
    return stable_hash(repr(value)), []


def raw_payload_hash(value: object) -> str:
    if isinstance(value, types.CodeType):
        return sha256_bytes(marshal.dumps(value))
    if isinstance(value, bytes):
        return sha256_bytes(value)
    return sha256_bytes(repr(value).encode())


def safe_filename_summary(filenames: list[str]) -> dict[str, int]:
    unique = sorted(set(filenames))
    home_name = Path.home().name.casefold()
    absolute = 0
    home_component = 0
    synthetic = 0
    for value in unique:
        if value.startswith("<") and value.endswith(">"):
            synthetic += 1
            continue
        windows = PureWindowsPath(value)
        if windows.is_absolute() or Path(value).is_absolute():
            absolute += 1
        components = [part.casefold() for part in re.split(r"[\\/]", value) if part]
        if home_name and home_name in components:
            home_component += 1
    return {
        "unique": len(unique),
        "absolute": absolute,
        "build_user_component": home_component,
        "synthetic": synthetic,
    }


def pyinstaller_profile(path: Path) -> dict[str, object]:
    archive = CArchiveReader(str(path))
    entries: list[dict[str, object]] = []
    filenames: list[str] = []
    for name in sorted(archive.toc):
        _offset, _compressed, uncompressed, _flag, entry_type = archive.toc[name]
        if name == "PYZ.pyz":
            pyz = archive.open_embedded_archive(name)
            pyz_entries: list[dict[str, object]] = []
            for module_name in sorted(pyz.toc):
                value = pyz.extract(module_name)
                semantic_hash, code_filenames = code_payload_profile(value)
                filenames.extend(code_filenames)
                pyz_entries.append(
                    {
                        "name": module_name,
                        "semantic_hash": semantic_hash,
                        "raw_marshaled_hash": raw_payload_hash(value),
                    }
                )
            semantic_hash = stable_hash(
                [
                    {"name": item["name"], "semantic_hash": item["semantic_hash"]}
                    for item in pyz_entries
                ]
            )
            entries.append(
                {
                    "name": name,
                    "type": entry_type,
                    "uncompressed_size": uncompressed,
                    "semantic_hash": semantic_hash,
                    "nested_entry_count": len(pyz_entries),
                    "nested_entries": pyz_entries,
                }
            )
            continue
        payload = archive.extract(name)
        semantic_hash, code_filenames = code_payload_profile(payload)
        filenames.extend(code_filenames)
        entries.append(
            {
                "name": name,
                "type": entry_type,
                "uncompressed_size": uncompressed,
                "semantic_hash": semantic_hash,
                "raw_payload_hash": raw_payload_hash(payload),
            }
        )
    semantic_entries = [
        {
            "name": entry["name"],
            "type": entry["type"],
            "semantic_hash": entry["semantic_hash"],
            "nested_entry_count": entry.get("nested_entry_count"),
        }
        for entry in entries
    ]
    return {
        "entry_count": len(entries),
        "semantic_hash": stable_hash(semantic_entries),
        "code_filenames": safe_filename_summary(filenames),
        "entries": entries,
    }


def pe_profile(path: Path, *, pyinstaller: bool) -> dict[str, object]:
    pe = pefile.PE(str(path), fast_load=False)
    overlay_offset = pe.get_overlay_data_start_offset()
    sections = [
        {
            "name": section.Name.rstrip(b"\0").decode("ascii", errors="replace"),
            "virtual_size": section.Misc_VirtualSize,
            "raw_size": section.SizeOfRawData,
            "characteristics": section.Characteristics,
            "sha256": sha256_bytes(section.get_data()),
        }
        for section in pe.sections
    ]
    result: dict[str, object] = {
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "machine": pe.FILE_HEADER.Machine,
        "coff_timestamp": pe.FILE_HEADER.TimeDateStamp,
        "checksum": pe.OPTIONAL_HEADER.CheckSum,
        "subsystem": pe.OPTIONAL_HEADER.Subsystem,
        "image_base": pe.OPTIONAL_HEADER.ImageBase,
        "size_of_image": pe.OPTIONAL_HEADER.SizeOfImage,
        "section_count": len(sections),
        "sections": sections,
        "section_shape_hash": stable_hash(
            [{key: value for key, value in section.items() if key != "sha256"} for section in sections]
        ),
        "section_content_hash": stable_hash(sections),
        "overlay_offset": overlay_offset,
        "overlay_bytes": 0 if overlay_offset is None else path.stat().st_size - overlay_offset,
    }
    if pyinstaller:
        result["pyinstaller"] = pyinstaller_profile(path)
    return result


def changed_entry_names(profiles: dict[str, dict[str, object]], reference: str = "published") -> dict[str, list[str]]:
    reference_map = {item["name"]: item for item in profiles[reference]["entries"]}
    result: dict[str, list[str]] = {}
    for label, profile in profiles.items():
        if label == reference:
            continue
        current_map = {item["name"]: item for item in profile["entries"]}
        names = sorted(set(reference_map) | set(current_map))
        result[label] = [name for name in names if reference_map.get(name) != current_map.get(name)]
    return result


def byte_diff(left: Path, right: Path) -> dict[str, object]:
    first: list[int] = []
    different = 0
    offset = 0
    with left.open("rb") as left_stream, right.open("rb") as right_stream:
        while True:
            a = left_stream.read(1024 * 1024)
            b = right_stream.read(1024 * 1024)
            if not a and not b:
                break
            common = min(len(a), len(b))
            for index in range(common):
                if a[index] != b[index]:
                    different += 1
                    if len(first) < 12:
                        first.append(offset + index)
            different += abs(len(a) - len(b))
            offset += max(len(a), len(b))
    return {"different_byte_positions": different, "first_offsets": first}


def parse_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        checksum, name = line.split("  ", 1)
        result[name] = checksum
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--published-root", type=Path, required=True)
    parser.add_argument("--build-a-root", type=Path, required=True)
    parser.add_argument("--build-b-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    roots = {
        "published": arguments.published_root,
        "build_a": arguments.build_a_root,
        "build_b": arguments.build_b_root,
    }
    for root in roots.values():
        for name in (WHEEL, SDIST, PORTABLE, INSTALLER, MANIFEST):
            if not (root / name).is_file():
                raise SystemExit(f"Required artifact missing: {name}")

    wheel_profiles = {label: zip_profile(root / WHEEL) for label, root in roots.items()}
    sdist_profiles = {label: tar_profile(root / SDIST) for label, root in roots.items()}
    portable_profiles = {label: zip_profile(root / PORTABLE) for label, root in roots.items()}
    base_library_profiles: dict[str, dict[str, object]] = {}
    for label, root in roots.items():
        with zipfile.ZipFile(root / PORTABLE) as archive:
            base_library_profiles[label] = base_library_profile(archive.read(BASE_LIBRARY))

    with tempfile.TemporaryDirectory(prefix="arx-repro-inspection-") as temporary:
        temp_root = Path(temporary)
        arx_executables: dict[str, Path] = {}
        for label, root in roots.items():
            if label == "published":
                target = temp_root / "published-ARX.exe"
                with zipfile.ZipFile(root / PORTABLE) as archive:
                    target.write_bytes(archive.read(PORTABLE_EXE))
                arx_executables[label] = target
            else:
                arx_executables[label] = root / "ARX-Desktop-win-x64" / "ARX.exe"
        arx_profiles = {
            label: pe_profile(path, pyinstaller=True) for label, path in arx_executables.items()
        }
        arx_diffs = {
            "build_a_vs_published": byte_diff(arx_executables["published"], arx_executables["build_a"]),
            "build_b_vs_published": byte_diff(arx_executables["published"], arx_executables["build_b"]),
            "build_a_vs_build_b": byte_diff(arx_executables["build_a"], arx_executables["build_b"]),
        }

    installer_profiles = {
        label: pe_profile(root / INSTALLER, pyinstaller=False) for label, root in roots.items()
    }
    installer_diffs = {
        "build_a_vs_published": byte_diff(roots["published"] / INSTALLER, roots["build_a"] / INSTALLER),
        "build_b_vs_published": byte_diff(roots["published"] / INSTALLER, roots["build_b"] / INSTALLER),
        "build_a_vs_build_b": byte_diff(roots["build_a"] / INSTALLER, roots["build_b"] / INSTALLER),
    }
    manifests = {label: parse_manifest(root / MANIFEST) for label, root in roots.items()}
    manifest_validity = {
        label: all(sha256_file(root / name) == checksum for name, checksum in manifests[label].items())
        for label, root in roots.items()
    }

    def compact(profile: dict[str, object]) -> dict[str, object]:
        return {key: value for key, value in profile.items() if key != "entries"}

    output = {
        "schema_version": 1,
        "wheel": {
            "profiles": {label: compact(profile) for label, profile in wheel_profiles.items()},
            "logical_equal_all": len({profile["logical_hash"] for profile in wheel_profiles.values()}) == 1,
            "changed_entries_from_published": changed_entry_names(wheel_profiles),
        },
        "sdist": {
            "profiles": {label: compact(profile) for label, profile in sdist_profiles.items()},
            "logical_equal_all": len({profile["logical_hash"] for profile in sdist_profiles.values()}) == 1,
            "changed_entries_from_published": changed_entry_names(sdist_profiles),
        },
        "portable_zip": {
            "profiles": {label: compact(profile) for label, profile in portable_profiles.items()},
            "logical_equal_all": len({profile["logical_hash"] for profile in portable_profiles.values()}) == 1,
            "changed_entries_from_published": changed_entry_names(portable_profiles),
            "base_library": {
                "profiles": base_library_profiles,
                "semantic_equal_all": len(
                    {profile["semantic_hash"] for profile in base_library_profiles.values()}
                )
                == 1,
            },
        },
        "arx_exe": {
            "profiles": arx_profiles,
            "semantic_equal_all": len(
                {profile["pyinstaller"]["semantic_hash"] for profile in arx_profiles.values()}
            )
            == 1,
            "section_shape_equal_all": len({profile["section_shape_hash"] for profile in arx_profiles.values()}) == 1,
            "byte_differences": arx_diffs,
        },
        "installer": {
            "profiles": installer_profiles,
            "section_shape_equal_all": len(
                {profile["section_shape_hash"] for profile in installer_profiles.values()}
            )
            == 1,
            "byte_differences": installer_diffs,
        },
        "sha256sums": {
            "profiles": {
                label: {
                    "bytes": (root / MANIFEST).stat().st_size,
                    "sha256": sha256_file(root / MANIFEST),
                    "entry_names": sorted(manifests[label]),
                    "valid_for_build": manifest_validity[label],
                }
                for label, root in roots.items()
            },
            "entry_names_equal_all": len({tuple(sorted(value)) for value in manifests.values()}) == 1,
            "valid_all": all(manifest_validity.values()),
        },
    }
    rendered = json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8", newline="\n")
        print("Reproducibility comparison written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

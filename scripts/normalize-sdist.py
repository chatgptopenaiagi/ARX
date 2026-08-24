"""Rebuild an ARX sdist with bounded, source-derived archive metadata."""

from __future__ import annotations

import argparse
import gzip
import io
import os
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_CONTENT_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 5_000


@dataclass(frozen=True)
class Member:
    name: str
    mode: int
    is_directory: bool
    content: bytes


def _safe_name(name: str, root: str) -> str:
    if "\\" in name:
        raise ValueError("sdist member names must use POSIX separators.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("sdist contains an absolute or traversing member name.")
    if not path.parts or path.parts[0] != root:
        raise ValueError("sdist member is outside the expected package root.")
    return path.as_posix().rstrip("/")


def _read_members(source: Path, expected_root: str) -> list[Member]:
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("sdist exceeds the normalization input bound.")
    result: list[Member] = []
    seen: set[str] = set()
    total = 0
    with tarfile.open(source, "r:gz") as archive:
        members = archive.getmembers()
        if not members or len(members) > MAX_MEMBERS:
            raise ValueError("sdist member count is empty or exceeds the bound.")
        for item in members:
            name = _safe_name(item.name, expected_root)
            if name in seen:
                raise ValueError("sdist contains a duplicate normalized member name.")
            seen.add(name)
            if item.isdir():
                content = b""
            elif item.isfile():
                stream = archive.extractfile(item)
                if stream is None:
                    raise ValueError("sdist regular-file content could not be read.")
                content = stream.read(MAX_CONTENT_BYTES + 1)
                total += len(content)
                if total > MAX_CONTENT_BYTES:
                    raise ValueError("sdist uncompressed content exceeds the bound.")
            else:
                raise ValueError("sdist contains an unsupported non-file member type.")
            result.append(Member(name, item.mode & 0o777, item.isdir(), content))
    return sorted(result, key=lambda item: item.name)


def _write_normalized(destination: Path, members: list[Member], epoch: int) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw, gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw,
            mtime=epoch,
        ) as compressed, tarfile.open(
            fileobj=compressed,
            mode="w",
            format=tarfile.PAX_FORMAT,
        ) as archive:
            for member in members:
                info = tarfile.TarInfo(member.name)
                info.mode = member.mode
                info.mtime = epoch
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                if member.is_directory:
                    info.type = tarfile.DIRTYPE
                    info.size = 0
                    archive.addfile(info)
                else:
                    info.type = tarfile.REGTYPE
                    info.size = len(member.content)
                    archive.addfile(info, io.BytesIO(member.content))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def normalize(source: Path, version: str, epoch: int) -> None:
    expected_name = f"arx_prescanner-{version}.tar.gz"
    expected_root = f"arx_prescanner-{version}"
    resolved = source.resolve(strict=True)
    if resolved.name != expected_name:
        raise ValueError("sdist filename does not match the requested ARX version.")
    if not 0 <= epoch <= 0xFFFFFFFF:
        raise ValueError("SOURCE_DATE_EPOCH is outside the portable gzip range.")
    members = _read_members(resolved, expected_root)
    _write_normalized(resolved, members, epoch)
    if _read_members(resolved, expected_root) != members:
        raise ValueError("normalized sdist failed independent member verification.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    arguments = parser.parse_args()
    normalize(arguments.sdist, arguments.version, arguments.source_date_epoch)
    print(f"Deterministic sdist normalized: {arguments.sdist.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

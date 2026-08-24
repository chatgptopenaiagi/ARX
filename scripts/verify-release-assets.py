"""Verify ARX release filenames, hashes, package metadata, and privacy bounds."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import tarfile
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

KEY_PATTERN = re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_.-]{16,}")
FORBIDDEN_ENTRY_NAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "external-transmissions.jsonl",
    "openai-api-key" + "2.txt",
}
FORBIDDEN_ENTRY_SUFFIXES = {".dpapi", ".key", ".pem", ".pfx", ".p12"}
MAX_NESTED_ARCHIVE_BYTES = 64 * 1024 * 1024


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if match is None:
            raise ValueError("SHA256SUMS.txt contains a malformed or path-bearing entry.")
        checksum, name = match.groups()
        if name in entries:
            raise ValueError("SHA256SUMS.txt contains a duplicate filename.")
        entries[name] = checksum
    return entries


def forbidden_markers(root: Path) -> list[bytes]:
    candidates = {
        str(root.resolve()),
        str(Path.cwd().resolve()),
        str(Path.home().resolve()),
        os.environ.get("USERPROFILE", ""),
        "openai-api-key" + "2.txt",
    }
    markers: list[bytes] = []
    for candidate in candidates:
        if not candidate or len(candidate) < 4:
            continue
        markers.extend((candidate.encode("utf-8", errors="ignore"), candidate.encode("utf-16-le", errors="ignore")))
    return [marker for marker in markers if marker]


def inspect_name(label: str, name: str) -> list[str]:
    findings: list[str] = []
    path = PurePosixPath(name.replace("\\", "/"))
    folded = path.name.casefold()
    if folded in FORBIDDEN_ENTRY_NAMES or path.suffix.casefold() in FORBIDDEN_ENTRY_SUFFIXES:
        findings.append(f"{label}: forbidden secret or private-data filename")
    if any(part.casefold() in {".git", ".venv", ".pytest_cache"} for part in path.parts):
        findings.append(f"{label}: forbidden development directory")
    return findings


def inspect_bytes(label: str, payload: bytes, markers: list[bytes], *, nested: bool = True) -> list[str]:
    findings: list[str] = []
    if KEY_PATTERN.search(payload):
        findings.append(f"{label}: OpenAI credential-shaped material")
    if any(marker in payload for marker in markers):
        findings.append(f"{label}: local build identity or temporary credential filename")
    if nested and len(payload) <= MAX_NESTED_ARCHIVE_BYTES and payload.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                for info in archive.infolist():
                    nested_label = f"{label}!{info.filename}"
                    findings.extend(inspect_name(nested_label, info.filename))
                    if not info.is_dir():
                        findings.extend(inspect_bytes(nested_label, archive.read(info), markers, nested=False))
        except (OSError, ValueError, zipfile.BadZipFile):
            pass
    return findings


def inspect_zip(path: Path, markers: list[bytes]) -> tuple[set[str], list[str]]:
    names: set[str] = set()
    findings: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            names.add(info.filename)
            label = f"{path.name}!{info.filename}"
            findings.extend(inspect_name(label, info.filename))
            if not info.is_dir():
                findings.extend(inspect_bytes(label, archive.read(info), markers))
    return names, findings


def inspect_sdist(path: Path, markers: list[bytes]) -> tuple[set[str], list[str]]:
    names: set[str] = set()
    findings: list[str] = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            names.add(member.name)
            label = f"{path.name}!{member.name}"
            findings.extend(inspect_name(label, member.name))
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is not None:
                    findings.extend(inspect_bytes(label, stream.read(), markers))
    return names, findings


def require_metadata(payload: bytes, version: str) -> None:
    metadata = BytesParser(policy=policy.default).parsebytes(payload)
    if metadata.get("Name") != "arx-prescanner" or metadata.get("Version") != version:
        raise ValueError("Python distribution metadata does not match arx-prescanner and the release version.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--artifact-version", required=True)
    parser.add_argument("--require-security-bundle", action="store_true")
    arguments = parser.parse_args()

    root = arguments.release_root.resolve()
    version = arguments.version
    artifact_version = arguments.artifact_version
    wheel = root / f"arx_prescanner-{version}-py3-none-any.whl"
    sdist = root / f"arx_prescanner-{version}.tar.gz"
    portable = root / f"ARX-Desktop-win-x64-v{artifact_version}.zip"
    installer = root / f"ARX-Desktop-Setup-win-x64-v{artifact_version}.exe"
    manifest_path = root / "SHA256SUMS.txt"
    sbom = root / f"ARX-{artifact_version}-SBOM.cdx.json"
    provenance = root / f"ARX-{artifact_version}-provenance.zip"
    reproducibility = root / f"ARX-{artifact_version}-reproducibility.json"
    security_gates = root / f"ARX-{artifact_version}-security-gates.json"
    signing = root / f"ARX-{artifact_version}-signing-preflight.json"
    lifecycle = root / f"ARX-{artifact_version}-lifecycle-preparation.json"
    release_notes = root / "RELEASE_NOTES.md"

    required = (wheel, sdist, portable, manifest_path)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing required release artifact(s): " + ", ".join(missing))

    public = [wheel, sdist, portable]
    if installer.is_file():
        public.append(installer)
    security_bundle = [sbom, provenance, reproducibility, security_gates, signing, lifecycle, release_notes]
    present_security_bundle = [path for path in security_bundle if path.is_file()]
    if arguments.require_security_bundle and len(present_security_bundle) != len(security_bundle):
        missing_security = [path.name for path in security_bundle if not path.is_file()]
        raise SystemExit("Missing required security release asset(s): " + ", ".join(missing_security))
    if present_security_bundle and len(present_security_bundle) != len(security_bundle):
        raise SystemExit("A partial security release bundle is not permitted.")
    public.extend(present_security_bundle)
    actual_public = {path.name for path in root.iterdir() if path.is_file() and path != manifest_path}
    expected_public = {path.name for path in public}
    if actual_public != expected_public:
        raise SystemExit("Unexpected or missing versioned public release artifacts.")

    try:
        manifest = parse_manifest(manifest_path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    if set(manifest) != expected_public:
        raise SystemExit("SHA256SUMS.txt does not name exactly every public release artifact.")
    for path in public:
        if digest(path) != manifest[path.name]:
            raise SystemExit(f"SHA-256 mismatch for {path.name}.")

    markers = forbidden_markers(root)
    findings: list[str] = []
    for path in public:
        findings.extend(inspect_name(path.name, path.name))
        findings.extend(inspect_bytes(path.name, path.read_bytes(), markers, nested=False))

    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        entry_names = [name for name in archive.namelist() if name.endswith(".dist-info/entry_points.txt")]
        if len(metadata_names) != 1 or len(entry_names) != 1:
            raise SystemExit("Wheel metadata or console entry points are incomplete.")
        require_metadata(archive.read(metadata_names[0]), version)
        entry_points = archive.read(entry_names[0]).decode("utf-8", errors="strict")
        if "arx = arx.cli:main" not in entry_points or "arx-desktop = arx.desktop.__main__:main" not in entry_points:
            raise SystemExit("Wheel console entry points are incomplete.")
    wheel_names, wheel_findings = inspect_zip(wheel, markers)
    findings.extend(wheel_findings)
    if not any(name == "arx/__init__.py" for name in wheel_names):
        raise SystemExit("Wheel does not contain the ARX package.")

    sdist_names, sdist_findings = inspect_sdist(sdist, markers)
    findings.extend(sdist_findings)
    sdist_prefix = f"arx_prescanner-{version}/"
    if not all(name == sdist_prefix.rstrip("/") or name.startswith(sdist_prefix) for name in sdist_names):
        raise SystemExit("Source distribution has an unexpected root directory.")
    with tarfile.open(sdist, "r:gz") as archive:
        pkg_info = archive.extractfile(f"arx_prescanner-{version}/PKG-INFO")
        if pkg_info is None:
            raise SystemExit("Source distribution PKG-INFO is missing.")
        require_metadata(pkg_info.read(), version)

    portable_names, portable_findings = inspect_zip(portable, markers)
    findings.extend(portable_findings)
    portable_required = {
        "ARX-Desktop-win-x64/ARX.exe",
        "ARX-Desktop-win-x64/README.txt",
        "ARX-Desktop-win-x64/LICENSE.txt",
    }
    if not portable_required.issubset(portable_names):
        raise SystemExit("Portable archive is missing ARX.exe, README.txt, or LICENSE.txt.")
    if not any(name.startswith("ARX-Desktop-win-x64/_internal/") for name in portable_names):
        raise SystemExit("Portable archive is missing the PyInstaller _internal runtime.")

    if present_security_bundle:
        try:
            sbom_payload = json.loads(sbom.read_text(encoding="utf-8"))
            security_payload = json.loads(security_gates.read_text(encoding="utf-8"))
            reproducibility_payload = json.loads(reproducibility.read_text(encoding="utf-8"))
            signing_payload = json.loads(signing.read_text(encoding="utf-8"))
            lifecycle_payload = json.loads(lifecycle.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Security release JSON is malformed: {type(exc).__name__}") from None
        if sbom_payload.get("bomFormat") != "CycloneDX":
            raise SystemExit("Release SBOM is not CycloneDX JSON.")
        if security_payload.get("record_type") != "arx_release_security_record" or security_payload.get(
            "record_state"
        ) != "FINAL":
            raise SystemExit("Release security record is not FINAL.")
        if reproducibility_payload.get("record_type") != "arx_release_reproducibility":
            raise SystemExit("Reproducibility evidence has an unexpected record type.")
        if signing_payload.get("record_type") != "authenticode_verification":
            raise SystemExit("Signing preflight evidence has an unexpected record type.")
        if lifecycle_payload.get("record_type") != "standard_user_windows_lifecycle_gate":
            raise SystemExit("Lifecycle preparation evidence has an unexpected record type.")
        provenance_names, provenance_findings = inspect_zip(provenance, markers)
        findings.extend(provenance_findings)
        required_provenance = {
            f"ARX-{artifact_version}-provenance/provenance.json",
            f"ARX-{artifact_version}-provenance/{sbom.name}",
            f"ARX-{artifact_version}-provenance/{security_gates.name}",
            f"ARX-{artifact_version}-provenance/{reproducibility.name}",
            f"ARX-{artifact_version}-provenance/{signing.name}",
            f"ARX-{artifact_version}-provenance/{lifecycle.name}",
            f"ARX-{artifact_version}-provenance/{release_notes.name}",
        }
        if not required_provenance.issubset(provenance_names):
            raise SystemExit("Provenance bundle is missing required public evidence.")

    if findings:
        for finding in sorted(set(findings)):
            print(finding)
        raise SystemExit(f"Release artifact privacy scan failed with {len(set(findings))} finding(s); values suppressed.")

    print(f"Release artifacts: PASS ({len(public)} public artifacts; installer={'present' if installer.is_file() else 'not built'})")
    print("SHA-256 manifest: PASS")
    print("Release artifact secret/private-data scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

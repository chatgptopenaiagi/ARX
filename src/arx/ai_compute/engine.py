"""AI compute operations are explicit and never install or repair packages."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from collections import deque
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path

from .worker import SOURCE

DEFAULT_ROOT = Path(r"C:\xampp\WINDOWS-AUTONOMOUS-REPAIR-2026")
AI_NAMES = {"torch", "torchvision", "torchaudio", "numpy", "onnxruntime", "onnxruntime-gpu", "tensorrt"}
_PROBE_LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def redact_text(text):
    text = re.sub(r"(?i)(https?://)[^\s/@]+@", r"\1[REDACTED]@", str(text))
    return re.sub(r"(?i)((?:password|access_token|api_key)\s*[=:]\s*)[^\s;\"}]+", r"\1[REDACTED]", text)


def save(path, value):
    from arx.core.models import serialize
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(redact_text(json.dumps(serialize(value), indent=2, ensure_ascii=False)), encoding="utf-8")
    os.replace(temp, path)


def command(args, timeout=20):
    """Only fixed diagnostic arguments; never invoke a shell or inherit stdin."""
    try:
        p = subprocess.run(args, capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"exit_code": p.returncode, "stdout": redact_text(p.stdout.decode("utf-8", "replace")[:262144]),
                "stderr": redact_text(p.stderr.decode("utf-8", "replace")[:8192])}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exit_code": None, "error": redact_text(str(exc)), "stdout": "", "stderr": ""}


def probe(executable, mode="inventory", *, user_site=False, files=False, timeout=90):
    """Each framework runs in its own interpreter with a fixed workload and deadline.

    -I ignores PYTHONHOME/PYTHONPATH and current-directory imports. User-site
    contexts are separate records, explicitly inserted by the fixed worker.
    A temporary DLL-directory reset prevents PyInstaller's embedded Python DLL
    search path from contaminating a child (restored immediately after spawn).
    """
    config = json.dumps({"mode": mode, "user_site": user_site, "files": files})
    args = [str(executable), "-I", "-B", "-c", SOURCE, config]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="arx-ai-probe-") as cwd:
        # Bound retained output and disk use by reading fixed worker output through
        # pipes; the worker's distribution and file inventory have explicit caps.
        try:
            with _PROBE_LOCK:
                previous = None
                if os.name == "nt" and getattr(sys, "frozen", False):
                    import ctypes
                    kernel = ctypes.windll.kernel32
                    kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
                    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
                    buffer = ctypes.create_unicode_buffer(32768)
                    kernel.GetDllDirectoryW(len(buffer), buffer)
                    previous = buffer.value
                    if not kernel.SetDllDirectoryW(None): raise ctypes.WinError()
                try:
                    p = subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                finally:
                    if previous is not None:
                        kernel.SetDllDirectoryW(previous or None)
            try:
                stdout, stderr = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                p.kill(); stdout, stderr = p.communicate()
                return {"status": "FAILED", "error": f"Probe timed out after {timeout}s", "executable": str(executable)}
            text = stdout.decode("utf-8", "replace")
            marker = next((line[len("ARX_AI_JSON:"):] for line in reversed(text.splitlines()) if line.startswith("ARX_AI_JSON:")), None)
            if p.returncode != 0 or marker is None:
                return {"status": "FAILED", "exit_code": p.returncode, "error": redact_text(stderr.decode("utf-8", "replace")[:4000] or text[:4000]), "executable": str(executable)}
            result = json.loads(marker)
            result.update(status="DETECTED", generated_at=now(), duration_seconds=round(time.monotonic()-started, 3),
                          invocation={"interpreter": str(executable), "isolated": True, "user_site": user_site, "mode": mode},
                          stderr=redact_text(stderr.decode("utf-8", "replace")[:4000]))
            return result
        except (OSError, ValueError) as exc:
            return {"status": "FAILED", "error": redact_text(str(exc)), "executable": str(executable)}


def bounded_walk(roots, *, depth=5, max_entries=12000, seconds=12):
    """BFS with one shared entry/time budget; never follow directory links/junctions."""
    pending = deque((Path(root), 0) for root in roots)
    seen = set(); count = 0; deadline = time.monotonic()+seconds
    skip = {".git", "node_modules", "site-packages", "__pycache__", "private-cold-backup", "private-ssms-settings", "preserved-files", "windows", "$recycle.bin", "pkgs", "conda-meta", "lib", "libs", "dlls", "include", "doc", "docs", "tcl"}
    while pending and count < max_entries and time.monotonic() < deadline:
        folder, level = pending.popleft()
        key = str(folder).casefold()
        if key in seen: continue
        seen.add(key)
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    count += 1
                    if count > max_entries or time.monotonic() >= deadline: return
                    path = Path(entry.path)
                    yield path
                    if level < depth and entry.name.casefold() not in skip and entry.is_dir(follow_symlinks=False):
                        if entry.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()): continue
                        # Windows reparse points also cover junctions on Python <3.12.
                        if getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400: continue
                        pending.append((path, level+1))
        except (OSError, PermissionError):
            continue


def candidates(extra_roots=()):
    found = {}; roots = []; notes = []
    def add(path, source):
        path = Path(path).expanduser()
        if path.is_file() and path.name.lower() in {"python.exe", "python", "python3"}:
            if "windowsapps" in str(path).lower(): return
            if getattr(sys, "frozen", False) and path.resolve() == Path(sys.executable).resolve(): return
            key = str(path.absolute()).casefold()
            found.setdefault(key, {"executable": str(path.absolute()), "sources": []})["sources"].append(source)
    if not getattr(sys, "frozen", False): add(sys.executable, "ARX host interpreter")
    for name in ("python", "python3"):
        if shutil.which(name): add(shutil.which(name), "PATH")
    launcher = shutil.which("py")
    if launcher:
        output = command([launcher, "--list-paths"])
        for line in output["stdout"].splitlines():
            match = re.search(r"([A-Za-z]:\\.*python(?:\d+)?\.exe)\s*$", line, re.I)
            if match: add(match.group(1), "Python launcher")
    if os.name == "nt":
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\Python\PythonCore", 0, winreg.KEY_READ|view) as key:
                        for i in range(min(winreg.QueryInfoKey(key)[0], 64)):
                            version = winreg.EnumKey(key, i)
                            try:
                                with winreg.OpenKey(key, version+r"\InstallPath") as install:
                                    try: path = winreg.QueryValueEx(install, "ExecutablePath")[0]
                                    except OSError: path = str(Path(winreg.QueryValueEx(install, "")[0])/"python.exe")
                                    add(path, "PythonCore registry")
                            except OSError: pass
                except OSError: pass
        system = Path(os.environ.get("SystemDrive", "C:")+"/")
        for path in system.glob("Python*/python.exe"): add(path, "Known system Python directory")
        profiles = [p for p in (system/"Users").glob("*") if p.is_dir() and p.name not in {"All Users", "Default User", "Public", "Default"}][:16]
        for profile in profiles:
            roots += [profile/"AppData/Local/Programs/Python", profile/"miniconda3", profile/"anaconda3", profile/".virtualenvs", profile/".venvs", profile/"source/repos"]
            registry = profile/".conda/environments.txt"
            if registry.is_file():
                for item in registry.read_text(encoding="utf-8", errors="replace").splitlines()[:128]:
                    if item.strip(): add(Path(item.strip())/"python.exe", "Conda environment registry")
        roots += [Path(r"C:\xampp"), Path(r"C:\NVIDIA-AI"), system/"Miniconda3", system/"Anaconda3"]
        if os.environ.get("ProgramData"):
            roots += [Path(os.environ["ProgramData"])/"Miniconda3", Path(os.environ["ProgramData"])/"Anaconda3"]
    for key in ("VIRTUAL_ENV", "CONDA_PREFIX"):
        if os.environ.get(key): roots.append(Path(os.environ[key]))
    # User-selected roots take priority over broad defaults under the shared cap.
    roots = [*(Path(p) for p in extra_roots), *roots]
    for root in roots:
        for relative in ("python.exe", "Scripts/python.exe", ".venv/Scripts/python.exe", "venv/Scripts/python.exe"):
            add(root/relative, "Known environment layout")
    for path in bounded_walk(roots):
        if path.name.lower() in {"python.exe", "python", "python3"} and path.parent.name.lower() not in {"nt", "posix"}:
            add(path, "Bounded known-directory search")
    notes.append("Search: known Python registry/PATH/launcher/profile/Conda/project roots, depth 5, 12,000 entries, 12 seconds; no whole-disk scan. Results are not proof of absence outside searched scope.")
    return list(found.values())[:64], notes


def hardware():
    from arx.machine.gpu_compute import _toolkit_roots, _libraries, _standalone_tensorrt, parse_nvcc_version
    env = dict(os.environ)
    smi = shutil.which("nvidia-smi")
    result = {"generated_at": now(), "nvidia_smi": command([smi, "--query-gpu=name,driver_version,memory.total,memory.free,compute_cap", "--format=csv,noheader"]) if smi else {"status": "UNAVAILABLE"}, "toolkits": [], "standalone_tensorrt": _standalone_tensorrt(env)}
    for root, source in _toolkit_roots(env, env.get("ProgramFiles")):
        nvcc = Path(root)/"bin/nvcc.exe"
        version = command([str(nvcc), "--version"]) if nvcc.exists() else {"stdout": "", "status": "UNAVAILABLE"}
        result["toolkits"].append({"root": root, "source": source, "version": parse_nvcc_version(version.get("stdout", "")), "compiler": version,
                                    "libraries": _libraries(Path(root), ("cudart", "cublas", "cudnn", "nvrtc")), "status": "DETECTED"})
    cudnn_roots = [Path(env[k]) for k in ("CUDNN_PATH", "CUDNN_HOME") if env.get(k)]
    cudnn_roots += [Path(env.get("ProgramFiles", r"C:\Program Files"))/"NVIDIA/CUDNN"]
    result["standalone_cudnn_libraries"] = [str(p) for p in bounded_walk(cudnn_roots, depth=4, max_entries=2000, seconds=3) if p.name.lower().startswith("cudnn") and p.suffix.lower()==".dll"]
    result["note"] = "Toolkit, driver capability and per-environment PyTorch runtime are separate; DLL presence is not successful loading."
    return result


def discover(extra_roots=(), *, interpreters=None):
    discovered, notes = candidates(extra_roots) if interpreters is None else ([{"executable": str(p), "sources": ["Explicit selection"]} for p in interpreters], [])
    environments = []
    for candidate in discovered:
        data = probe(candidate["executable"], timeout=20)
        data.update(candidate)
        prefix = data.get("python", {}).get("prefix")
        base = data.get("python", {}).get("base_prefix")
        data["scope"] = "virtual-environment" if prefix and prefix != base else "conda" if prefix and (Path(prefix)/"conda-meta").is_dir() else "system-or-user-installation"
        data["id"] = hashlib.sha256(candidate["executable"].casefold().encode()).hexdigest()[:16]
        data["user_site"] = False
        if any(p["name"].lower() in {"onnxruntime", "onnxruntime-gpu", "tensorrt"} for p in data.get("packages", [])):
            data["provider_probe"] = probe(candidate["executable"], "providers", timeout=45)
        environments.append(data)
        user_site = data.get("python", {}).get("user_site")
        if prefix == base and user_site and Path(user_site).is_dir():
            separate = probe(candidate["executable"], user_site=True, timeout=20)
            # Keep user-site context only when it actually changes the package set.
            if separate.get("packages") != data.get("packages"):
                separate.update(candidate, scope="user-site", user_site=True, id=data["id"]+"-user")
                environments.append(separate)
    return {"schema_version": "1.0", "generated_at": now(), "environments": environments, "hardware": hardware(), "search_notes": notes, "verification": [], "preservation": []}


def verify(environment, *, benchmark=False):
    result = probe(environment["executable"], "benchmark" if benchmark else "verify", user_site=environment.get("user_site", False), timeout=120)
    result.update(environment_id=environment["id"], executable=environment["executable"])
    required = {"python_core_imports", "torch_import", "torchvision_import", "torchaudio_import", "numpy_interoperability", "gpu_tensor", "gpu_matrix", "cuda_synchronize", "cudnn_convolution"}
    passed = {t["name"] for t in result.get("tests", []) if t.get("outcome")=="PASS"}
    result["health"] = "VERIFIED" if required <= passed else "PARTIAL" if "torch_import" in passed else "FAILED"
    return result


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b""): h.update(chunk)
    return h.hexdigest()


def copy_verified(source, destination):
    source, destination = Path(source), Path(destination)
    before = source.stat()
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with source.open("rb") as inp, destination.open("xb") as out:
        for chunk in iter(lambda: inp.read(4*1024*1024), b""): digest.update(chunk); out.write(chunk)
    after = source.stat()
    original = digest.hexdigest(); copied = sha256(destination)
    if original != copied or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError(f"Source changed or copied hash mismatch: {source}")
    return {"source": str(source), "copy": str(destination), "bytes": before.st_size, "sha256": copied, "status": "PRESERVED", "verified": True}


def cached_wheels(packages):
    wanted = {(p["name"].lower().replace("_", "-"), p["version"]) for p in packages}
    cache = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/".cache")))/"pip/Cache"
    records = []
    for path in bounded_walk([cache], depth=8, max_entries=15000, seconds=15):
        if path.suffix.lower() not in {".whl", ".body"}: continue
        try:
            if not zipfile.is_zipfile(path): continue
            with zipfile.ZipFile(path) as wheel:
                names = wheel.namelist()
                metadata = next((n for n in names if n.endswith(".dist-info/METADATA")), None)
                wheel_meta = next((n for n in names if n.endswith(".dist-info/WHEEL")), None)
                if not metadata or not wheel_meta or wheel.getinfo(metadata).file_size > 262144: continue
                package = Parser().parsestr(wheel.read(metadata).decode("utf-8", "replace"))
                name, version = package.get("Name", ""), package.get("Version", "")
                if (name.lower().replace("_", "-"), version) not in wanted: continue
                if wheel.getinfo(wheel_meta).file_size > 65536: continue
                tag = Parser().parsestr(wheel.read(wheel_meta).decode()).get("Tag", "")
                filename = f"{name.replace('-', '_')}-{version}-{tag}.whl"
                if not re.fullmatch(r"[A-Za-z0-9_.+!-]+\.whl", filename): continue
                records.append({"source": str(path), "filename": filename, "name": name, "version": version, "tag": tag, "status": "DETECTED"})
        except (OSError, zipfile.BadZipFile, UnicodeError): continue
    return records


def preserve(environment, destination=None, *, progress=None, cancel=None):
    base = Path(destination or DEFAULT_ROOT)
    base.mkdir(parents=True, exist_ok=True)
    target = base/("AI-preservation-"+datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:8])
    data = probe(environment["executable"], files=True, user_site=environment.get("user_site", False), timeout=45)
    if data.get("status") == "FAILED": raise RuntimeError(data.get("error"))
    prefix = Path(data["python"]["prefix"]).resolve()
    roots = {prefix, *(Path(p["root"]).resolve() for p in data["packages"])}
    # Some existing Windows installations relocate Scripts through a junction.
    # Trust only the interpreter's sysconfig script root, never arbitrary RECORD escapes.
    if data["python"].get("scripts_path"):
        roots.add(Path(data["python"]["scripts_path"]).resolve())
    if any(target.resolve().is_relative_to(root) for root in roots):
        raise ValueError("Preservation destination must be outside the source environment/package roots")
    sources = {}; rejected = []
    for package in data["packages"]:
        if package.get("files_truncated"):
            rejected.append({"package": package["name"], "reason": "Package file inventory exceeded 100,000-file bound"})
        if package.get("files_unavailable"):
            rejected.append({"package": package["name"], "reason": "No installed package file inventory available; preservation is incomplete"})
        for name in package.get("files", []):
            path = Path(name).resolve()
            if not any(path.is_relative_to(root) for root in roots):
                rejected.append({"path": str(path), "reason": "Distribution RECORD escapes package/interpreter roots"}); continue
            if path.is_file(): sources[str(path).casefold()] = path
            elif path.suffix != ".pyc": rejected.append({"path": str(path), "reason": "Recorded package file is missing"})
    # Preserve runtime identifiers/artifacts too; this is not a portable Python installation.
    for path in [Path(environment["executable"]), *prefix.glob("python*.dll"), prefix/"pyvenv.cfg"]:
        if path.is_file(): sources[str(path).casefold()] = path
    wheels = cached_wheels(data["packages"])
    needed = sum(p.stat().st_size for p in sources.values())+sum(Path(w["source"]).stat().st_size for w in wheels)
    if shutil.disk_usage(base).free < needed + 1024**3: raise OSError("Insufficient space for copies plus 1 GiB reserve")
    target.mkdir()
    result = {"schema_version": "1.0", "generated_at": now(), "environment_id": environment["id"], "python": data["python"], "destination": str(target), "status": "UNTESTED", "packages": [{k:v for k,v in p.items() if k!="files"} for p in data["packages"]], "files": [], "wheels": [], "issues": rejected, "estimated_bytes": needed, "portable": False}
    save(target/"PACKAGE-MANIFEST.json", result["packages"])
    requirements = [p["name"]+"=="+p["version"] for p in data["packages"] if re.fullmatch(r"[A-Za-z0-9_.-]+",p["name"]) and re.fullmatch(r"[A-Za-z0-9_.+!-]+",p["version"])]
    (target/"requirements-pinned.txt").write_text("\n".join(requirements)+"\n", encoding="utf-8")
    try:
        for index, source in enumerate(sources.values()):
            if cancel and cancel(): raise InterruptedError("Preservation cancelled; completed copies retained")
            root = next(root for root in sorted(roots, key=lambda p:len(str(p)), reverse=True) if source.is_relative_to(root))
            key = hashlib.sha256(str(root).casefold().encode()).hexdigest()[:12]
            destination_file = target/"preserved-files"/key/source.relative_to(root)
            result["files"].append(copy_verified(source, destination_file))
            if progress and index % 100 == 0: progress(index+1, len(sources))
        for wheel in wheels:
            destination_file = target/"wheels"/wheel["filename"]
            if destination_file.exists(): continue
            result["wheels"].append({**wheel, **copy_verified(wheel["source"], destination_file)})
        result["status"] = "PRESERVED" if not result["issues"] else "PARTIAL"
    except Exception as exc:
        result["status"] = "FAILED";result["issues"].append({"error": redact_text(str(exc))})
    result["copied_bytes"] = sum(f["bytes"] for f in result["files"]+result["wheels"])
    result["completed_at"] = now()
    save(target/"ARX-AI-PRESERVATION-MANIFEST.json", result)
    (target/"RESTORE.md").write_text(
        "# Restoration procedure\n\nThese are evidence and recovery copies, not a portable Python distribution. Do not overwrite a working environment.\n\n"
        "1. Verify every copy against SHA-256 in ARX-AI-PRESERVATION-MANIFEST.json. Retain the originals.\n"
        "2. Install the same CPython major/minor and architecture in a separate location if the original runtime is unavailable. Preserve the original installer and use official Python distribution sources. Copied python.exe/DLLs alone are insufficient.\n"
        "3. Create a NEW virtual environment with that interpreter. Review PACKAGE-MANIFEST.json and pinned requirements, including CUDA build suffixes.\n"
        "4. If ALL required compatible wheels are preserved, run NEW_PYTHON -m pip install --no-index --find-links PATH_TO_WHEELS -r requirements-pinned.txt. Missing wheel coverage is not an offline restore success; obtain exact compatible wheels from official PyPI/PyTorch sources if required.\n"
        "5. Package-file copies are a forensic fallback, not an installer. RECORD paths, compiled extensions, scripts, ABI, DLL search paths and dependencies must be accounted for. Do not copy this tree wholesale into another Python.\n"
        "6. Run ARX AI Compute verification in the restored environment, including CUDA matrix, explicit cuDNN convolution, NumPy and companion imports. A successful copy does not verify a restore.\n\n"
        "The NVIDIA driver and system CUDA Toolkit are inventoried separately and not contained in this snapshot. Restore was NOT TESTED.\n", encoding="utf-8")
    return result


def write_reports(report, destination):
    out = Path(destination); out.mkdir(parents=True, exist_ok=True)
    results = report.get("verification", [])
    save(out/"ARX-AI-ENVIRONMENT-INVENTORY.json", {k:v for k,v in report.items() if k not in {"verification", "preservation"}})
    save(out/"ARX-PYTORCH-INSTALLATIONS.json", [{"environment_id": e["id"], "executable":e["executable"], "scope":e["scope"], "packages":[p for p in e.get("packages",[]) if p["name"].lower() in AI_NAMES]} for e in report["environments"]])
    save(out/"ARX-CUDA-CUDNN-INVENTORY.json", {"hardware":report["hardware"], "environments":[{"environment_id":r["environment_id"], "torch":r.get("torch"), "gpu":r.get("gpu"), "runtime_libraries":r.get("runtime_libraries",[])} for r in results]})
    save(out/"ARX-GPU-FUNCTIONAL-TESTS.json", results)
    save(out/"ARX-AI-COMPUTE-BENCHMARKS.json", [{"environment_id":r["environment_id"], "benchmarks":r.get("benchmarks",[])} for r in results])
    save(out/"ARX-AI-PRESERVATION-MANIFEST.json", report.get("preservation", []))
    lines = ["# ARX AI Compute verification", "", "Generated: "+now(), "", "Evidence states: DETECTED / INSTALLED / IMPORTABLE / FUNCTIONAL / BENCHMARKED / PRESERVED / UNAVAILABLE / UNTESTED / FAILED.", "", "| Interpreter | Environment health | Torch CUDA | cuDNN code |", "|---|---|---|---|"]
    for result in results:
        torch = result.get("torch", {})
        lines.append(f"| {result['executable']} | {result['health']} | {torch.get('cuda_runtime','Unknown')} | {torch.get('cudnn_version','Unknown')} |")
    lines += ["", "Each environment is independent. Missing companion packages do not invalidate a working torch installation; overall VERIFIED requires all required checks. Provider enumeration and DLL/version detection do not prove GPU inference or cuDNN execution.", "", "Benchmarks are short synchronized microbenchmarks (one warmup, three samples), not sustained performance or application-throughput claims. Driver/context memory is outside the torch allocator peak. Tests run on CUDA device 0; other GPUs are inventoried but not tested.", "", "Preservation: "+", ".join(p["status"] for p in report.get("preservation", [])), "", "Restoration has not been tested. Consult the snapshot RESTORE.md before any recovery."]
    (out/"ARX-AI-FINAL-VERIFICATION.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return out

"""Layered, deterministic NVIDIA/CUDA machine intelligence.

Driver capability, toolkits, runtime libraries, frameworks, resolution, and
project suitability are intentionally separate facts.  No detector in this
module treats the CUDA level printed by nvidia-smi as an installed toolkit.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

from arx.core.models import Evidence, EvidenceKind, utc_now
from arx.core.subprocess import run_bounded

MAX_OUTPUT = 64 * 1024
PROBE_TIMEOUT = 8
CUDA_LIBRARY_NAMES = ("cudart", "cublas", "cufft", "cusolver", "cusparse", "nvrtc")
KNOWLEDGE_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "gpu_compatibility.json"


def _evidence(kind: EvidenceKind, source: str, value: object, method: str, confidence: float = 1.0, note: str | None = None) -> Evidence:
    return Evidence(kind, source, value, method, confidence, note)


def load_gpu_knowledge() -> dict:
    """Load versioned local semantic rules; normal scans never fetch knowledge."""
    try:
        return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "unknown", "rules": []}


def _run(args: list[str], timeout: int = PROBE_TIMEOUT) -> dict:
    try:
        result = run_bounded(args, timeout=timeout, limit=MAX_OUTPUT, runner=subprocess.run)
        return {
            "ok": result["returncode"] == 0,
            "exit_code": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": "", "error": "timeout"}
    except OSError as exc:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": "", "error": type(exc).__name__}


def parse_nvidia_smi_summary(text: str) -> dict:
    driver = re.search(r"(?:Driver|KMD) Version:\s*([0-9.]+)", text, re.I)
    ceiling = re.search(r"CUDA(?: UMD)? Version:\s*([0-9.]+)", text, re.I)
    return {
        "driver_version": driver.group(1) if driver else None,
        "cuda_driver_capability": ceiling.group(1) if ceiling else None,
    }


def parse_nvidia_smi_gpus(text: str) -> list[dict]:
    records = []
    for line in text.splitlines():
        fields = [item.strip() for item in line.split(",")]
        if len(fields) < 6:
            continue
        memory = re.search(r"\d+", fields[4])
        records.append(
            {
                "name": fields[0] or None,
                "uuid": fields[1] or None,
                "pci_bus_id": fields[2] or None,
                "driver_version": fields[3] or None,
                "dedicated_vram_bytes": int(memory.group()) * 1024 * 1024 if memory else None,
                "compute_capability": fields[5] if re.fullmatch(r"\d+\.\d+", fields[5]) else None,
                "visible_to_nvidia_tooling": True,
            }
        )
    return records


def parse_nvcc_version(text: str) -> str | None:
    match = re.search(r"release\s+(\d+\.\d+)", text, re.I)
    return match.group(1) if match else None


def resource_pressure(total: int | None, available: int | None, *, kind: str) -> dict:
    if not total or available is None or total <= 0 or available < 0:
        return {"state": "unknown", "used_bytes": None, "percent_used": None, "percent_free": None}
    used = max(total - available, 0)
    free_percent = available * 100.0 / total
    used_percent = used * 100.0 / total
    if kind == "disk":
        state = "critical" if free_percent < 5 or available < 5 * 1024**3 else "low" if free_percent < 15 or available < 20 * 1024**3 else "normal"
    else:
        state = "critical" if free_percent < 5 else "low" if free_percent < 15 else "normal"
    return {"state": state, "used_bytes": used, "percent_used": round(used_percent, 2), "percent_free": round(free_percent, 2)}


def disk_preflight(free_bytes: int | None, *, download_bytes: int | None = None, extracted_bytes: int | None = None, install_bytes: int | None = None, temporary_bytes: int | None = None) -> dict:
    parts = {"download_bytes": download_bytes, "extracted_bytes": extracted_bytes, "install_bytes": install_bytes, "temporary_bytes": temporary_bytes}
    known = [value for value in parts.values() if isinstance(value, int) and value >= 0]
    if free_bytes is None or not known:
        return {**parts, "free_bytes": free_bytes, "required_bytes": sum(known) if known else None, "state": "unknown", "reason": "Free space or required workflow sizes are incomplete"}
    required = sum(known)
    return {**parts, "free_bytes": free_bytes, "required_bytes": required, "state": "green" if free_bytes >= required else "red", "reason": "Known disk requirements fit" if free_bytes >= required else "Known disk requirements exceed free space"}


def _version_from_path(path: Path) -> str | None:
    match = re.search(r"(?:[\\/]v|TensorRT-)(\d+\.\d+(?:\.\d+){0,2})(?:[\\/]|$)", str(path), re.I)
    return match.group(1) if match else None


def _toolkit_roots(env: dict[str, str], program_files: str | None) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for key, value in env.items():
        if key.upper() == "CUDA_PATH" or re.fullmatch(r"CUDA_PATH_V\d+_\d+", key.upper()):
            if value:
                candidates.append((value, f"environment:{key}"))
    root = Path(program_files) / "NVIDIA GPU Computing Toolkit" / "CUDA" if program_files else None
    if root and root.is_dir():
        try:
            candidates.extend((str(item), "known CUDA installation directory") for item in root.iterdir() if item.is_dir() and re.fullmatch(r"v\d+\.\d+", item.name, re.I))
        except OSError:
            pass
    unique: dict[str, tuple[str, str]] = {}
    for path, source in candidates:
        unique.setdefault(str(Path(path).resolve(strict=False)).casefold(), (str(Path(path).resolve(strict=False)), source))
    return list(unique.values())[:16]


def _libraries(root: Path, names: Iterable[str]) -> list[dict]:
    results = []
    for folder in (root / "bin", root / "lib" / "x64", root / "lib"):
        if not folder.is_dir():
            continue
        try:
            entries = list(folder.iterdir())[:2048]
        except OSError:
            continue
        for name in names:
            match = next((item for item in entries if item.is_file() and item.name.lower().startswith(name) and item.suffix.lower() in {".dll", ".lib"}), None)
            if match:
                runtime = match.suffix.lower() == ".dll"
                results.append({"component": name, "path": str(match), "version": _version_from_path(match), "architecture": "x64", "scope": "global-toolkit", "artifact_kind": "runtime_library" if runtime else "import_library", "runtime_loadable": runtime, "development_link_role": not runtime})
    return results


def _tensorrt_roots(env: dict[str, str]) -> list[tuple[Path, list[str]]]:
    candidates: list[tuple[Path, str]] = []
    for key in ("TENSORRT_ROOT", "TENSORRT_HOME", "TRT_ROOT"):
        if env.get(key):
            candidates.append((Path(env[key]), f"environment:{key}"))
    path_value = env.get("PATH", "")
    separator = ";" if ";" in path_value else os.pathsep
    for entry in path_value.split(separator):
        if entry and "tensorrt" in entry.casefold():
            path = Path(entry)
            candidates.append((path.parent if path.name.casefold() in {"bin", "lib"} else path, "PATH entry"))
    known = Path(env.get("NVIDIA_AI_ROOT", r"C:\NVIDIA-AI"))
    if known.is_dir():
        try:
            candidates.extend((item, "bounded NVIDIA-AI root") for item in list(known.iterdir())[:64] if item.is_dir() and item.name.casefold().startswith("tensorrt-"))
        except OSError:
            pass
    unique: dict[str, tuple[Path, list[str]]] = {}
    for root, source in candidates:
        key = str(root.resolve(strict=False)).casefold()
        if key not in unique:
            unique[key] = (root.resolve(strict=False), [source])
        elif source not in unique[key][1]:
            unique[key][1].append(source)
    return list(unique.values())[:16]


def _standalone_tensorrt(env: dict[str, str]) -> dict:
    runtime: list[dict] = []
    imports: list[dict] = []
    providers: list[dict] = []
    for root, sources in _tensorrt_roots(env):
        artifacts = _libraries(root, ("nvinfer", "nvonnxparser"))
        if not artifacts:
            continue
        version = _version_from_path(root)
        providers.append({"root": str(root), "version": version, "version_source": "installation_directory_name" if version else "unknown", "sources": sources, "resolution": "resolved" if any(str(root / "bin").casefold() == item.casefold() for item in env.get("PATH", "").split(";")) else "available", "compatibility": "unknown", "evidence": [_evidence(EvidenceKind.OBSERVED, ", ".join(sources), {"root": str(root), "version": version}, "bounded TensorRT provider discovery")]})
        runtime.extend(item for item in artifacts if item["runtime_loadable"])
        imports.extend(item for item in artifacts if item["development_link_role"])
    return {"native_providers": providers, "runtime_libraries": runtime, "import_libraries": imports}


def _select_framework_python(explicit: str | None, providers: list[dict] | None) -> str | None:
    frozen_self = bool(getattr(sys, "frozen", False))
    if explicit and not (frozen_self and Path(explicit).resolve(strict=False) == Path(sys.executable).resolve(strict=False)):
        return explicit
    for provider in providers or []:
        path = provider.get("path")
        if provider.get("healthy") is True and path and "windowsapps" not in str(path).casefold():
            return str(path)
    if not frozen_self and sys.executable and Path(sys.executable).name.casefold().startswith("python"):
        return sys.executable
    return None


def _framework_probe(python: str, runner: Callable[[list[str], int], dict]) -> dict:
    script = r'''import importlib.util,json
r={"python":__import__("sys").executable}
if importlib.util.find_spec("torch"):
 import torch
 t={"installed":True,"version":getattr(torch,"__version__",None),"compiled_cuda":getattr(getattr(torch,"version",None),"cuda",None)}
 try:
  t["cuda_available"]=bool(torch.cuda.is_available());t["device_count"]=int(torch.cuda.device_count())
  t["devices"]=[{"name":torch.cuda.get_device_name(i),"compute_capability":"%d.%d"%torch.cuda.get_device_capability(i)} for i in range(t["device_count"])] if t["cuda_available"] else []
  arches=getattr(torch.cuda,"get_arch_list",lambda:[])();t["compiled_architectures"]=list(arches)
 except Exception as e:t.update(cuda_available=False,initialization_error=type(e).__name__)
 r["pytorch"]=t
if importlib.util.find_spec("onnxruntime"):
 import onnxruntime as ort;r["onnxruntime"]={"installed":True,"version":ort.__version__,"providers":ort.get_available_providers(),"gpu_provider_available":"CUDAExecutionProvider" in ort.get_available_providers()}
if importlib.util.find_spec("tensorrt"):
 import tensorrt as trt;r["tensorrt_python"]={"installed":True,"version":trt.__version__}
print(json.dumps(r,separators=(",",":")))'''
    result = runner([python, "-I", "-c", script], PROBE_TIMEOUT)
    if not result["ok"]:
        return {"probe_status": "unknown", "error": result["error"] or f"exit {result['exit_code']}", "evidence": [_evidence(EvidenceKind.UNKNOWN, python, result["error"] or result["stderr"][:300], "fixed isolated framework probe", .5)]}
    try:
        parsed = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"probe_status": "unknown", "error": "malformed output", "evidence": [_evidence(EvidenceKind.UNKNOWN, python, "malformed output", "fixed isolated framework probe", .4)]}
    parsed["probe_status"] = "observed"
    parsed["tested_python_provider"] = python
    parsed["evidence"] = [_evidence(EvidenceKind.OBSERVED, python, "framework inventory returned", "fixed isolated framework probe")]
    pytorch = parsed.get("pytorch")
    if pytorch:
        pytorch["build_kind"] = "cuda" if pytorch.get("compiled_cuda") else "cpu-only"
        pytorch["initialization_status"] = "pass" if pytorch.get("cuda_available") else "fail"
        pytorch["architecture_status"] = _pytorch_architecture_status(pytorch)
        pytorch["vram_feasibility"] = {"state": "unknown", "reason": "No project workload VRAM requirement was observed"}
    else:
        parsed["pytorch"] = {"installed": False, "probe_status": "absent_in_tested_provider", "python_provider": python}
    if "onnxruntime" not in parsed:
        parsed["onnxruntime"] = {"installed": False, "probe_status": "absent_in_tested_provider", "python_provider": python}
    if "tensorrt_python" not in parsed:
        parsed["tensorrt_python"] = {"installed": False, "probe_status": "absent_in_tested_provider", "python_provider": python}
    return parsed


def _pytorch_architecture_status(pytorch: dict) -> dict:
    devices = pytorch.get("devices") or []
    arches = {str(value).lower().replace("sm_", "").replace("compute_", "").replace(".", "") for value in (pytorch.get("compiled_architectures") or [])}
    if not devices:
        return {"state": "unknown", "reason": "No initialized CUDA device exposed compute capability"}
    capabilities = {str(item.get("compute_capability", "")).replace(".", "") for item in devices}
    if not arches:
        return {"state": "yellow", "reason": "CUDA initialized, but compiled SM architecture coverage was not reported"}
    unsupported = capabilities - arches
    return {"state": "red" if unsupported else "green", "reason": f"Compiled architecture list {'excludes ' + ', '.join(sorted(unsupported)) if unsupported else 'explicitly includes detected devices'}"}


def detect_gpu_compute(windows_gpus: object, *, env: dict[str, str] | None = None, runner: Callable[[list[str], int], dict] = _run, python_executable: str | None = None, python_providers: list[dict] | None = None, msvc: dict | None = None) -> dict:
    env = dict(os.environ if env is None else env)
    smi = shutil.which("nvidia-smi")
    nvcc = shutil.which("nvcc")
    gpus = windows_gpus if isinstance(windows_gpus, list) else [windows_gpus] if windows_gpus else []
    hardware = [{"name": item.get("Name"), "pnp_device_id": item.get("PNPDeviceID"), "dedicated_vram_bytes": item.get("AdapterRAM"), "windows_driver_version": item.get("DriverVersion"), "video_processor": item.get("VideoProcessor"), "visible_to_windows": True, "compute_capability": None, "evidence": [_evidence(EvidenceKind.OBSERVED, "Win32_VideoController", item.get("Name"), "bounded CIM query")]} for item in gpus if isinstance(item, dict)]

    driver = {"installed": bool(smi), "nvidia_smi": {"available": bool(smi), "resolved_path": smi, "execution_health": "not_found" if not smi else "unknown"}, "version": None, "cuda_driver_capability": None, "nvml_available": None, "evidence": []}
    nvidia_gpus: list[dict] = []
    if smi:
        summary_result = runner([smi], PROBE_TIMEOUT)
        query_result = runner([smi, "--query-gpu=name,uuid,pci.bus_id,driver_version,memory.total,compute_cap", "--format=csv,noheader,nounits"], PROBE_TIMEOUT)
        summary = parse_nvidia_smi_summary(summary_result["stdout"] + summary_result["stderr"])
        driver.update(version=summary["driver_version"], cuda_driver_capability=summary["cuda_driver_capability"], nvml_available=summary_result["ok"] or query_result["ok"])
        driver["nvidia_smi"]["execution_health"] = "healthy" if summary_result["ok"] else "failed"
        driver["evidence"].append(_evidence(EvidenceKind.OBSERVED if summary_result["ok"] else EvidenceKind.UNKNOWN, smi, {"driver_version": driver["version"], "cuda_driver_capability": driver["cuda_driver_capability"]}, "fixed nvidia-smi summary probe", 1.0 if summary_result["ok"] else .5, "Driver CUDA capability is not toolkit installation evidence"))
        if query_result["ok"]:
            nvidia_gpus = parse_nvidia_smi_gpus(query_result["stdout"])

    roots = _toolkit_roots(env, env.get("ProgramFiles"))
    if nvcc:
        nvcc_root = str(Path(nvcc).resolve(strict=False).parent.parent)
        roots.append((nvcc_root, "resolved nvcc"))
    toolkit_map: dict[str, dict] = {}
    for root_value, source in roots:
        root = Path(root_value)
        key = str(root.resolve(strict=False)).casefold()
        nvcc_path = root / "bin" / "nvcc.exe"
        version = _version_from_path(root)
        health = "not_resolved"
        if nvcc_path.is_file():
            result = runner([str(nvcc_path), "--version"], PROBE_TIMEOUT)
            version = parse_nvcc_version(result["stdout"] + result["stderr"]) or version
            health = "healthy" if result["ok"] else "probe_failed"
        libraries = _libraries(root, CUDA_LIBRARY_NAMES)
        toolkit_map[key] = {"version": version, "root": str(root), "nvcc_path": str(nvcc_path) if nvcc_path.is_file() else None, "health": health, "source": source, "selected_by_cuda_path": str(root).casefold() == str(env.get("CUDA_PATH", "")).casefold(), "resolved": bool(nvcc and Path(nvcc).resolve(strict=False) == nvcc_path.resolve(strict=False)), "runtime_libraries": [item for item in libraries if item["runtime_loadable"]], "import_libraries": [item for item in libraries if item["development_link_role"]], "component_inventory": libraries, "evidence": [_evidence(EvidenceKind.OBSERVED, source, str(root), "bounded environment/known-directory discovery")]}
    toolkits = list(toolkit_map.values())
    cudnn_inventory = [item for toolkit in toolkits for item in _libraries(Path(toolkit["root"]), ("cudnn",))]
    toolkit_tensorrt = [item for toolkit in toolkits for item in _libraries(Path(toolkit["root"]), ("nvinfer", "nvonnxparser"))]
    standalone_tensorrt = _standalone_tensorrt(env)
    python = _select_framework_python(python_executable, python_providers)
    frameworks = _framework_probe(python, runner) if python else {"probe_status": "not_tested", "reason": "no usable Python provider resolved for framework probe", "tested_python_provider": None, "pytorch": {"installed": None, "probe_status": "not_tested"}, "onnxruntime": {"installed": None, "probe_status": "not_tested"}, "tensorrt_python": {"installed": None, "probe_status": "not_tested"}, "evidence": [_evidence(EvidenceKind.UNKNOWN, "Python provider inventory", "not tested", "framework probe provider selection", 1.0, "No healthy real Python provider resolved")]}

    contradictions = []
    windows_nvidia = any("nvidia" in str(item.get("name", "")).casefold() for item in hardware)
    if windows_nvidia and not nvidia_gpus:
        contradictions.append({"code": "windows_gpu_not_visible_to_nvidia_smi", "state": "yellow", "reason": "Windows reports an NVIDIA GPU but NVIDIA tooling did not enumerate it"})
    if driver["nvidia_smi"]["execution_health"] == "healthy" and not toolkits:
        contradictions.append({"code": "driver_without_toolkit", "state": "informational", "reason": "NVIDIA driver capability is present but no CUDA Toolkit was detected; this is not inherently an error"})
    selected = next((item for item in toolkits if item["selected_by_cuda_path"]), None)
    resolved = next((item for item in toolkits if item["resolved"]), None)
    if selected and resolved and selected["root"].casefold() != resolved["root"].casefold():
        contradictions.append({"code": "cuda_path_nvcc_mismatch", "state": "yellow", "reason": f"CUDA_PATH selects {selected['root']} while nvcc resolves from {resolved['root']}"})
    pytorch = frameworks.get("pytorch") or {}
    if pytorch.get("compiled_cuda") and pytorch.get("cuda_available") is False:
        contradictions.append({"code": "pytorch_cuda_build_unavailable", "state": "yellow", "reason": "PyTorch has a CUDA build but CUDA backend initialization failed"})
    windows_nvidia_gpus = [item for item in hardware if "nvidia" in str(item.get("name", "")).casefold()]
    if len(windows_nvidia_gpus) == 1 and len(nvidia_gpus) == 1:
        windows_nvidia_gpu = windows_nvidia_gpus[0]
        windows_vram = windows_nvidia_gpu.get("dedicated_vram_bytes")
        nvidia_vram = nvidia_gpus[0].get("dedicated_vram_bytes")
        if isinstance(windows_vram, int) and isinstance(nvidia_vram, int) and abs(windows_vram - nvidia_vram) >= 256 * 1024**2:
            contradictions.append({"code": "GPU_VRAM_SOURCE_DISAGREEMENT", "state": "yellow", "subject": nvidia_gpus[0].get("uuid") or nvidia_gpus[0].get("name"), "observations": [{"source": "Win32_VideoController.AdapterRAM", "value_bytes": windows_vram}, {"source": "nvidia-smi memory.total", "value_bytes": nvidia_vram}], "difference_bytes": abs(windows_vram - nvidia_vram), "interpretation": "WMI AdapterRAM can be limited or unreliable for modern adapters; healthy NVIDIA tooling is preferred for NVIDIA operational reporting", "remaining_uncertainty": "Single-device correlation lacks a shared PCI identifier from WMI"})
    msvc = msvc or {}
    entry_available = msvc.get("developer_environment_entry_point", {}).get("available")
    if nvcc and msvc.get("provider_installed") and not msvc.get("current_resolution", {}).get("resolved") and entry_available:
        contradictions.append({"code": "CUDA_HOST_COMPILER_CONTEXT_UNRESOLVED", "state": "yellow", "reason": "CUDA Toolkit resolves, but cl.exe does not resolve in the current process; a supported Visual Studio developer environment entry point is available", "recoverable_context": msvc.get("recoverable_context"), "automatic_activation": False})

    cuda_runtime_libraries = [item for toolkit in toolkits for item in toolkit["runtime_libraries"]]
    cuda_import_libraries = [item for toolkit in toolkits for item in toolkit["import_libraries"]]
    trt_runtime = [item for item in toolkit_tensorrt if item["runtime_loadable"]] + standalone_tensorrt["runtime_libraries"]
    trt_imports = [item for item in toolkit_tensorrt if item["development_link_role"]] + standalone_tensorrt["import_libraries"]

    return {
        "schema_version": "1.0",
        "knowledge": {key: value for key, value in load_gpu_knowledge().items() if key != "rules"},
        "generated_at": utc_now(),
        "semantics": {"driver_cuda_capability_is_toolkit": False, "confidence": "detector-authored heuristic weight; not a calibrated probability", "verification": "semantic verification is separate from EvidenceKind"},
        "gpus": hardware,
        "nvidia_tooling_gpus": nvidia_gpus,
        "selected_gpu": nvidia_gpus[0] if len(nvidia_gpus) == 1 else None,
        "nvidia_driver": driver,
        "cuda_driver_capability": {"version": driver["cuda_driver_capability"], "meaning": "maximum CUDA API/runtime compatibility level advertised by the NVIDIA driver; not an installed Toolkit", "evidence_refs": ["nvidia_driver.evidence"] if driver["cuda_driver_capability"] else []},
        "cuda_toolkits": toolkits,
        "cuda_runtimes": cuda_runtime_libraries,
        "cuda_import_libraries": cuda_import_libraries,
        "cudnn": {"runtime_providers": [item for item in cudnn_inventory if item["runtime_loadable"]], "import_libraries": [item for item in cudnn_inventory if item["development_link_role"]], "status": "present" if cudnn_inventory else "unknown"},
        "tensorrt": {**standalone_tensorrt, "runtime_libraries": trt_runtime, "import_libraries": trt_imports, "python": frameworks.get("tensorrt_python"), "status": "present" if trt_runtime or trt_imports or (frameworks.get("tensorrt_python") or {}).get("installed") else "unknown", "compatibility": "unknown"},
        "frameworks": frameworks,
        "resolution": {"nvidia_smi": smi, "nvcc": nvcc, "cuda_path": env.get("CUDA_PATH"), "python": python, "framework_probe": "not_tested" if not python else "executed"},
        "msvc_context": msvc,
        "contradictions": contradictions,
        "dimensions": {"presence": "green" if hardware or nvidia_gpus else "unknown", "health": "green" if driver["nvidia_smi"]["execution_health"] == "healthy" else "unknown", "resolution": "green" if nvcc else "unknown", "compatibility": "unknown", "project_relevance": "unknown", "resource_feasibility": "unknown", "verification_level": "observed_and_inferred" if smi else "unknown"},
    }


def analyze_resources(memory: dict | None, storage: object) -> dict:
    memory = memory or {}
    memory_result = {**memory, **resource_pressure(memory.get("total_bytes"), memory.get("available_bytes"), kind="memory"), "meaning": "current resource pressure, not permanent incompatibility"}
    volumes = storage if isinstance(storage, list) else [storage] if storage else []
    disk_results = []
    for volume in volumes:
        if not isinstance(volume, dict):
            continue
        total = volume.get("Size")
        free = volume.get("SizeRemaining")
        disk_results.append({"drive": volume.get("DriveLetter"), "total_bytes": total, "free_bytes": free, **resource_pressure(total, free, kind="disk"), "consequences": ["extraction/build space", "package installation", "temporary files", "model downloads", "Windows Update"]})
    system_drive = os.environ.get("SystemDrive", "C:").rstrip(":").casefold()
    selected = next((item for item in disk_results if str(item.get("drive", "")).casefold() == system_drive), disk_results[0] if disk_results else None)
    return {"memory": memory_result, "volumes": disk_results, "system_drive": selected, "disk_preflight": disk_preflight(selected.get("free_bytes") if selected else None)}

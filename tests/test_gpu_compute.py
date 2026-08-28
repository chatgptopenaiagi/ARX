from pathlib import Path

import pytest

from arx.machine.gpu_compute import (
    _framework_probe,
    _libraries,
    _pytorch_architecture_status,
    detect_gpu_compute,
    disk_preflight,
    parse_nvidia_smi_gpus,
    parse_nvidia_smi_summary,
    parse_nvcc_version,
    resource_pressure,
)
from arx.project.scanner import inspect_project


def result(stdout="", *, ok=True, error=None):
    return {"ok": ok, "exit_code": 0 if ok else None, "stdout": stdout, "stderr": "", "error": error}


def test_driver_cuda_capability_is_never_an_installed_toolkit(monkeypatch):
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: r"C:\NVIDIA\nvidia-smi.exe" if name == "nvidia-smi" else None)

    def runner(args, timeout):
        if any(item.startswith("--query-gpu") for item in args):
            return result("NVIDIA RTX Test, GPU-1, 00000000:01:00.0, 590.00, 16384, 8.9\n")
        return result("NVIDIA-SMI 590.00 Driver Version: 590.00 CUDA Version: 13.3")

    report = detect_gpu_compute([{"Name": "NVIDIA RTX Test", "AdapterRAM": 2**32}], env={}, runner=runner)
    assert report["cuda_driver_capability"]["version"] == "13.3"
    assert report["cuda_toolkits"] == []
    assert report["semantics"]["driver_cuda_capability_is_toolkit"] is False
    assert "not an installed Toolkit" in report["cuda_driver_capability"]["meaning"]


def test_nvidia_parsers_preserve_multiple_gpus_and_unknown_architecture():
    summary = parse_nvidia_smi_summary("Driver Version: 560.10 CUDA Version: 12.8")
    gpus = parse_nvidia_smi_gpus("GPU A, UUID-A, 01:00.0, 560.10, 8192, 8.6\nGPU B, UUID-B, 02:00.0, 560.10, 24576, N/A")
    assert summary == {"driver_version": "560.10", "cuda_driver_capability": "12.8"}
    assert len(gpus) == 2
    assert gpus[0]["compute_capability"] == "8.6"
    assert gpus[1]["compute_capability"] is None


def test_nvidia_parser_supports_current_kmd_umd_labels():
    assert parse_nvidia_smi_summary("NVIDIA-SMI 616.56 KMD Version: 616.56 CUDA UMD Version: 13.4") == {
        "driver_version": "616.56",
        "cuda_driver_capability": "13.4",
    }


def test_nvcc_parser_rejects_unrelated_version_text():
    assert parse_nvcc_version("Cuda compilation tools, release 13.0, V13.0.1") == "13.0"
    assert parse_nvcc_version("driver CUDA Version: 13.3") is None


def test_multiple_toolkits_cuda_path_and_resolution_are_distinct(tmp_path, monkeypatch):
    first = tmp_path / "CUDA" / "v12.8"
    second = tmp_path / "CUDA" / "v13.0"
    for root in (first, second):
        (root / "bin").mkdir(parents=True)
        (root / "bin" / "nvcc.exe").write_bytes(b"")
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: str(second / "bin" / "nvcc.exe") if name == "nvcc" else None)
    report = detect_gpu_compute([], env={"CUDA_PATH": str(first), "CUDA_PATH_V13_0": str(second)}, runner=lambda args, timeout: result(f"Cuda compilation tools, release {'12.8' if str(first) in args[0] else '13.0'}"))
    assert {item["version"] for item in report["cuda_toolkits"]} == {"12.8", "13.0"}
    assert next(item for item in report["cuda_toolkits"] if item["selected_by_cuda_path"])["version"] == "12.8"
    assert next(item for item in report["cuda_toolkits"] if item["resolved"])["version"] == "13.0"
    assert "cuda_path_nvcc_mismatch" in {item["code"] for item in report["contradictions"]}


@pytest.mark.parametrize(
    ("payload", "kind", "available", "architecture"),
    [
        ('{"python":"p","pytorch":{"installed":true,"version":"2","compiled_cuda":null,"cuda_available":false,"device_count":0,"devices":[],"compiled_architectures":[]}}', "cpu-only", False, "unknown"),
        ('{"python":"p","pytorch":{"installed":true,"version":"2","compiled_cuda":"12.8","cuda_available":false,"device_count":0,"devices":[],"compiled_architectures":["sm_89"]}}', "cuda", False, "unknown"),
        ('{"python":"p","pytorch":{"installed":true,"version":"2","compiled_cuda":"12.8","cuda_available":true,"device_count":1,"devices":[{"name":"GPU","compute_capability":"8.9"}],"compiled_architectures":["sm_89"]}}', "cuda", True, "green"),
    ],
)
def test_pytorch_states_are_independent(payload, kind, available, architecture):
    framework = _framework_probe("python.exe", lambda args, timeout: result(payload))
    torch = framework["pytorch"]
    assert torch["build_kind"] == kind
    assert torch["cuda_available"] is available
    assert torch["architecture_status"]["state"] == architecture
    assert torch["vram_feasibility"]["state"] == "unknown"


def test_pytorch_unknown_and_unsupported_architecture():
    assert _pytorch_architecture_status({"devices": [{"compute_capability": "9.0"}], "compiled_architectures": []})["state"] == "yellow"
    assert _pytorch_architecture_status({"devices": [{"compute_capability": "9.0"}], "compiled_architectures": ["sm_89"]})["state"] == "red"


@pytest.mark.parametrize("failure", [result(ok=False, error="timeout"), result("not-json")])
def test_framework_probe_failure_is_unknown(failure):
    assert _framework_probe("python.exe", lambda args, timeout: failure)["probe_status"] == "unknown"


def test_resource_pressure_and_disk_preflight_are_separate():
    gib = 1024**3
    disk = resource_pressure(100 * gib, 4 * gib, kind="disk")
    memory = resource_pressure(32 * gib, 2 * gib, kind="memory")
    assert disk["state"] == "critical"
    assert memory["state"] == "low"
    assert disk_preflight(4 * gib, download_bytes=1 * gib, extracted_bytes=5 * gib)["state"] == "red"
    assert disk_preflight(4 * gib)["state"] == "unknown"


def test_framework_private_runtime_does_not_create_toolkit(monkeypatch):
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: None)
    payload = '{"python":"p","pytorch":{"installed":true,"version":"2","compiled_cuda":"12.8","cuda_available":false,"device_count":0,"devices":[],"compiled_architectures":[]}}'
    report = detect_gpu_compute([], env={}, runner=lambda args, timeout: result(payload))
    assert report["frameworks"]["pytorch"]["compiled_cuda"] == "12.8"
    assert report["cuda_toolkits"] == []
    assert "pytorch_cuda_build_unavailable" in {item["code"] for item in report["contradictions"]}


def test_project_gpu_requirements_are_extracted_statically(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="gpu-app"\nrequires-python=">=3.12"\ndependencies=["torch==2.8.0", "onnxruntime-gpu>=1.22", "tensorrt==10.0"]\n',
        encoding="utf-8",
    )
    project = inspect_project(tmp_path)
    capabilities = {item.capability for item in project.requirements}
    assert {"gpu.framework.pytorch", "gpu.framework.onnxruntime", "gpu.framework.tensorrt"} <= capabilities
    assert all(item.evidence[0].kind.value == "declared" for item in project.requirements if item.capability.startswith("gpu."))


def test_frozen_arx_executable_is_never_framework_python(monkeypatch):
    invoked = []
    monkeypatch.setattr("arx.machine.gpu_compute.sys.executable", r"C:\Program Files\ARX\ARX.exe")
    monkeypatch.setattr("arx.machine.gpu_compute.sys.frozen", True, raising=False)
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: None)
    providers = [{"path": r"C:\Python314\python.exe", "healthy": True}]
    report = detect_gpu_compute([], env={}, python_providers=providers, runner=lambda args, timeout: invoked.append(args) or result('{"python":"C:\\\\Python314\\\\python.exe"}'))
    assert invoked[0][0] == r"C:\Python314\python.exe"
    assert report["resolution"]["python"] != r"C:\Program Files\ARX\ARX.exe"


def test_frozen_scan_without_healthy_python_is_not_tested(monkeypatch):
    invoked = []
    monkeypatch.setattr("arx.machine.gpu_compute.sys.executable", r"C:\Program Files\ARX\ARX.exe")
    monkeypatch.setattr("arx.machine.gpu_compute.sys.frozen", True, raising=False)
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: None)
    report = detect_gpu_compute([], env={}, python_providers=[{"path": r"C:\WindowsApps\python.exe", "healthy": False}], runner=lambda args, timeout: invoked.append(args) or result())
    assert invoked == []
    assert report["frameworks"]["probe_status"] == "not_tested"
    assert report["resolution"]["python"] is None


def test_standalone_tensorrt_path_provider_is_discovered(tmp_path, monkeypatch):
    root = tmp_path / "NVIDIA-AI" / "TensorRT-11.2.1.2"
    (root / "bin").mkdir(parents=True)
    (root / "lib").mkdir()
    (root / "bin" / "nvinfer_11.dll").write_bytes(b"")
    (root / "bin" / "nvonnxparser_11.dll").write_bytes(b"")
    (root / "lib" / "nvinfer.lib").write_bytes(b"")
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: None)
    report = detect_gpu_compute([], env={"PATH": str(root / "bin")}, python_executable="python.exe", runner=lambda args, timeout: result("{}"))
    assert report["tensorrt"]["native_providers"][0]["version"] == "11.2.1.2"
    assert report["tensorrt"]["native_providers"][0]["version_source"] == "installation_directory_name"
    assert all(item["runtime_loadable"] for item in report["tensorrt"]["runtime_libraries"])
    assert all(item["development_link_role"] for item in report["tensorrt"]["import_libraries"])
    assert report["tensorrt"]["compatibility"] == "unknown"


def test_cuda_runtime_and_import_libraries_are_not_conflated(tmp_path):
    root = tmp_path / "CUDA" / "v13.3"
    (root / "bin").mkdir(parents=True)
    (root / "lib" / "x64").mkdir(parents=True)
    (root / "bin" / "cudart64_13.dll").write_bytes(b"")
    (root / "lib" / "x64" / "cudart.lib").write_bytes(b"")
    libraries = _libraries(root, ("cudart",))
    runtime = next(item for item in libraries if item["path"].endswith(".dll"))
    import_library = next(item for item in libraries if item["path"].endswith(".lib"))
    assert runtime["artifact_kind"] == "runtime_library" and runtime["runtime_loadable"] is True
    assert import_library["artifact_kind"] == "import_library" and import_library["runtime_loadable"] is False


def test_single_nvidia_gpu_vram_disagreement_preserves_both_sources(monkeypatch):
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: "nvidia-smi.exe" if name == "nvidia-smi" else None)
    def runner(args, timeout):
        if any(item.startswith("--query-gpu") for item in args):
            return result("NVIDIA RTX 3050, GPU-1, 00000000:01:00.0, 616.56, 6144, 8.6")
        return result("KMD Version: 616.56 CUDA UMD Version: 13.4")
    wmi = 4293918720
    report = detect_gpu_compute([{"Name": "NVIDIA RTX 3050", "AdapterRAM": wmi}], env={}, python_executable="python.exe", runner=runner)
    contradiction = next(item for item in report["contradictions"] if item["code"] == "GPU_VRAM_SOURCE_DISAGREEMENT")
    assert report["gpus"][0]["dedicated_vram_bytes"] == wmi
    assert report["nvidia_tooling_gpus"][0]["dedicated_vram_bytes"] == 6442450944
    assert {item["source"] for item in contradiction["observations"]} == {"Win32_VideoController.AdapterRAM", "nvidia-smi memory.total"}


def test_dual_gpu_windows_inventory_does_not_suppress_nvidia_vram_reconciliation(monkeypatch):
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: "nvidia-smi.exe" if name == "nvidia-smi" else None)
    def runner(args, timeout):
        return result("NVIDIA RTX 3050, GPU-1, 00000000:01:00.0, 616.56, 6144, 8.6") if any(item.startswith("--query-gpu") for item in args) else result("KMD Version: 616.56 CUDA UMD Version: 13.4")
    hardware = [{"Name": "AMD Radeon Graphics", "AdapterRAM": 512 * 1024**2}, {"Name": "NVIDIA RTX 3050", "AdapterRAM": 4293918720}]
    report = detect_gpu_compute(hardware, env={}, python_executable="python.exe", runner=runner)
    assert len(report["gpus"]) == 2
    assert len(report["nvidia_tooling_gpus"]) == 1
    assert "GPU_VRAM_SOURCE_DISAGREEMENT" in {item["code"] for item in report["contradictions"]}


def test_cuda_host_compiler_context_is_recoverable_not_permanent_failure(monkeypatch):
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: "nvcc.exe" if name == "nvcc" else None)
    msvc = {"provider_installed": True, "current_resolution": {"resolved": False}, "developer_environment_entry_point": {"available": True}, "recoverable_context": "Visual Studio x64 Developer Environment"}
    report = detect_gpu_compute([], env={}, python_executable="python.exe", msvc=msvc, runner=lambda args, timeout: result("{}"))
    finding = next(item for item in report["contradictions"] if item["code"] == "CUDA_HOST_COMPILER_CONTEXT_UNRESOLVED")
    assert finding["automatic_activation"] is False
    assert finding["recoverable_context"] == "Visual Studio x64 Developer Environment"


def test_cuda_context_finding_requires_observed_developer_entry_point(monkeypatch):
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: "nvcc.exe" if name == "nvcc" else None)
    msvc = {"provider_installed": True, "current_resolution": {"resolved": False}, "developer_environment_entry_point": {"available": False}, "recoverable_context": None}
    report = detect_gpu_compute([], env={}, python_executable="python.exe", msvc=msvc, runner=lambda args, timeout: result("{}"))
    assert "CUDA_HOST_COMPILER_CONTEXT_UNRESOLVED" not in {item["code"] for item in report["contradictions"]}


def test_tensorrt_provider_is_deduplicated_across_environment_and_path(tmp_path, monkeypatch):
    root = tmp_path / "TensorRT-11.2.1.2"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "nvinfer_11.dll").write_bytes(b"")
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: None)
    report = detect_gpu_compute([], env={"PATH": str(root / "bin"), "TENSORRT_ROOT": str(root), "NVIDIA_AI_ROOT": str(tmp_path / "absent")}, python_executable="python.exe", runner=lambda args, timeout: result("{}"))
    assert len(report["tensorrt"]["native_providers"]) == 1
    assert set(report["tensorrt"]["native_providers"][0]["sources"]) == {"PATH entry", "environment:TENSORRT_ROOT"}

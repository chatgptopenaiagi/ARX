from pathlib import Path

import pytest

from arx.machine.gpu_compute import (
    _framework_probe,
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
        if "--query-gpu" in args:
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

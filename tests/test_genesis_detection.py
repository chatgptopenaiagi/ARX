import json
from types import SimpleNamespace

from arx.machine import windows
from arx.machine.gpu_compute import detect_gpu_compute
from arx.project.resolver import providers_from_machine


def test_appexeclink_alias_is_not_executed_or_marked_broken(monkeypatch):
    path = r"C:\Users\Alice\AppData\Local\Microsoft\WindowsApps\python.exe"
    monkeypatch.setattr(windows, "_python_candidates", lambda: [path])
    monkeypatch.setattr(windows.Path, "lstat", lambda self: SimpleNamespace(st_reparse_tag=0x8000001B))
    monkeypatch.setattr(windows.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("alias must not execute")))
    record = windows.discover_python_installations()[0]
    assert record["detection_status"] == "ALIAS"
    assert record["health_status"] == "unknown"
    assert record["healthy"] is None and record["error"] is None
    provider = providers_from_machine({"python_installations": [record]})[0]
    assert provider.kind.value == "windowsapps_alias"
    assert provider.health_status.value == "unknown"


def test_windowsapps_name_alone_is_not_proof_of_alias(tmp_path):
    executable = tmp_path / "Microsoft" / "WindowsApps" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"real executable fixture")
    assert windows._is_app_execution_alias(executable) is False


def test_python_health_uses_same_isolation_as_framework_probe(monkeypatch):
    monkeypatch.setattr(windows, "_python_candidates", lambda: [r"C:\Python315\python.exe"])
    monkeypatch.setattr(windows, "_is_app_execution_alias", lambda path: False)
    def run(args, **kwargs):
        # A split installation can start with registry fallback but fails -I.
        assert args[1:3] == ["-I", "-c"]
        assert "base_prefix" in args[3] and "sys.path" in args[3]
        return SimpleNamespace(returncode=1, stdout="", stderr="Fatal Python error: Failed to import encodings module")
    monkeypatch.setattr(windows.subprocess, "run", run)
    record = windows.discover_python_installations()[0]
    assert record["healthy"] is False
    assert "encodings" in record["error"]


def test_python_initialization_evidence_is_preserved(monkeypatch):
    monkeypatch.setattr(windows, "_python_candidates", lambda: ["python.exe"])
    monkeypatch.setattr(windows, "_is_app_execution_alias", lambda path: False)
    initialization = {"prefix": "C:\\Python315", "base_prefix": "C:\\Python315", "path": ["C:\\Python315\\Lib"], "isolated": 1, "ignore_environment": 1}
    payload = {"version": "3.15.1", "architecture_bits": "64-bit", "ssl": "OpenSSL", "initialization": initialization}
    monkeypatch.setattr(windows.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""))
    record = windows.discover_python_installations()[0]
    assert record["healthy"] is True
    assert record["initialization"] == initialization


def test_default_android_sdk_can_be_discovered_without_environment(tmp_path, monkeypatch):
    adb = tmp_path / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    adb.parent.mkdir(parents=True)
    adb.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    assert windows._known_tool_path("adb") == str(adb)


def test_vs_bundled_build_tools_can_be_discovered_without_path(tmp_path, monkeypatch):
    vswhere = tmp_path / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    vswhere.parent.mkdir(parents=True)
    vswhere.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))
    for name in ("cmake", "ninja"):
        executable = tmp_path / f"{name}.exe"
        executable.write_bytes(b"")
        def run(args, **kwargs):
            assert name + ".exe" in args[-1]
            assert "-sort" in args and "-latest" not in args and "-all" not in args
            return SimpleNamespace(stdout=str(executable) + "\n")
        monkeypatch.setattr(windows.subprocess, "run", run)
        assert windows._known_tool_path(name) == str(executable)


def test_gpu_operational_memory_prefers_nvidia_and_preserves_wmi(monkeypatch):
    monkeypatch.setattr("arx.machine.gpu_compute.shutil.which", lambda name: "nvidia-smi.exe" if name == "nvidia-smi" else None)
    def runner(args, timeout):
        text = "NVIDIA RTX 3050, GPU-1, 00000000:01:00.0, 617.42, 6144, 8.6" if any(arg.startswith("--query-gpu") for arg in args) else "NVIDIA-SMI 617.42 Driver Version: 617.42 CUDA Version: 13.4"
        return {"ok": True, "exit_code": 0, "stdout": text, "stderr": "", "error": None}
    report = detect_gpu_compute([{"Name": "NVIDIA RTX 3050", "AdapterRAM": 4293918720}], env={}, runner=runner)
    gpu = report["gpus"][0]
    assert gpu["wmi_adapter_ram_bytes"] == gpu["dedicated_vram_bytes"] == 4293918720
    assert "uint32" in gpu["dedicated_vram_source"]
    assert gpu["operational_vram"]["bytes"] == 6442450944
    assert gpu["operational_vram"]["source"] == "nvidia-smi memory.total"


def test_codex_export_does_not_list_alias_or_unknown_as_unhealthy():
    from arx.exporters.codex_exporter import codex_report
    records = [{"path": "alias", "healthy": None, "detection_status": "ALIAS"},
               {"path": "unverified", "healthy": None},
               {"path": "failed", "healthy": False}]
    report = codex_report({"os": {}, "tools": {}, "python_installations": records}, {}, "test")
    assert [item["path"] for item in report["unhealthy_python_installations"]] == ["failed"]

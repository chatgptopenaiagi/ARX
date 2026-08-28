from __future__ import annotations

from types import SimpleNamespace

from arx.machine.windows import discover_msvc, probe, scan_machine


def test_windows_probe_normalizes_utf16_wsl_and_utf8_flutter(monkeypatch):
    monkeypatch.setattr("arx.machine.windows.shutil.which", lambda name: name + ".exe")
    outputs = {
        "wsl.exe": "WSL version: 2.6.1".encode("utf-16-le"),
        "flutter.exe": "Flutter 3.41.5 • stable".encode("utf-8"),
    }
    monkeypatch.setattr("arx.machine.windows.subprocess.run", lambda args, **kwargs: SimpleNamespace(returncode=0, stdout=outputs[args[0]], stderr=b""))
    wsl = probe("wsl", ("wsl", "--version"))
    flutter = probe("flutter", ("flutter", "--version"))
    assert wsl.version == "2.6.1"
    assert "\x00" not in str(wsl.evidence[0].value)
    assert "•" in str(flutter.evidence[0].value)


def test_msvc_physical_provider_is_separate_from_current_resolution(tmp_path, monkeypatch):
    base = tmp_path / "Microsoft Visual Studio" / "18" / "BuildTools"
    compiler = base / "VC" / "Tools" / "MSVC" / "14.51.36231" / "bin" / "Hostx64" / "x64" / "cl.exe"
    compiler.parent.mkdir(parents=True)
    compiler.write_bytes(b"")
    entry = base / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    entry.parent.mkdir(parents=True)
    entry.write_text("rem fixture")
    sdk = tmp_path / "Windows Kits" / "10"
    (sdk / "Include" / "10.0.26100.0").mkdir(parents=True)
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))
    monkeypatch.setenv("WindowsSdkDir", str(sdk))
    monkeypatch.delenv("VCToolsInstallDir", raising=False)
    monkeypatch.setattr("arx.machine.windows.shutil.which", lambda name: None)
    report = discover_msvc()
    assert report["provider_installed"] is True
    assert report["providers"][0]["compiler_path"] == str(compiler)
    assert report["current_resolution"]["resolved"] is False
    assert report["developer_environment"]["observed_active"] is False
    assert report["developer_environment_entry_point"] == {"available": True, "path": str(entry), "automatic_activation": False}
    assert "10.0.26100.0" in report["windows_sdk"]["versions"]


def test_windows_scan_passes_python_and_msvc_inventory_to_gpu_analysis(monkeypatch):
    python = [{"path": r"C:\Python314\python.exe", "healthy": True}]
    msvc = {"provider_installed": True, "current_resolution": {"resolved": False}}
    captured = {}
    monkeypatch.setattr("arx.machine.windows.discover_python_installations", lambda: python)
    monkeypatch.setattr("arx.machine.windows.discover_msvc", lambda: msvc)
    monkeypatch.setattr("arx.machine.windows.discover_dotnet_runtimes", lambda: [])
    monkeypatch.setattr("arx.machine.windows._ps", lambda script, timeout=15: None)
    monkeypatch.setattr("arx.machine.windows.probe", lambda name, spec: None)
    monkeypatch.setattr("arx.machine.windows.analyze_resources", lambda memory, storage: {})
    monkeypatch.setattr("arx.machine.windows.safe_environment", lambda: {})
    def detect(gpu, **kwargs):
        captured.update(kwargs)
        return {}
    monkeypatch.setattr("arx.machine.windows.detect_gpu_compute", detect)
    report = scan_machine(deep=True)
    assert captured["python_providers"] is python
    assert captured["msvc"] is msvc
    assert report["python_installations"] is python
    assert report["msvc"] is msvc

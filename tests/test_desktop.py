import json,struct
import time
from pathlib import Path
from arx.core.engine import compare
from arx.core.models import ToolRecord
from arx.desktop.controllers import DesktopController
from arx.desktop.app import ARXDesktopApp
from arx.software.scanner import _application_evidence
from arx.project import ExecutionContext, ProviderKind, inspect_project, make_provider, preflight, resolve_python

def test_desktop_controller_reuses_engine_apis(monkeypatch,tmp_path):
    machine={"os":{"architecture":"AMD64"},"tools":{"python":ToolRecord("python",True)},"python_installations":[{"healthy":True}]}
    software={"filename":"sample.zip","detected_file_type":"zip_archive","evidence":[]}
    monkeypatch.setattr("arx.desktop.controllers.scan_machine",lambda deep:machine);monkeypatch.setattr("arx.desktop.controllers.scan_software",lambda target:software)
    controller=DesktopController();assert controller.scan().get("tools");assert controller.inspect("sample.zip") is software;assert controller.compare()["status"]=="partial"
    output=tmp_path/"report.json";controller.export(output);assert json.loads(output.read_text())["software"]["filename"]=="sample.zip"

def test_neighboring_dotnet_artifacts_are_application_evidence(tmp_path):
    app=tmp_path/"Example.exe";app.write_bytes(b"MZ")
    (tmp_path/"Example.dll").write_bytes(b"managed companion")
    (tmp_path/"Example.deps.json").write_text("{}")
    (tmp_path/"Example.runtimeconfig.json").write_text(json.dumps({"runtimeOptions":{"framework":{"name":"Microsoft.WindowsDesktop.App","version":"10.0.0"}}}))
    result=_application_evidence(app);assert result["dotnet"]=="detected";assert result["classification"]=="inferred";assert result["frameworks"][0]["version"]=="10.0.0"

def test_dotnet_runtime_requirement_uses_runtime_inventory():
    machine={"os":{"architecture":"AMD64"},"tools":{},"dotnet_runtimes":[{"name":"Microsoft.WindowsDesktop.App","version":"10.0.10"}]}
    software={"requirements":[{"capability":"dotnet.runtime","framework":"Microsoft.WindowsDesktop.App","version":"10.0.0","status":"declared"}]}
    report=compare(machine,software);assert report["status"]=="partial";assert report["checks"][-1]["status"]=="ready"

def test_desktop_file_picker_inspects_without_blocking(monkeypatch):
    class FakeController:
        def __init__(self):self.machine=None;self.software=None;self.compatibility=None;self.capabilities={}
        def inspect(self,target):self.software={"filename":"Chosen.exe","absolute_path":target,"detected_file_type":"windows_pe","evidence":[],"pe":{"architecture":"x64","imports":[]}};return self.software
    controller=FakeController();app=ARXDesktopApp(controller);app.withdraw();monkeypatch.setattr("arx.desktop.app.filedialog.askopenfilename",lambda **kwargs:r"C:\Chosen.exe")
    app._inspect_file();deadline=time.monotonic()+3
    while controller.software is None and time.monotonic()<deadline:app.update();time.sleep(.01)
    for _ in range(10):app.update();time.sleep(.01)
    assert controller.software["filename"]=="Chosen.exe";assert app._started is None;app.destroy()


def _project_report(tmp_path):
    (tmp_path/"pyproject.toml").write_text('[project]\nname="desktop-project"\nrequires-python=">=3.12,<3.13"',encoding="utf-8")
    project=inspect_project(tmp_path);provider=make_provider(path=tmp_path/".venv"/"Scripts"/"python.exe",version="3.12.13",kind=ProviderKind.VIRTUAL_ENVIRONMENT,discovery_method="fixture",healthy=True)
    context=ExecutionContext.capture(tmp_path,environment={"PATH":provider.path});resolution=resolve_python([provider],context,command_paths=[provider.path])
    return preflight(project,[provider],resolution)


def _project_mismatch_report(tmp_path):
    (tmp_path/"pyproject.toml").write_text('[project]\nname="desktop-project"\nrequires-python=">=3.12,<3.13"',encoding="utf-8")
    (tmp_path/".python-version").write_text("3.12",encoding="utf-8")
    project=inspect_project(tmp_path)
    current=make_provider(path=r"C:\Python314\python.exe",version="3.14.6",kind=ProviderKind.CPYTHON,discovery_method="fixture",healthy=True)
    compatible=make_provider(path=tmp_path/".venv"/"Scripts"/"python.exe",version="3.12.13",kind=ProviderKind.VIRTUAL_ENVIRONMENT,discovery_method="fixture",healthy=True)
    providers=[current,compatible]
    context=ExecutionContext.capture(tmp_path,environment={"PATH":current.path})
    resolution=resolve_python(providers,context,command_paths=[current.path])
    return preflight(project,providers,resolution)


def test_desktop_controller_runs_project_preflight_with_reused_machine(monkeypatch,tmp_path):
    report=_project_report(tmp_path);machine={"os":{},"tools":{},"python_installations":[]}
    captured={}
    def analyze(target,**kwargs):captured.update(target=target,**kwargs);return report
    monkeypatch.setattr("arx.desktop.controllers.project_preflight",analyze)
    controller=DesktopController();controller.machine=machine

    assert controller.preflight(tmp_path) is report
    assert captured["machine"] is machine
    assert controller.project_preflight.severity.severity.value=="green"

    monkeypatch.setattr("arx.desktop.controllers.scan_machine",lambda deep:machine)
    controller.scan(False)
    assert controller.project_preflight is None


def test_desktop_project_readiness_uses_text_and_color(tmp_path):
    controller=DesktopController();controller.project_preflight=_project_report(tmp_path)
    app=ARXDesktopApp(controller);app.withdraw();app._render_project()

    assert app.project_badge.cget("text")=="GREEN"
    detail=app.project_detail.get("1.0","end")
    assert "Shortest trusted path to GREEN" in detail
    assert "SATISFIED" in detail
    assert "dependency installation and application execution are not verified" in detail
    assert len(app.project_tree.get_children())>=1
    app.destroy()


def test_desktop_project_readiness_renders_compatible_mismatch_as_yellow(tmp_path):
    controller=DesktopController();controller.project_preflight=_project_mismatch_report(tmp_path)
    app=ARXDesktopApp(controller);app.withdraw();app._render_project()

    assert app.project_badge.cget("text")=="YELLOW"
    detail=app.project_detail.get("1.0","end")
    assert "Satisfaction: UNSATISFIED" in detail
    assert "Blockers: 0" in detail
    assert "WARNING  ARX-PYTHON-DEFAULT-MISMATCH" in detail
    assert "ARX-PYTHON-NO-COMPATIBLE-PROVIDER" not in detail
    assert "Use the existing Python 3.12.13" in detail
    app.destroy()


def test_desktop_project_smoke_mode_writes_result(monkeypatch,tmp_path):
    from arx.desktop.__main__ import main

    expected={"decision":"YELLOW","ai_schema_version":"0.2"}
    monkeypatch.setattr("arx.desktop.app.project_ui_smoke_test",lambda target,output:expected)
    output=tmp_path/"project.codex.json"

    assert main(["--project-ui-smoke-test",str(tmp_path),str(output)])==0
    result=Path(str(output)+".result.json")
    assert json.loads(result.read_text(encoding="utf-8"))==expected

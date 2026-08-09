import json,struct
import time
from arx.core.engine import compare
from arx.core.models import ToolRecord
from arx.desktop.controllers import DesktopController
from arx.desktop.app import ARXDesktopApp
from arx.software.scanner import _application_evidence

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

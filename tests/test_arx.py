import hashlib,json,struct,zipfile
from types import SimpleNamespace
from arx.core.engine import capabilities,compare,version_satisfies
from arx.core.evidence import redact_path,safe_environment
from arx.core.models import Evidence,EvidenceKind,ToolRecord,serialize
from arx.software import PEError,file_type,inspect_pe,sha256
from arx.software import scan_software
from arx.machine.windows import _known_tool_path,discover_python_installations,probe

def toolset(**present):
    names={"git","github_cli","python","node","javac","dotnet","cmake","ninja","adb","flutter","cuda","msbuild","rust","go","docker"}
    return {n:ToolRecord(n,present.get(n,False)) for n in names}
def test_evidence_kind_stays_explicit():assert serialize(Evidence(EvidenceKind.INFERRED,"x","Java >= 17","manifest",.8))["kind"]=="inferred"
def test_capability_explains_missing():
    caps=capabilities({"tools":toolset(javac=True,adb=True,cmake=True)});assert caps["android.native.build"].status.value=="partial";assert "ninja" in caps["android.native.build"].reason
def test_architecture_rules():
    machine={"os":{"architecture":"AMD64"},"tools":{}};assert compare(machine,{"pe":{"architecture":"x64"}})["status"]=="ready";assert compare(machine,{"pe":{"architecture":"arm64"}})["status"]=="blocked"
def test_redaction(monkeypatch):
    monkeypatch.setenv("USERPROFILE",r"C:\Users\Alice");assert redact_path(r"C:\Users\Alice\x")==r"%USERPROFILE%\x";assert safe_environment({"PATH":r"C:\Users\Alice\bin","API_KEY":"secret"})=={"PATH":r"%USERPROFILE%\bin"}
def test_types_and_hash(tmp_path):
    p=tmp_path/"x.ps1";p.write_text("safe");assert file_type(p)=="script";assert sha256(p)==hashlib.sha256(p.read_bytes()).hexdigest()
def test_pe(tmp_path):
    p=tmp_path/"x.exe";data=bytearray(512);data[:2]=b"MZ";struct.pack_into("<I",data,60,128);data[128:132]=b"PE\0\0";struct.pack_into("<HHIIIHH",data,132,0x8664,1,0,0,0,240,0x22);struct.pack_into("<H",data,152,0x20B);struct.pack_into("<H",data,220,3);p.write_bytes(data);result=inspect_pe(p);assert result["architecture"]=="x64";assert result["subsystem"]=="windows_console"
def test_missing_probe_is_evidence(monkeypatch):
    monkeypatch.setattr("arx.machine.windows.shutil.which",lambda _:None);monkeypatch.setattr("arx.machine.windows._known_tool_path",lambda _:None)
    record=probe("missing",("definitely-not-arx", "--version"));assert not record.detected;assert record.evidence[0].kind==EvidenceKind.OBSERVED
def test_archive_runtime_indicators(tmp_path):
    target=tmp_path/"app.zip"
    with zipfile.ZipFile(target,"w") as archive:archive.writestr("app/package.json",'{"engines":{"node":">=20"}}')
    result=scan_software(target);assert result["detected_file_type"]=="zip_archive";assert result["runtime_indicators"][0]["runtime"]=="node";assert result["requirements"][0]["version"]==">=20"
def test_corrupt_pe_is_reported(tmp_path):
    target=tmp_path/"bad.exe";target.write_bytes(b"MZ"+b"\0"*20)
    result=scan_software(target);assert "inspection_error" in result;assert result["evidence"][-1].kind==EvidenceKind.UNKNOWN
def test_declared_requirement_blocks_when_tool_missing():
    report=compare({"os":{"architecture":"AMD64"},"tools":toolset()},{"requirements":[{"capability":"node.available","version":">=20","status":"declared"}]})
    assert report["status"]=="blocked";assert "node.available not detected or version requirement not met" in report["blockers"]
def test_version_comparison_is_conservative():
    assert version_satisfies("20.11.1",">=20") is True;assert version_satisfies("17.0.2",">=20") is False;assert version_satisfies("20.0","^20") is None
def test_android_studio_jbr_jdk_is_found_outside_path(tmp_path,monkeypatch):
    javac=tmp_path/"Android"/"Android Studio"/"jbr"/"bin"/"javac.exe";javac.parent.mkdir(parents=True);javac.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles",str(tmp_path));monkeypatch.delenv("JAVA_HOME",raising=False);monkeypatch.delenv("ANDROID_STUDIO_JDK",raising=False);monkeypatch.delenv("STUDIO_JDK",raising=False)
    assert _known_tool_path("javac")==str(javac)
def test_msbuild_is_found_with_vswhere(tmp_path,monkeypatch):
    installer=tmp_path/"Microsoft Visual Studio"/"Installer"/"vswhere.exe";installer.parent.mkdir(parents=True);installer.write_bytes(b"")
    msbuild=tmp_path/"Microsoft Visual Studio"/"18"/"MSBuild.exe";msbuild.parent.mkdir(parents=True);msbuild.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles(x86)",str(tmp_path));monkeypatch.setattr("arx.machine.windows.subprocess.run",lambda *a,**k:SimpleNamespace(stdout=str(msbuild)+"\n"))
    assert _known_tool_path("msbuild")==str(msbuild)
def test_python_installations_keep_health_separate(monkeypatch):
    paths=[r"C:\PythonHealthy\python.exe",r"C:\PythonBroken\python.exe"]
    monkeypatch.setattr("arx.machine.windows._python_candidates",lambda:paths)
    def run(args,**kwargs):
        if args[0]==paths[0]:return SimpleNamespace(returncode=0,stdout=json.dumps({"version":"3.12.1","architecture":"AMD64","ssl":"OpenSSL test"}),stderr="")
        return SimpleNamespace(returncode=1,stdout="",stderr="ImportError: DLL load failed")
    monkeypatch.setattr("arx.machine.windows.subprocess.run",run)
    records=discover_python_installations();assert [r["healthy"] for r in records]==[True,False];assert records[1]["error"].startswith("ImportError")
    caps=capabilities({"tools":toolset(python=True),"python_installations":[records[1]]});assert caps["python.available"].status.value=="missing";assert caps["python.available"].reason=="healthy Python runtime not detected"

import hashlib,struct
from arx.core.engine import capabilities,compare
from arx.core.evidence import redact_path,safe_environment
from arx.core.models import Evidence,EvidenceKind,ToolRecord,serialize
from arx.software import PEError,file_type,inspect_pe,sha256

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


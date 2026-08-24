import hashlib, json, re, shutil, struct, subprocess, zipfile
from collections.abc import Mapping
from pathlib import Path
from arx.core.models import Evidence,EvidenceKind,utc_now

MACHINES={0x14C:"x86",0x8664:"x64",0xAA64:"arm64",0x1C4:"arm"}; SUBSYSTEMS={2:"windows_gui",3:"windows_console",10:"efi_application"}
class PEError(ValueError):pass
def file_type(path):
    if path.is_dir():return "directory"
    try: magic=path.read_bytes()[:8]
    except OSError:return "unknown"
    ext=path.suffix.lower()
    if magic[:2]==b"MZ":return "windows_pe"
    if magic[:4]==b"PK\x03\x04":return "android_apk" if ext==".apk" else "java_archive" if ext==".jar" else "zip_archive"
    if magic==b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and ext==".msi":return "windows_msi"
    return "script" if ext in {".ps1",".bat",".cmd",".py",".js",".sh"} else "unknown"
def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def inspect_pe(path):
    data=path.read_bytes()
    if len(data)<64 or data[:2]!=b"MZ":raise PEError("missing DOS header")
    off=struct.unpack_from("<I",data,60)[0]
    if off+24>len(data) or data[off:off+4]!=b"PE\0\0":raise PEError("missing or truncated PE header")
    machine,sections,timestamp,_,_,opt_size,chars=struct.unpack_from("<HHIIIHH",data,off+4); optional=off+24
    if opt_size<2 or optional+opt_size>len(data):raise PEError("truncated optional header")
    magic=struct.unpack_from("<H",data,optional)[0]
    if magic not in (0x10B,0x20B):raise PEError("unsupported optional header")
    base_size=96 if magic==0x10B else 112
    if opt_size<base_size:raise PEError("truncated optional header")
    subsystem=struct.unpack_from("<H",data,optional+68)[0]; directory=optional+base_size; clr=(0,0)
    if directory+120<=optional+opt_size:clr=struct.unpack_from("<II",data,directory+112)
    lower=data.lower(); imports=sorted({x[:-1].decode("ascii","ignore") for x in re.findall(rb"[a-zA-Z0-9_.-]{2,80}\.dll\x00",lower)})
    level=next((x.decode() for x in (b"requireAdministrator",b"highestAvailable",b"asInvoker") if x.lower() in lower),None)
    return {"format":"PE32+" if magic==0x20B else "PE32","architecture":MACHINES.get(machine,f"machine_0x{machine:04x}"),"sections":sections,"timestamp":timestamp,"subsystem":SUBSYSTEMS.get(subsystem,f"subsystem_{subsystem}"),"characteristics":chars,"imports":imports[:500],"is_dotnet":bool(clr[0] and clr[1]),"requested_execution_level":level}
def signature(path):
    pwsh=shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:return {"status":"unknown","reason":"PowerShell unavailable"}
    script="$s=Get-AuthenticodeSignature -LiteralPath $args[0];[pscustomobject]@{Status=[string]$s.Status;StatusMessage=$s.StatusMessage;SignerSubject=if($s.SignerCertificate){$s.SignerCertificate.Subject}else{$null}}|ConvertTo-Json -Compress"
    try:
        p=subprocess.run([pwsh,"-NoProfile","-NonInteractive","-CommandWithArgs",script,str(path)],capture_output=True,text=True,timeout=10,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        return json.loads(p.stdout) if p.returncode==0 and p.stdout.strip() else {"status":"unknown","reason":p.stderr.strip()[:300]}
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:return {"status":"unknown","reason":type(exc).__name__}

MANIFEST_NAMES={"package.json","pyproject.toml","requirements.txt","pom.xml","build.gradle","build.gradle.kts","androidmanifest.xml","manifest.mf","runtimeconfig.json"}
def _indicators(names):
    lowered=[n.lower().replace("\\","/") for n in names]; result=[]
    tests=[("dotnet",lambda n:n.endswith(".runtimeconfig.json") or n.endswith(".deps.json")),("java",lambda n:n.endswith(".jar") or n.endswith("pom.xml")),("node",lambda n:n.endswith("package.json")),("python",lambda n:n.endswith("pyproject.toml") or n.endswith("requirements.txt")),("android",lambda n:n.endswith("androidmanifest.xml"))]
    for runtime,test in tests:
        matches=[n for n in lowered if test(n)]
        if matches:result.append({"runtime":runtime,"status":"inferred","confidence":0.75,"evidence":matches[:10]})
    return result

def _archive_metadata(path):
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist(); manifests=[n for n in names if Path(n).name.lower() in MANIFEST_NAMES or n.lower().endswith(".runtimeconfig.json")]
        requirements=[]
        for name in manifests[:20]:
            if name.lower().endswith("package.json") and archive.getinfo(name).file_size<=1024*1024:
                try:requirements.extend(_package_requirements(json.loads(archive.read(name))))
                except (UnicodeDecodeError,json.JSONDecodeError,KeyError):pass
        return {"entries":len(names),"sample_entries":names[:100],"manifest_files":manifests[:100]},_indicators(names),requirements

def _package_requirements(data):
    result=[]
    if not isinstance(data,Mapping):return result
    engines=data.get("engines",{})
    if not isinstance(engines,Mapping):return result
    for runtime,spec in engines.items():
        capability={"node":"node.available","npm":"npm"}.get(runtime,runtime)
        result.append({"capability":capability,"version":str(spec),"status":"declared","confidence":1.0,"source":"package.json engines"})
    return result

def _directory_requirements(path,files):
    result=[]
    for item in files:
        if item.name.lower()=="package.json" and item.stat().st_size<=1024*1024:
            try:result.extend(_package_requirements(json.loads(item.read_text(encoding="utf-8"))))
            except (OSError,UnicodeDecodeError,json.JSONDecodeError):pass
    return result

def _application_evidence(path):
    """Inspect bounded neighboring artifacts without loading or executing the application."""
    evidence=[];frameworks=[];stem=path.stem.lower()
    try:siblings=[item for item in path.parent.iterdir() if item.is_file() and item.stem.lower().startswith(stem)]
    except OSError:return {}
    for item in siblings:
        lower=item.name.lower()
        if lower.endswith(".runtimeconfig.json") and item.stat().st_size<=1024*1024:
            evidence.append(item.name)
            try:
                config=json.loads(item.read_text(encoding="utf-8"));runtime=config.get("runtimeOptions",{});declared=runtime.get("framework") or ((runtime.get("frameworks") or [None])[0])
                if declared:frameworks.append({"name":declared.get("name"),"version":declared.get("version"),"status":"declared","source":item.name})
            except (OSError,UnicodeDecodeError,json.JSONDecodeError,AttributeError):pass
        elif lower.endswith(".deps.json") or (lower.endswith(".dll") and item.stem.lower()==stem):evidence.append(item.name)
    if not evidence:return {}
    return {"dotnet":"detected","classification":"inferred","confidence":.9 if frameworks else .75,"evidence":evidence[:50],"frameworks":frameworks}
def scan_software(target):
    path=Path(target).expanduser().resolve(strict=True); kind=file_type(path); result={"generated_at":utc_now(),"filename":path.name,"absolute_path":str(path),"detected_file_type":kind,"evidence":[]}
    if path.is_dir():
        files=[p for p in path.rglob("*") if p.is_file()]; relative=[str(p.relative_to(path)) for p in files]; result.update(file_count=len(files),manifest_files=[n for n in relative if Path(n).name.lower() in MANIFEST_NAMES][:100],runtime_indicators=_indicators(relative),requirements=_directory_requirements(path,files));return result
    result.update(size=path.stat().st_size,sha256=sha256(path));result["evidence"].append(Evidence(EvidenceKind.OBSERVED,str(path),kind,"magic bytes and extension"))
    try:
        if kind=="windows_pe":
            result["pe"]=inspect_pe(path);result["signature"]=signature(path);application=_application_evidence(path)
            if application:
                result["application"]=application;result.setdefault("runtime_indicators",[]).append({"runtime":"dotnet","status":"inferred","confidence":application["confidence"],"evidence":application["evidence"]})
                result.setdefault("requirements",[]).extend({"capability":"dotnet.runtime","framework":item.get("name"),"version":item.get("version"),"status":"declared","confidence":1.0,"source":item.get("source")} for item in application.get("frameworks",[]))
        elif kind in {"zip_archive","android_apk","java_archive"}:
            result["archive"],result["runtime_indicators"],result["requirements"]=_archive_metadata(path)
            if kind=="android_apk":result["requirements"]=[{"capability":"android.runtime","status":"inferred","confidence":.7,"source":"APK container"}]
    except (OSError,PEError,zipfile.BadZipFile) as exc:result["inspection_error"]=str(exc);result["evidence"].append(Evidence(EvidenceKind.UNKNOWN,str(path),str(exc),"static parser",.3))
    return result

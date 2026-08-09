import hashlib, json, os, re, shutil, struct, subprocess, zipfile
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
    if optional+opt_size>len(data):raise PEError("truncated optional header")
    magic=struct.unpack_from("<H",data,optional)[0]
    if magic not in (0x10B,0x20B):raise PEError("unsupported optional header")
    subsystem=struct.unpack_from("<H",data,optional+68)[0]; directory=optional+(96 if magic==0x10B else 112); clr=(0,0)
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
def scan_software(target):
    path=Path(target).expanduser().resolve(strict=True); kind=file_type(path); result={"generated_at":utc_now(),"filename":path.name,"absolute_path":str(path),"detected_file_type":kind,"evidence":[]}
    if path.is_dir():
        files=[p for p in path.rglob("*") if p.is_file()]; result.update(file_count=len(files),manifest_files=[str(p.relative_to(path)) for p in files if p.name.lower() in {"package.json","pyproject.toml","requirements.txt","pom.xml","build.gradle","androidmanifest.xml"}][:100]);return result
    result.update(size=path.stat().st_size,sha256=sha256(path));result["evidence"].append(Evidence(EvidenceKind.OBSERVED,str(path),kind,"magic bytes and extension"))
    try:
        if kind=="windows_pe":result["pe"]=inspect_pe(path);result["signature"]=signature(path)
        elif kind in {"zip_archive","android_apk","java_archive"}:
            with zipfile.ZipFile(path) as z: result["archive"]={"entries":len(z.namelist()),"sample_entries":z.namelist()[:100]}
    except (OSError,PEError,zipfile.BadZipFile) as exc:result["inspection_error"]=str(exc);result["evidence"].append(Evidence(EvidenceKind.UNKNOWN,str(path),str(exc),"static parser",.3))
    return result


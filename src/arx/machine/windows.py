import json, os, platform, re, shutil, subprocess
from pathlib import Path
from arx.core.evidence import safe_environment
from arx.core.models import Evidence, EvidenceKind, ToolRecord, utc_now

PROBES={
"git":("git","--version"),"github_cli":("gh","--version"),"python":("python","--version"),"pip":("pip","--version"),"conda":("conda","--version"),
"node":("node","--version"),"npm":("npm","--version"),"pnpm":("pnpm","--version"),"yarn":("yarn","--version"),"java":("java","-version"),"javac":("javac","-version"),
"gradle":("gradle","--version"),"maven":("mvn","--version"),"dotnet":("dotnet","--version"),"powershell":("pwsh","--version"),"cmake":("cmake","--version"),
"ninja":("ninja","--version"),"msbuild":("msbuild","-version"),"clang":("clang","--version"),"gcc":("gcc","--version"),"rust":("rustc","--version"),
"cargo":("cargo","--version"),"go":("go","version"),"docker":("docker","--version"),"wsl":("wsl","--version"),"adb":("adb","version"),"flutter":("flutter","--version"),
"cuda":("nvcc","--version"),"nvidia_smi":("nvidia-smi","--query-gpu=name,driver_version,memory.total","--format=csv,noheader")}

def probe(name, spec, timeout=5):
    path=shutil.which(spec[0]) or _known_tool_path(name)
    if not path: return ToolRecord(name,False,evidence=[Evidence(EvidenceKind.OBSERVED,"PATH","not found","shutil.which")])
    try:
        p=subprocess.run([path,*spec[1:]],capture_output=True,text=True,timeout=timeout,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        output=(p.stdout+"\n"+p.stderr).strip(); match=re.search(r"(?<!\d)(\d+(?:\.\d+){1,3}(?:[-+._a-zA-Z0-9]*)?)",output)
        return ToolRecord(name,p.returncode==0,match.group(1) if match else None,path,[Evidence(EvidenceKind.OBSERVED,path,(output.splitlines() or [f"exit {p.returncode}"])[0][:300],"safe version probe")],confidence=1 if p.returncode==0 else .7,notes=[] if p.returncode==0 else [f"exit {p.returncode}"])
    except (OSError,subprocess.TimeoutExpired) as exc:
        return ToolRecord(name,True,path=path,evidence=[Evidence(EvidenceKind.UNKNOWN,path,type(exc).__name__,"safe version probe",.5)],confidence=.5,notes=["probe failed"])

def _known_tool_path(name):
    """Resolve selected Windows tools that installers intentionally omit from PATH."""
    candidates=[]
    if name=="msbuild":
        installer=Path(os.environ.get("ProgramFiles(x86)",r"C:\Program Files (x86)"))/"Microsoft Visual Studio"/"Installer"/"vswhere.exe"
        if installer.is_file():
            try:
                p=subprocess.run([str(installer),"-latest","-products","*","-requires","Microsoft.Component.MSBuild","-find",r"MSBuild\**\Bin\MSBuild.exe"],capture_output=True,text=True,timeout=5,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                candidates.extend(line.strip() for line in p.stdout.splitlines())
            except (OSError,subprocess.TimeoutExpired): pass
    roots={
        "adb":[os.environ.get("ANDROID_SDK_ROOT"),os.environ.get("ANDROID_HOME")],
        "cuda":[os.environ.get("CUDA_PATH")],
        "java":[os.environ.get("JAVA_HOME"),os.environ.get("ANDROID_STUDIO_JDK"),os.environ.get("STUDIO_JDK")],
        "javac":[os.environ.get("JAVA_HOME"),os.environ.get("ANDROID_STUDIO_JDK"),os.environ.get("STUDIO_JDK")],
    }
    suffix={"adb":r"platform-tools\adb.exe","cuda":r"bin\nvcc.exe","java":r"bin\java.exe","javac":r"bin\javac.exe"}
    for root in roots.get(name,[]):
        if root:candidates.append(str(Path(root)/suffix[name]))
    if name in {"java","javac"}:
        program_files=Path(os.environ.get("ProgramFiles",r"C:\Program Files"))
        candidates.extend((str(program_files/"Android"/"Android Studio"/folder/"bin"/f"{name}.exe") for folder in ("jbr","jre")))
    return next((p for p in candidates if p and Path(p).is_file()),None)

def _python_candidates():
    candidates=[];launcher=shutil.which("py")
    if launcher:
        try:
            p=subprocess.run([launcher,"-0p"],capture_output=True,text=True,timeout=5,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            candidates.extend(re.findall(r"([A-Za-z]:\\[^\r\n]*?python\.exe)",p.stdout+p.stderr,re.I))
        except (OSError,subprocess.TimeoutExpired):pass
    where=shutil.which("where.exe")
    if where:
        try:
            p=subprocess.run([where,"python"],capture_output=True,text=True,timeout=5,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0));candidates.extend(line.strip() for line in p.stdout.splitlines())
        except (OSError,subprocess.TimeoutExpired):pass
    default=shutil.which("python")
    if default:candidates.append(default)
    unique={str(Path(item).resolve()).lower():str(Path(item).resolve()) for item in candidates if item and Path(item).is_file()}
    return list(unique.values())

def discover_python_installations(timeout=8):
    """Inventory each registered/command-visible Python and test core runtime imports."""
    script="import ctypes,json,platform,ssl,sys;print(json.dumps({'version':platform.python_version(),'architecture':platform.machine(),'ssl':ssl.OPENSSL_VERSION,'executable':sys.executable}))"
    records=[]
    for path in _python_candidates():
        try:
            p=subprocess.run([path,"-c",script],capture_output=True,text=True,timeout=timeout,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0));details=json.loads(p.stdout) if p.returncode==0 and p.stdout.strip() else {}
            records.append({"path":path,"version":details.get("version"),"architecture":details.get("architecture"),"healthy":p.returncode==0,"health_probe":"import ssl, ctypes","ssl":details.get("ssl"),"exit_code":p.returncode,"error":None if p.returncode==0 else (p.stderr or p.stdout).strip()[:500],"evidence":[Evidence(EvidenceKind.OBSERVED,path,"healthy" if p.returncode==0 else "unhealthy","fixed Python core import probe",1.0 if p.returncode==0 else .9)]})
        except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
            records.append({"path":path,"version":None,"architecture":None,"healthy":False,"health_probe":"import ssl, ctypes","ssl":None,"exit_code":None,"error":type(exc).__name__,"evidence":[Evidence(EvidenceKind.UNKNOWN,path,type(exc).__name__,"fixed Python core import probe",.5)]})
    return records

def discover_dotnet_runtimes(timeout=8):
    path=shutil.which("dotnet")
    if not path:return []
    try:
        p=subprocess.run([path,"--list-runtimes"],capture_output=True,text=True,timeout=timeout,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0));records=[]
        for line in p.stdout.splitlines():
            match=re.match(r"(\S+)\s+(\S+)\s+\[(.+)\]",line.strip())
            if match:records.append({"name":match.group(1),"version":match.group(2),"path":match.group(3),"evidence":[Evidence(EvidenceKind.OBSERVED,path,line.strip(),"dotnet --list-runtimes")]})
        return records
    except (OSError,subprocess.TimeoutExpired):return []

def _ps(script,timeout=15):
    exe=shutil.which("pwsh") or shutil.which("powershell")
    if not exe:return None
    try:
        p=subprocess.run([exe,"-NoProfile","-NonInteractive","-Command",script],capture_output=True,text=True,timeout=timeout,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        return json.loads(p.stdout) if p.returncode==0 and p.stdout.strip() else None
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError): return None

def scan_machine(deep=True):
    memory=_ps("Get-CimInstance Win32_OperatingSystem|Select TotalVisibleMemorySize,FreePhysicalMemory|ConvertTo-Json -Compress")
    if memory: memory={"total_bytes":int(memory.get("TotalVisibleMemorySize",0))*1024,"available_bytes":int(memory.get("FreePhysicalMemory",0))*1024}
    keys=("ANDROID_HOME","ANDROID_SDK_ROOT","ANDROID_NDK_HOME","JAVA_HOME","CUDA_PATH","VULKAN_SDK")
    os_info=_ps("Get-CimInstance Win32_OperatingSystem|Select Caption,Version,BuildNumber,OSArchitecture|ConvertTo-Json -Compress") or {}
    return {"generated_at":utc_now(),"os":{"system":platform.system(),"edition":os_info.get("Caption"),"release":platform.release(),"version":os_info.get("Version",platform.version()),"build":os_info.get("BuildNumber"),"architecture":platform.machine(),"reported_architecture":os_info.get("OSArchitecture"),"hostname":platform.node(),"wow64":bool(os.environ.get("PROCESSOR_ARCHITEW6432"))},
      "cpu":_ps("Get-CimInstance Win32_Processor|Select -First 1 Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,Architecture,VirtualizationFirmwareEnabled|ConvertTo-Json -Compress") or {"model":platform.processor(),"logical_processors":os.cpu_count()},"memory":memory,
      "gpu":_ps("Get-CimInstance Win32_VideoController|Select Name,AdapterRAM,DriverVersion,VideoProcessor|ConvertTo-Json -Compress") if deep else None,
      "storage":_ps("Get-Volume|Where DriveLetter|Select DriveLetter,FileSystem,Size,SizeRemaining,DriveType|ConvertTo-Json -Compress") if deep else None,
      "tools":{name:probe(name,spec) for name,spec in PROBES.items()},"python_installations":discover_python_installations(),"dotnet_runtimes":discover_dotnet_runtimes(),"sdk_hints":{k.lower():{"detected":bool(os.environ.get(k)),"path":os.environ.get(k)} for k in keys},
      "environment":safe_environment() if deep else {},"evidence":[Evidence(EvidenceKind.OBSERVED,"local Windows host","read-only scan","Python APIs and CIM")]}

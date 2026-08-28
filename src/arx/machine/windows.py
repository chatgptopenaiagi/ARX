import json, os, platform, re, shutil, subprocess
from pathlib import Path
from arx.core.evidence import safe_environment
from arx.core.models import Evidence, EvidenceKind, ToolRecord, utc_now
from arx.core.subprocess import run_bounded
from arx.machine.gpu_compute import analyze_resources, detect_gpu_compute

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
        p=run_bounded([path,*spec[1:]],timeout=timeout,limit=64*1024,runner=subprocess.run)
        output=(p["stdout"]+"\n"+p["stderr"]).strip(); match=re.search(r"(?<!\d)(\d+(?:\.\d+){1,3}(?:[-+._a-zA-Z0-9]*)?)",output)
        return ToolRecord(name,p["returncode"]==0,match.group(1) if match else None,path,[Evidence(EvidenceKind.OBSERVED,path,(output.splitlines() or [f"exit {p['returncode']}"])[0][:300],"safe version probe")],confidence=1 if p["returncode"]==0 else .7,notes=[] if p["returncode"]==0 else [f"exit {p['returncode']}"])
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
        for command in ("python", "python3"):
            try:
                p=subprocess.run([where,command],capture_output=True,text=True,timeout=5,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0));candidates.extend(line.strip() for line in p.stdout.splitlines())
            except (OSError,subprocess.TimeoutExpired):pass
    default=shutil.which("python")
    if default:candidates.append(default)
    unique={str(Path(item).resolve(strict=False)).lower():str(Path(item).resolve(strict=False)) for item in candidates if item}
    return list(unique.values())

def discover_python_installations(timeout=8):
    """Inventory each registered/command-visible Python and test core runtime imports."""
    script="import ctypes,json,platform,ssl,struct,sys;print(json.dumps({'version':platform.python_version(),'architecture':platform.machine(),'architecture_bits':str(struct.calcsize('P')*8)+'-bit','ssl':ssl.OPENSSL_VERSION,'executable':sys.executable}))"
    records=[]
    for path in _python_candidates():
        try:exists=Path(path).exists()
        except OSError:exists=True
        try:
            p=subprocess.run([path,"-c",script],capture_output=True,text=True,timeout=timeout,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if p.returncode != 0:
                reason=(p.stderr or p.stdout).strip()[:500] or f"probe exited {p.returncode}"
                records.append({"path":path,"exists":exists,"version":None,"architecture":None,"architecture_bits":None,"healthy":False,"health_status":"unhealthy","health_reason":reason,"health_probe":"start, version, architecture, import sys/ssl/ctypes","ssl":None,"exit_code":p.returncode,"error":reason,"evidence":[Evidence(EvidenceKind.OBSERVED,path,"unhealthy","fixed Python core import probe",.9,reason)]})
                continue
            try:
                details=json.loads(p.stdout) if p.stdout.strip() else {}
            except json.JSONDecodeError as exc:
                reason="provider started but did not return valid fixed-probe output"
                records.append({"path":path,"exists":exists,"version":None,"architecture":None,"architecture_bits":None,"healthy":False,"health_status":"degraded","health_reason":reason,"health_probe":"start, version, architecture, import sys/ssl/ctypes","ssl":None,"exit_code":p.returncode,"error":type(exc).__name__,"evidence":[Evidence(EvidenceKind.UNKNOWN,path,"degraded", "fixed Python core import probe",.6,reason)]})
                continue
            healthy=bool(details.get("version") and details.get("architecture_bits") and details.get("ssl"))
            reason=None if healthy else "fixed probe returned incomplete runtime details"
            status="healthy" if healthy else "degraded"
            records.append({"path":path,"exists":exists,"version":details.get("version"),"architecture":details.get("architecture"),"architecture_bits":details.get("architecture_bits"),"healthy":healthy,"health_status":status,"health_reason":reason,"health_probe":"start, version, architecture, import sys/ssl/ctypes","ssl":details.get("ssl"),"exit_code":p.returncode,"error":reason,"evidence":[Evidence(EvidenceKind.OBSERVED if healthy else EvidenceKind.UNKNOWN,path,status,"fixed Python core import probe",1.0 if healthy else .6,reason)]})
        except PermissionError as exc:
            reason=f"permission/access failure: {type(exc).__name__}"
            records.append({"path":path,"exists":exists,"version":None,"architecture":None,"architecture_bits":None,"healthy":None,"health_status":"unknown","health_reason":reason,"health_probe":"start, version, architecture, import sys/ssl/ctypes","ssl":None,"exit_code":None,"error":reason,"evidence":[Evidence(EvidenceKind.UNKNOWN,path,"unknown","fixed Python core import probe",.5,reason)]})
        except subprocess.TimeoutExpired as exc:
            reason=f"fixed probe timed out after {timeout} seconds"
            records.append({"path":path,"exists":exists,"version":None,"architecture":None,"architecture_bits":None,"healthy":None,"health_status":"unknown","health_reason":reason,"health_probe":"start, version, architecture, import sys/ssl/ctypes","ssl":None,"exit_code":None,"error":type(exc).__name__,"evidence":[Evidence(EvidenceKind.UNKNOWN,path,"unknown","fixed Python core import probe",.5,reason)]})
        except OSError as exc:
            reason=f"provider invocation failed and may be transient: {type(exc).__name__}"
            records.append({"path":path,"exists":exists,"version":None,"architecture":None,"architecture_bits":None,"healthy":None,"health_status":"unknown","health_reason":reason,"health_probe":"start, version, architecture, import sys/ssl/ctypes","ssl":None,"exit_code":None,"error":type(exc).__name__,"evidence":[Evidence(EvidenceKind.UNKNOWN,path,"unknown","fixed Python core import probe",.5,reason)]})
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

def discover_msvc():
    """Bounded physical-provider and current-context inventory; never activates a shell."""
    base=Path(os.environ.get("ProgramFiles(x86)",r"C:\Program Files (x86)"))/"Microsoft Visual Studio"
    providers=[]
    if base.is_dir():
        try: editions=[item for version in list(base.iterdir())[:32] if version.is_dir() for item in list(version.iterdir())[:32] if item.is_dir()]
        except OSError: editions=[]
        for installation in editions:
            tools=installation/"VC"/"Tools"/"MSVC"
            try: versions=sorted((item for item in tools.iterdir() if item.is_dir()),reverse=True)[:8] if tools.is_dir() else []
            except OSError: versions=[]
            for toolset in versions:
                compiler=toolset/"bin"/"Hostx64"/"x64"/"cl.exe"
                if compiler.is_file(): providers.append({"installation_root":str(installation),"toolset_version":toolset.name,"compiler_path":str(compiler),"architecture":"x64","evidence":[Evidence(EvidenceKind.OBSERVED,"Visual Studio bounded installation roots",str(compiler),"physical file presence")]})
    resolved=shutil.which("cl.exe") or shutil.which("cl")
    selected=providers[0] if providers else None
    installation=Path(selected["installation_root"]) if selected else None
    vcvars=installation/"VC"/"Auxiliary"/"Build"/"vcvars64.bat" if installation else None
    vsdev=installation/"Common7"/"Tools"/"VsDevCmd.bat" if installation else None
    sdk_root=Path(os.environ.get("WindowsSdkDir",r"C:\Program Files (x86)\Windows Kits\10"))
    include=sdk_root/"Include"
    try: sdk_versions=sorted((item.name for item in include.iterdir() if item.is_dir()),reverse=True)[:16] if include.is_dir() else []
    except OSError: sdk_versions=[]
    active=bool(os.environ.get("VCToolsInstallDir") and os.environ.get("WindowsSdkDir"))
    entry=next((str(item) for item in (vcvars,vsdev) if item and item.is_file()),None)
    return {"provider_installed":bool(providers),"providers":providers,"current_resolution":{"resolved":bool(resolved),"path":resolved},"developer_environment":{"observed_active":active,"selected_markers":{"VCToolsInstallDir":bool(os.environ.get("VCToolsInstallDir")),"WindowsSdkDir":bool(os.environ.get("WindowsSdkDir")),"INCLUDE":bool(os.environ.get("INCLUDE")),"LIB":bool(os.environ.get("LIB"))}},"developer_environment_entry_point":{"available":bool(entry),"path":entry,"automatic_activation":False},"windows_sdk":{"root":str(sdk_root),"versions":sdk_versions,"selected_version":next((value for value in sdk_versions if str(sdk_root/value).casefold() in os.environ.get("INCLUDE","").casefold()),None)},"recoverable_context":"Visual Studio x64 Developer Environment" if entry else None}

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
    gpu=_ps("Get-CimInstance Win32_VideoController|Select Name,PNPDeviceID,AdapterRAM,DriverVersion,VideoProcessor|ConvertTo-Json -Compress") if deep else None
    storage=_ps("Get-Volume|Where DriveLetter|Select DriveLetter,FileSystem,Size,SizeRemaining,DriveType|ConvertTo-Json -Compress") if deep else None
    python_installations=discover_python_installations();msvc=discover_msvc()
    return {"generated_at":utc_now(),"os":{"system":platform.system(),"edition":os_info.get("Caption"),"release":platform.release(),"version":os_info.get("Version",platform.version()),"build":os_info.get("BuildNumber"),"architecture":platform.machine(),"reported_architecture":os_info.get("OSArchitecture"),"hostname":platform.node(),"wow64":bool(os.environ.get("PROCESSOR_ARCHITEW6432"))},
      "cpu":_ps("Get-CimInstance Win32_Processor|Select -First 1 Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,Architecture,VirtualizationFirmwareEnabled|ConvertTo-Json -Compress") or {"model":platform.processor(),"logical_processors":os.cpu_count()},"memory":memory,
      "gpu":gpu,"storage":storage,
      "gpu_compute":detect_gpu_compute(gpu,python_providers=python_installations,msvc=msvc) if deep else None,"resource_pressure":analyze_resources(memory,storage),"msvc":msvc,
      "tools":{name:probe(name,spec) for name,spec in PROBES.items()},"python_installations":python_installations,"dotnet_runtimes":discover_dotnet_runtimes(),"sdk_hints":{k.lower():{"detected":bool(os.environ.get(k)),"path":os.environ.get(k)} for k in keys},
      "environment":safe_environment() if deep else {},"evidence":[Evidence(EvidenceKind.OBSERVED,"local Windows host","read-only scan","Python APIs and CIM")]}

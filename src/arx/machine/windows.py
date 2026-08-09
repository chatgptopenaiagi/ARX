import json, os, platform, re, shutil, subprocess
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
    path=shutil.which(spec[0])
    if not path: return ToolRecord(name,False,evidence=[Evidence(EvidenceKind.OBSERVED,"PATH","not found","shutil.which")])
    try:
        p=subprocess.run([path,*spec[1:]],capture_output=True,text=True,timeout=timeout,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        output=(p.stdout+"\n"+p.stderr).strip(); match=re.search(r"(?<!\d)(\d+(?:\.\d+){1,3}(?:[-+._a-zA-Z0-9]*)?)",output)
        return ToolRecord(name,p.returncode==0,match.group(1) if match else None,path,[Evidence(EvidenceKind.OBSERVED,path,(output.splitlines() or [f"exit {p.returncode}"])[0][:300],"safe version probe")],confidence=1 if p.returncode==0 else .7,notes=[] if p.returncode==0 else [f"exit {p.returncode}"])
    except (OSError,subprocess.TimeoutExpired) as exc:
        return ToolRecord(name,True,path=path,evidence=[Evidence(EvidenceKind.UNKNOWN,path,type(exc).__name__,"safe version probe",.5)],confidence=.5,notes=["probe failed"])

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
    return {"generated_at":utc_now(),"os":{"system":platform.system(),"release":platform.release(),"version":platform.version(),"architecture":platform.machine(),"hostname":platform.node(),"wow64":bool(os.environ.get("PROCESSOR_ARCHITEW6432"))},
      "cpu":_ps("Get-CimInstance Win32_Processor|Select -First 1 Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,Architecture,VirtualizationFirmwareEnabled|ConvertTo-Json -Compress") or {"model":platform.processor(),"logical_processors":os.cpu_count()},"memory":memory,
      "gpu":_ps("Get-CimInstance Win32_VideoController|Select Name,AdapterRAM,DriverVersion,VideoProcessor|ConvertTo-Json -Compress") if deep else None,
      "storage":_ps("Get-Volume|Where DriveLetter|Select DriveLetter,FileSystem,Size,SizeRemaining,DriveType|ConvertTo-Json -Compress") if deep else None,
      "tools":{name:probe(name,spec) for name,spec in PROBES.items()},"sdk_hints":{k.lower():{"detected":bool(os.environ.get(k)),"path":os.environ.get(k)} for k in keys},
      "environment":safe_environment() if deep else {},"evidence":[Evidence(EvidenceKind.OBSERVED,"local Windows host","read-only scan","Python APIs and CIM")]}


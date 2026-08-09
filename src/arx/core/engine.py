import platform
from arx.core.models import Capability,Status

def capabilities(machine):
    tools=machine.get("tools",{}); result={}
    mapping={"git":"git","github_cli":"github_cli","python.available":"python","node.available":"node","java.jdk":"javac","dotnet.sdk":"dotnet","cmake":"cmake","ninja":"ninja","adb":"adb","flutter":"flutter","cuda":"cuda","visualstudio.cpp":"msbuild","rust":"rust","go":"go","docker":"docker","android.sdk":"adb"}
    for cap,tool in mapping.items():
        ok=bool(tools.get(tool) and tools[tool].detected);result[cap]=Capability(cap,Status.READY if ok else Status.MISSING,f"{tool} {'detected' if ok else 'not detected'}")
    composites={"python_development":["python.available"],"node_development":["node.available"],"android_java_build":["java.jdk","android.sdk"],"android.native.build":["java.jdk","android.sdk","cmake","ninja"],"flutter.android.build":["flutter","java.jdk","android.sdk","adb"],"windows_cpp_build":["visualstudio.cpp","cmake"],"cuda_compute":["cuda"]}
    for name,deps in composites.items():
        states=[result[d].status for d in deps];status=Status.READY if all(x==Status.READY for x in states) else Status.BLOCKED if all(x==Status.MISSING for x in states) else Status.PARTIAL;missing=[d for d in deps if result[d].status!=Status.READY];result[name]=Capability(name,status,"All dependencies detected" if not missing else "Missing: "+", ".join(missing),deps)
    return result

def compare(machine,software):
    checks=[];blockers=[];warnings=[];arch=software.get("pe",{}).get("architecture");host=machine.get("os",{}).get("architecture",platform.machine()).lower()
    if arch:
        ok=arch=="x86" or arch in host or (arch=="x64" and host in {"amd64","x86_64"});check={"name":"architecture","status":"ready" if ok else "blocked","required":arch,"observed":host,"reason":"Architecture is runnable" if ok else "Target architecture does not match host"};checks.append(check)
        if not ok:blockers.append(check["reason"])
    else:checks.append({"name":"architecture","status":"unknown","reason":"Target did not declare an architecture"});warnings.append("Architecture requirement is unknown")
    if software.get("pe",{}).get("is_dotnet"):
        ready=bool(machine.get("tools",{}).get("dotnet") and machine["tools"]["dotnet"].detected);checks.append({"name":".NET","status":"ready" if ready else "partial","reason":".NET host detected" if ready else "Required .NET version is unknown"})
        if not ready:warnings.append(".NET executable detected but host is absent")
    sig=str(software.get("signature",{}).get("Status",software.get("signature",{}).get("status","unknown"))).lower()
    if sig not in {"valid","unknown"}:warnings.append(f"Authenticode status: {sig}")
    known=[c for c in checks if c["status"]!="unknown"];status="blocked" if blockers else "partial" if warnings else "ready"
    return {"status":status,"score":round(sum(c["status"]=="ready" for c in known)/len(known),2) if known else 0,"checks":checks,"blockers":blockers,"warnings":warnings,"confidence":round(.5+.5*len(known)/max(len(checks),1),2)}


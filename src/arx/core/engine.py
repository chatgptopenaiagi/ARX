import platform,re
from arx.core.models import Capability,Status

def version_satisfies(observed,requirement):
    """Evaluate a conservative subset of version constraints; return None if unknown."""
    if not requirement or requirement=="available":return True
    match=re.fullmatch(r"\s*(>=|>|=|==)?\s*v?(\d+(?:\.\d+){0,3})\s*",str(requirement))
    found=re.search(r"\d+(?:\.\d+){0,3}",str(observed or ""))
    if not match or not found:return None
    left=tuple(int(x) for x in found.group().split("."));right=tuple(int(x) for x in match.group(2).split("."));width=max(len(left),len(right));left+=((0,)*(width-len(left)));right+=((0,)*(width-len(right)))
    return left>right if match.group(1)==">" else left>=right if match.group(1)==">=" else left==right

def capabilities(machine):
    tools=machine.get("tools",{}); result={}
    hints=machine.get("sdk_hints",{})
    mapping={"git":"git","github_cli":"github_cli","python.available":"python","node.available":"node","java.jdk":"javac","dotnet.sdk":"dotnet","cmake":"cmake","ninja":"ninja","adb":"adb","flutter":"flutter","cuda":"cuda","visualstudio.cpp":"msbuild","rust":"rust","go":"go","docker":"docker","android.sdk":"adb"}
    for cap,tool in mapping.items():
        ok=bool(tools.get(tool) and tools[tool].detected)
        if cap=="python.available" and machine.get("python_installations"):ok=any(item.get("healthy") for item in machine["python_installations"])
        if cap=="android.sdk" and not ok:ok=any(hints.get(k,{}).get("detected") for k in ("android_home","android_sdk_root"))
        label="healthy Python runtime" if cap=="python.available" and machine.get("python_installations") else "Android SDK" if cap=="android.sdk" else "CUDA Toolkit compiler (nvcc)" if cap=="cuda" else tool
        result[cap]=Capability(cap,Status.READY if ok else Status.MISSING,f"{label} {'detected' if ok else 'not detected'}")
    composites={"python_development":["python.available"],"node_development":["node.available"],"android_java_build":["java.jdk","android.sdk"],"android.native.build":["java.jdk","android.sdk","cmake","ninja"],"flutter.android.build":["flutter","java.jdk","android.sdk","adb"],"windows_cpp_build":["visualstudio.cpp","cmake"],"cuda_compute":["cuda"]}
    for name,deps in composites.items():
        states=[result[d].status for d in deps];status=Status.READY if all(x==Status.READY for x in states) else Status.BLOCKED if all(x==Status.MISSING for x in states) else Status.PARTIAL;missing=[d for d in deps if result[d].status!=Status.READY];result[name]=Capability(name,status,"All dependencies detected" if not missing else "Missing: "+", ".join(missing),deps)
    if result["cuda"].status==Status.READY:
        result["cuda_compute"]=Capability("cuda_compute",Status.PARTIAL,"CUDA Toolkit compiler detected; driver, GPU, framework, project compatibility, and resource feasibility remain separate",["cuda"])
    else:
        result["cuda_compute"]=Capability("cuda_compute",Status.UNKNOWN,"CUDA compute chain is unknown; nvcc absence does not prove the NVIDIA driver or framework runtime is absent",["cuda"])
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
    capmap=capabilities(machine)
    aliases={"npm":"npm","android.runtime":None}
    for requirement in software.get("requirements",[]):
        name=requirement.get("capability");cap=capmap.get(name)
        if name=="dotnet.runtime":
            framework=requirement.get("framework");required=requirement.get("version");matching=[item for item in machine.get("dotnet_runtimes",[]) if not framework or item.get("name")==framework];ready=any(version_satisfies(item.get("version"),f">={required}") for item in matching) if required else bool(matching)
            observed=", ".join(f"{item.get('name')} {item.get('version')}" for item in matching) or "not detected";check={"name":name,"status":"ready" if ready else "blocked","required":f"{framework or ''} {required or ''}".strip(),"observed":observed,"reason":"Required .NET runtime detected" if ready else "Required .NET runtime not detected","evidence_status":requirement.get("status","unknown")};checks.append(check)
            if not ready:blockers.append(check["reason"])
            continue
        if cap is None and name in aliases and aliases[name]:
            tool=machine.get("tools",{}).get(aliases[name]);ready=bool(tool and tool.detected)
        elif cap is None:
            checks.append({"name":name,"status":"unknown","reason":"ARX has no deterministic host rule for this requirement","evidence_status":requirement.get("status","unknown")});warnings.append(f"Cannot evaluate {name}");continue
        else:ready=cap.status==Status.READY
        required=requirement.get("version","available");tool_name={"node.available":"node","python.available":"python","java.jdk":"javac","dotnet.sdk":"dotnet"}.get(name,aliases.get(name));record=machine.get("tools",{}).get(tool_name) if tool_name else None
        version_ok=version_satisfies(record.version if record else None,required) if ready else False
        if ready and version_ok is None:
            check={"name":name,"status":"unknown","required":required,"observed":record.version if record else None,"reason":"Version constraint is not safely comparable","evidence_status":requirement.get("status","unknown")};checks.append(check);warnings.append(f"Cannot compare {name} version constraint {required}");continue
        ready=ready and bool(version_ok)
        reason=f"{name} detected and version satisfies requirement" if ready else f"{name} not detected or version requirement not met"
        check={"name":name,"status":"ready" if ready else "blocked","required":required,"observed":record.version if record else None,"reason":reason,"evidence_status":requirement.get("status","unknown")};checks.append(check)
        if not ready:blockers.append(check["reason"])
    sig=str(software.get("signature",{}).get("Status",software.get("signature",{}).get("status","unknown"))).lower()
    if sig not in {"valid","unknown"}:warnings.append(f"Authenticode status: {sig}")
    known=[c for c in checks if c["status"]!="unknown"];status="blocked" if blockers else "partial" if warnings else "ready"
    return {"status":status,"score":round(sum(c["status"]=="ready" for c in known)/len(known),2) if known else 0,"checks":checks,"blockers":blockers,"warnings":warnings,"confidence":round(.5+.5*len(known)/max(len(checks),1),2)}

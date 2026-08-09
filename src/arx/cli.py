import argparse,json,sys
from pathlib import Path
from arx import __version__
from arx.core.engine import capabilities,compare
from arx.core.evidence import redact
from arx.core.models import serialize,utc_now
from arx.machine import scan_machine
from arx.software import scan_software

def envelope(machine=None,software=None,compatibility=None):return redact(serialize({"schema_version":"0.1","scanner":{"name":"ARX","version":__version__},"machine":machine,"software":software,"compatibility":compatibility,"generated_at":utc_now()}))
def parser():
    p=argparse.ArgumentParser(prog="arx",description="ARX pre-installation compatibility intelligence");p.add_argument("-o","--output",type=Path);s=p.add_subparsers(dest="command",required=True)
    for name in ("quick","deep","codex"):s.add_parser(name)
    for name in ("inspect","compare"):q=s.add_parser(name);q.add_argument("target")
    return p
def quick(caps):
    labels={"git":"Git","python.available":"Python","node.available":"Node.js","java.jdk":"Java JDK","android.sdk":"Android SDK","android.native.build":"Android Native Build","flutter.android.build":"Flutter Android","dotnet.sdk":".NET SDK","windows_cpp_build":"Visual C++ Build","cuda_compute":"CUDA Compute"}
    return "ARX - Quick Scan\n\n"+"\n".join(f"[{caps[k].status.value.upper():<9}] {v:<24} {caps[k].reason}" for k,v in labels.items())
def inspect_text(software,compat=None):
    pe=software.get("pe",{});sig=software.get("signature",{});lines=["ARX",f"Target: {software['filename']}",f"SHA256: {software.get('sha256','n/a')}",f"Type: {software['detected_file_type']}",f"Architecture: {pe.get('architecture','unknown')}",f"Signature: {sig.get('Status',sig.get('status','not inspected'))}"]
    if pe:lines += [f"Subsystem: {pe.get('subsystem')}",f".NET indicator: {pe.get('is_dotnet')}",f"Requested level: {pe.get('requested_execution_level') or 'not detected'}","Imported libraries: "+(", ".join(pe.get("imports",[])[:20]) or "none detected")]
    if compat:lines += [f"Machine compatibility: {compat['status'].upper()}"]+(["Blockers: "+"; ".join(compat["blockers"])] if compat["blockers"] else [])+(["Warnings: "+"; ".join(compat["warnings"])] if compat["warnings"] else [])
    return "\n".join(lines)
def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=="quick":machine=scan_machine(False);caps=capabilities(machine);data=envelope(machine=machine);text=quick(caps)
        elif args.command=="deep":data=envelope(machine=scan_machine(True));text=json.dumps(data,indent=2)
        elif args.command=="codex":
            machine=scan_machine(True);caps=capabilities(machine);data=redact(serialize({"schema_version":"0.1","scanner":{"name":"ARX","version":__version__},"generated_at":utc_now(),"host":{"os":machine["os"],"cpu":machine.get("cpu"),"memory":machine.get("memory")},"capabilities":{k:{"status":v.status.value,"reason":v.reason,"requires":v.dependencies} for k,v in caps.items()},"tools":{k:{"detected":v.detected,"version":v.version,"path":v.path} for k,v in machine["tools"].items()},"important_gaps":[k for k,v in caps.items() if v.status in {__import__('arx.core.models',fromlist=['Status']).Status.MISSING,__import__('arx.core.models',fromlist=['Status']).Status.PARTIAL,__import__('arx.core.models',fromlist=['Status']).Status.BLOCKED}]}));text=json.dumps(data,indent=2)
        elif args.command=="inspect":software=scan_software(args.target);data=envelope(software=software);text=inspect_text(software)
        else:machine=scan_machine(True);software=scan_software(args.target);compat=compare(machine,software);data=envelope(machine,software,compat);text=inspect_text(software,compat)
        if args.output:args.output.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8");print(f"Report written to {args.output}",file=sys.stderr)
        print(text);return 0
    except (FileNotFoundError,PermissionError) as exc:print(f"arx: {exc}",file=sys.stderr);return 2
    except KeyboardInterrupt:return 130

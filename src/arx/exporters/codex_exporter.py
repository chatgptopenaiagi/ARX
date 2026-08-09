from arx.core.evidence import redact
from arx.core.models import Status,serialize,utc_now

def codex_report(machine,caps,version):
    return redact(serialize({"schema_version":"0.1","scanner":{"name":"ARX","version":version},"generated_at":utc_now(),"host":{"os":machine["os"],"cpu":machine.get("cpu"),"memory":machine.get("memory")},"capabilities":{k:{"status":v.status.value,"reason":v.reason,"requires":v.dependencies} for k,v in caps.items()},"tools":{k:{"detected":v.detected,"version":v.version,"path":v.path} for k,v in machine["tools"].items()},"python_installations":machine.get("python_installations",[]),"unhealthy_python_installations":[item for item in machine.get("python_installations",[]) if not item.get("healthy")],"important_gaps":[k for k,v in caps.items() if v.status in {Status.MISSING,Status.PARTIAL,Status.BLOCKED}]}))

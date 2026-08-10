import os, re
from pathlib import Path
from typing import Any
SENSITIVE=re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL|COOKIE)",re.I)
def redact_path(value:str,private_roots=None)->str:
    result=value
    for root in sorted((str(Path(item)) for item in (private_roots or []) if item),key=len,reverse=True):
        result=re.sub(re.escape(root),"%PROJECT_ROOT%",result,flags=re.I)
    profile=os.environ.get("USERPROFILE")
    return re.sub(re.escape(str(Path(profile))),"%USERPROFILE%",result,flags=re.I) if profile else result
def safe_environment(env=None):
    allowed={"PATH","PATHEXT","PROCESSOR_ARCHITECTURE","PROCESSOR_IDENTIFIER","OS","TEMP","TMP","JAVA_HOME","ANDROID_HOME","ANDROID_SDK_ROOT","CUDA_PATH","VULKAN_SDK"}
    return {k:("<redacted>" if SENSITIVE.search(k) else redact_path(v)) for k,v in (env or dict(os.environ)).items() if k.upper() in allowed}
def redact(value:Any,private_roots=None)->Any:
    if isinstance(value,str): return redact_path(value,private_roots)
    if isinstance(value,list): return [redact(v,private_roots) for v in value]
    if isinstance(value,dict): return {k:("<redacted>" if SENSITIVE.search(k) else redact(v,private_roots)) for k,v in value.items()}
    return value


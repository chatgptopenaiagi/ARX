import os, re
from pathlib import Path
from typing import Any
SENSITIVE=re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL|COOKIE)",re.I)
def redact_path(value:str)->str:
    profile=os.environ.get("USERPROFILE")
    return re.sub(re.escape(str(Path(profile))),"%USERPROFILE%",value,flags=re.I) if profile else value
def safe_environment(env=None):
    allowed={"PATH","PATHEXT","PROCESSOR_ARCHITECTURE","PROCESSOR_IDENTIFIER","OS","TEMP","TMP","JAVA_HOME","ANDROID_HOME","ANDROID_SDK_ROOT","CUDA_PATH","VULKAN_SDK"}
    return {k:("<redacted>" if SENSITIVE.search(k) else redact_path(v)) for k,v in (env or dict(os.environ)).items() if k.upper() in allowed}
def redact(value:Any)->Any:
    if isinstance(value,str): return redact_path(value)
    if isinstance(value,list): return [redact(v) for v in value]
    if isinstance(value,dict): return {k:("<redacted>" if SENSITIVE.search(k) else redact(v)) for k,v in value.items()}
    return value


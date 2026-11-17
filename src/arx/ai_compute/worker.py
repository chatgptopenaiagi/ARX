"""Fixed, stdlib-only bootstrap sent to each selected Python interpreter.

Keeping the source as data also works in the frozen desktop without importing
the host's torch or depending on source .py files beside the executable.
"""

SOURCE = r'''
import importlib, importlib.util, importlib.metadata as md, json, os, platform, site, sys, sysconfig, time
from pathlib import Path
config=json.loads(sys.argv[1]); mode=config.get("mode","inventory")
if config.get("user_site"):
    sys.path.insert(0,site.getusersitepackages())
result={"python":{"executable":sys.executable,"version":platform.python_version(),"prefix":sys.prefix,"base_prefix":sys.base_prefix,"architecture":platform.machine(),"bits":64 if sys.maxsize>2**32 else 32,"scripts_path":sysconfig.get_path("scripts"),"user_site":site.getusersitepackages(),"user_site_enabled":bool(config.get("user_site")),"site_paths":sys.path},"packages":[],"tests":[],"benchmarks":[]}
def clean(value):
    import re
    return re.sub(r"(?i)(https?://)[^\s/@]+:[^\s/@]+@",r"\1[REDACTED]@",str(value))[:3000]
def test(name,fn):
    started=time.perf_counter()
    try:
        detail=fn(); row={"name":name,"status":"FUNCTIONAL","outcome":"PASS","detail":detail}
    except Exception as exc:
        row={"name":name,"status":"FAILED","outcome":"FAIL","error":clean(type(exc).__name__+": "+str(exc))}
    row["elapsed_ms"]=round((time.perf_counter()-started)*1000,4);result["tests"].append(row);return row
def unavailable(name,reason):
    result["tests"].append({"name":name,"status":"UNAVAILABLE","outcome":"NOT TESTED","reason":reason})
def core():
    import ssl, ctypes, sqlite3
    return {"ssl":ssl.OPENSSL_VERSION,"sqlite":sqlite3.sqlite_version}
test("python_core_imports",core)
for distribution in list(md.distributions())[:2048]:
    name=distribution.metadata.get("Name","")
    if not name: continue
    root=Path(distribution.locate_file("")).resolve()
    record={"name":name,"version":distribution.version,"root":str(root),"metadata_path":str(getattr(distribution,"_path","")),"requires":list(distribution.requires or []),"status":"INSTALLED"}
    if config.get("files"):
        listed=list(distribution.files or [])
        record["files"]=[str(Path(distribution.locate_file(p)).resolve()) for p in listed[:100000]]
        record["files_truncated"]=len(listed)>100000
        record["files_unavailable"]=not bool(listed)
    result["packages"].append(record)
result["packages"].sort(key=lambda d:d["name"].lower())
if mode=="inventory":
    print("ARX_AI_JSON:"+json.dumps(result));sys.exit(0)
modules={}
for name in ("torch","numpy","torchvision","torchaudio","onnxruntime","tensorrt"):
    def load(name=name):
        module=importlib.import_module(name);modules[name]=module
        return {"version":str(getattr(module,"__version__","unknown")),"path":str(getattr(module,"__file__","unknown")),"status":"IMPORTABLE"}
    if importlib.util.find_spec(name) is None:
        unavailable(name+"_import","Module not found in this interpreter context")
    else:
        test(name+"_import",load)
if "onnxruntime" in modules:
    test("onnxruntime_providers",lambda:modules["onnxruntime"].get_available_providers())
    result["onnxruntime_note"]="Provider enumeration does not verify model inference or GPU execution"
if mode=="providers":
    print("ARX_AI_JSON:"+json.dumps(result));sys.exit(0)
torch=modules.get("torch")
if torch is None:
    print("ARX_AI_JSON:"+json.dumps(result));sys.exit(0)
torch.set_num_threads(min(4,os.cpu_count() or 1));torch.manual_seed(2026)
result["torch"]={"version":str(torch.__version__),"path":torch.__file__,"cuda_runtime":torch.version.cuda,"cuda_available":torch.cuda.is_available(),"cudnn_available":torch.backends.cudnn.is_available(),"cudnn_version":torch.backends.cudnn.version(),"device_count":torch.cuda.device_count(),"cpu_threads":torch.get_num_threads()}
lib=Path(torch.__file__).parent/"lib"
result["runtime_libraries"]=[{"path":str(p),"scope":"environment-bundled","status":"DETECTED"} for p in list(lib.glob("*.dll"))[:4096] if p.name.lower().startswith(("cudnn","cudart","cublas","torch_cuda","nvrtc"))]
def numpy_interop():
    np=modules["numpy"]; source=np.arange(16,dtype=np.float32)
    tensor=torch.from_numpy(source);tensor[0]=42
    assert source[0]==42 and np.array_equal(tensor.numpy(),source)
    return {"shared_memory_roundtrip":True,"numpy_version":np.__version__}
test("numpy_interoperability",numpy_interop)
def cpu_tensor():
    x=torch.arange(4096,dtype=torch.float32); y=x*2+1
    assert y[-1].item()==8191
    return {"shape":list(y.shape),"device":"cpu"}
test("cpu_tensor",cpu_tensor)
gpu_ok=result["torch"]["cuda_available"]
device_index=int(config.get("device",0))
device="cuda:"+str(device_index)
if gpu_ok:
    try:
        torch.cuda.set_device(device_index)
        prop=torch.cuda.get_device_properties(device_index); free,total=torch.cuda.mem_get_info(device_index)
        result["gpu"]={"name":prop.name,"device":device,"capability":list(torch.cuda.get_device_capability(device_index)),"total_memory":total,"free_memory_before":free}
        # A strict allocator budget in this child; context/driver memory is separate.
        budget=min(256*1024**2,free//4)
        result["gpu"]["allocator_budget_bytes"]=budget
        if budget<64*1024**2: raise RuntimeError("Less than 256 MiB GPU memory free; bounded verification deferred")
        torch.cuda.set_per_process_memory_fraction(min(0.25,budget/total),device_index)
    except Exception as exc:
        gpu_ok=False;result["gpu_gate"]={"status":"UNAVAILABLE","reason":clean(exc)}
def gpu_tensor():
    x=torch.arange(4096,device=device,dtype=torch.float32); y=x+1;torch.cuda.synchronize()
    assert y[-1].item()==4096
    return {"shape":list(y.shape),"device":device,"peak_allocated_bytes":torch.cuda.max_memory_allocated()}
def gpu_matrix():
    # Reproduce the operator's shape, then compare a deterministic CPU reference.
    x=torch.randn(1024,1024,device=device); y=x@x;torch.cuda.synchronize()
    assert y.shape==(1024,1024) and bool(torch.isfinite(y).all().item())
    small=torch.arange(64*64,dtype=torch.float32).reshape(64,64)/4096
    actual=(small.to(device)@small.to(device)).cpu()
    torch.testing.assert_close(actual,small@small,rtol=1e-3,atol=1e-4)
    return {"shape":list(y.shape),"device":device,"reference_checked":True,"peak_allocated_bytes":torch.cuda.max_memory_allocated()}
def cudnn_convolution():
    if not torch.backends.cudnn.is_available(): raise RuntimeError("cuDNN unavailable")
    x=torch.randn(1,4,32,32,device=device); weight=torch.randn(8,4,3,3,device=device)
    # This explicit backend operator cannot silently use a non-cuDNN fallback.
    y=torch.ops.aten.cudnn_convolution(x,weight,[1,1],[1,1],[1,1],1,False,True,False)
    torch.cuda.synchronize()
    expected=torch.nn.functional.conv2d(x.cpu(),weight.cpu(),padding=1)
    torch.testing.assert_close(y.cpu(),expected,rtol=1e-3,atol=1e-4)
    return {"backend":"aten::cudnn_convolution","shape":list(y.shape),"reference_checked":True,"peak_allocated_bytes":torch.cuda.max_memory_allocated()}
if gpu_ok:
    test("gpu_tensor",gpu_tensor);test("gpu_matrix",gpu_matrix)
    test("cuda_synchronize",lambda:(torch.cuda.synchronize() or {"device":device}))
    test("cudnn_convolution",cudnn_convolution)
else:
    for name in ("gpu_tensor","gpu_matrix","cuda_synchronize","cudnn_convolution"):
        unavailable(name,result.get("gpu_gate",{}).get("reason","CUDA not available in this environment"))
if mode=="benchmark":
    versions={p["name"]:p["version"] for p in result["packages"] if p["name"].lower() in ("torch","numpy","torchvision","torchaudio")}
    def bench(name,fn,target,shape,bytes_count=None):
        row={"name":name,"device":target,"dimensions":shape,"dtype":"float32","iterations":3,"warmups":1,"package_versions":versions,"cuda_runtime":torch.version.cuda,"cudnn_version":torch.backends.cudnn.version(),"timing":"perf_counter with CUDA synchronization on both sides for GPU/transfer operations","peak_allocated_gpu_bytes":0}
        try:
            fn()
            times=[]
            if target!="cpu": torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
            for _ in range(3):
                if target!="cpu":torch.cuda.synchronize()
                start=time.perf_counter();value=fn()
                if target!="cpu":torch.cuda.synchronize()
                times.append((time.perf_counter()-start)*1000)
                del value
            row.update(status="BENCHMARKED",outcome="PASS",samples_ms=times,mean_ms=sum(times)/len(times),peak_allocated_gpu_bytes=torch.cuda.max_memory_allocated() if target!="cpu" else 0)
            if bytes_count:row["bytes_per_operation"]=bytes_count
        except Exception as exc:row.update(status="FAILED",outcome="FAIL",error=clean(exc))
        result["benchmarks"].append(row)
    cpu=torch.randn(512,512)
    bench("cpu_tensor_operations",lambda:cpu*1.01+0.5,"cpu",[512,512])
    if gpu_ok:
        gpu=cpu.to(device);x=torch.randn(1,4,32,32,device=device);w=torch.randn(8,4,3,3,device=device)
        bench("gpu_tensor_operations",lambda:gpu*1.01+0.5,device,[512,512])
        bench("cpu_to_gpu",lambda:cpu.to(device),"cpu -> "+device,[512,512],cpu.numel()*cpu.element_size())
        bench("gpu_to_cpu",lambda:gpu.cpu(),device+" -> cpu",[512,512],gpu.numel()*gpu.element_size())
        bench("gpu_matrix_multiplication",lambda:gpu@gpu,device,[512,512])
        bench("cudnn_convolution",lambda:torch.ops.aten.cudnn_convolution(x,w,[1,1],[1,1],[1,1],1,False,True,False),device,[1,4,32,32])
    else:
        for name in ("gpu_tensor_operations","cpu_to_gpu","gpu_to_cpu","gpu_matrix_multiplication","cudnn_convolution"):
            result["benchmarks"].append({"name":name,"status":"UNAVAILABLE","outcome":"NOT TESTED","reason":"GPU gate did not pass"})
print("ARX_AI_JSON:"+json.dumps(result))
'''

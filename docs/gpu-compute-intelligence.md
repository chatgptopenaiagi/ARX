# Layered GPU and CUDA intelligence

ARX never reduces NVIDIA compute readiness to “CUDA installed: yes.” Machine DNA records a compatibility chain whose component facts remain independently inspectable:

1. NVIDIA GPU hardware and Windows visibility
2. NVIDIA driver health and `nvidia-smi` resolution
3. the CUDA API/runtime ceiling advertised by the driver
4. independently discovered CUDA Toolkit providers and the `nvcc` that resolves in the current environment
5. CUDA runtime-library providers, kept distinct from development import/link libraries
6. independent cuDNN and TensorRT providers
7. framework builds and actual backend initialization
8. GPU compute-capability coverage when the framework reports its compiled architectures
9. project relevance and resource feasibility

The CUDA version printed by `nvidia-smi` is a driver compatibility level. It is never evidence that the matching CUDA Toolkit is installed. A toolkit requires independent bounded evidence such as a known installation root and its own `nvcc`. Likewise, CUDA libraries bundled inside PyTorch describe that framework environment; they do not establish a global Toolkit.

## Providers and execution context

Multiple CUDA Toolkits are normal. ARX preserves every provider, the provider selected by `CUDA_PATH`, and the provider reached by command resolution. A difference becomes a precise contradiction only when it creates ambiguity or breaks a required relationship. ARX does not automatically remove, reinstall, or reconfigure providers.

Runtime-loadable DLLs and development import/link libraries are different facts. A `.lib` such as `cudart.lib` does not prove that a CUDA runtime DLL is present or usable. The same classification applies to bounded cuDNN and TensorRT inventories. Standalone TensorRT roots may be discovered from explicit environment values, relevant `PATH` entries, or bounded NVIDIA AI installation roots; discovery sources are retained and normalized roots are deduplicated. Version evidence from a directory such as `TensorRT-11.2.1.2` identifies the provider but does not establish compatibility.

A frozen ARX desktop executable is never used as a Python interpreter. Framework probes select a healthy discovered Python provider, exclude unhealthy WindowsApps aliases, and report the exact tested environment. Absence in that provider is not global absence; when no usable provider exists the probe remains not tested.

Machine DNA distinguishes an installed MSVC provider and physical `cl.exe` from command resolution in the current process. A discovered `vcvars64.bat` or `VsDevCmd.bat` can support a read-only explanation of a recoverable Visual Studio developer context, but ARX does not activate it or mutate the environment. Thus provider presence is not current resolution, and current-context failure is not permanent machine incapability.

Trusted probes use fixed executable paths and argument arrays, `shell=False`, timeouts, bounded retained/report output, and explicit failure states. Captured bytes are normalized for UTF-8, UTF-16, and bounded Windows legacy output; the current subprocess wrapper does not claim streaming-bounded OS pipe capture. The framework probe runs through the selected trusted Python with isolated interpreter flags. It checks only recognized PyTorch, ONNX Runtime, and TensorRT APIs and never imports project code.

When Windows and healthy NVIDIA tooling report materially different VRAM values for a safely correlated NVIDIA adapter, both observations remain evidence and ARX emits `GPU_VRAM_SOURCE_DISAGREEMENT`. This is source disagreement, not a hardware-fault diagnosis; WMI `AdapterRAM` can be limited or unreliable for modern adapters.

## Independent verdict dimensions

Presence, health, resolution, compatibility, project relevance, resource feasibility, and verification level remain separate dimensions. UNKNOWN is a valid result when ARX lacks a deterministic relationship—for example, exact cuDNN/TensorRT compatibility, an unavailable compiled-SM list, or a missing project VRAM requirement.

PyTorch is represented as distinct facts: package presence, CPU-only or CUDA build, compiled CUDA family, CUDA initialization, enumerated devices, compute capability, compiled SM coverage, and workload VRAM feasibility. CUDA initialization does not prove that a workload fits in VRAM.

## Evidence and knowledge

Fact provenance continues to use only `DECLARED`, `OBSERVED`, `INFERRED`, and `UNKNOWN`. Semantic verification is a separate concept; `VERIFIED` is not an `EvidenceKind`. Numeric confidence values are detector-authored heuristic weights, not calibrated probabilities.

Compatibility rules live in the versioned offline knowledge file `src/arx/knowledge/gpu_compatibility.json`. Normal scans do not fetch internet data, and ordinary numeric ordering is not treated as proof of CUDA compatibility.

## Resource pressure

Machine DNA reports disk and memory pressure independently from software compatibility. Disk observations include total/free bytes and percentages; consequences such as build, extraction, package-installation, temporary-file, model-download, and Windows Update pressure are inferred separately. Memory utilization describes current pressure, not permanent incompatibility. Disk preflight returns UNKNOWN unless enough workflow-size evidence exists to compare required download, extraction, installation, and temporary headroom with actual free space.

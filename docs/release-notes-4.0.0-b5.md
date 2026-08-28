# ARX 4.0.0 Beta 5

Package version: `4.0.0b5`

Artifact version: `4.0.0-b5`

Windows file/product version: `4.0.0.5`

Git tag: `v4.0.0-b5`

Release channel: **Beta / GitHub Latest; not ARX 4 stable**

ARX 4.0.0 Beta 5 rebuilds GPU and CUDA compatibility intelligence around a layered, evidence-backed provider model. ARX no longer treats CUDA as one installed/not-installed fact. The compatibility chain now keeps NVIDIA GPU hardware, the NVIDIA driver, the driver-advertised CUDA capability, installed CUDA Toolkit providers, resolved `nvcc`, CUDA runtime libraries, cuDNN, TensorRT, framework GPU providers, GPU compute capability/SM, project requirements, and resource feasibility distinct.

> **NVIDIA driver CUDA capability is not an installed CUDA Toolkit.** A CUDA level reported by `nvidia-smi` describes the driver's advertised API/runtime ceiling. Toolkit installation is established independently through bounded Toolkit evidence.

## Layered GPU compute intelligence

- Adds structured `gpu_compute` Machine DNA with independent hardware, driver, Toolkit, runtime, library, framework, execution-context, contradiction, and resource-pressure records.
- Preserves multiple NVIDIA GPUs and multiple CUDA Toolkit providers instead of collapsing them into a single version or Boolean.
- Records the `nvcc` provider that resolves in the active context separately from providers advertised by `CUDA_PATH`, versioned CUDA environment variables, registry information, and trusted installation roots.
- Identifies major CUDA runtime libraries, cuDNN, and TensorRT providers with path, version, architecture, source, and global versus framework-private scope where bounded evidence permits.
- Adds safe adapters for PyTorch, ONNX Runtime GPU, and TensorRT Python. PyTorch evidence distinguishes package presence, a CUDA-enabled build, backend initialization, visible devices, and reported device capability.
- Models compute capability/SM support conservatively. Exact support is reported only with deterministic evidence; otherwise the result remains UNKNOWN.
- Detects precise contradictions such as a Windows-visible NVIDIA GPU missing from NVIDIA tooling, a Toolkit whose compiler does not resolve, `CUDA_PATH` disagreement, a PyTorch CUDA build whose backend cannot initialize, and TensorRT whose required runtime relationship is unresolved.
- Recognizes bounded static GPU-related project dependencies without importing or executing project code.

## Compatibility and feasibility semantics

GPU findings retain independent presence, health, resolution, compatibility, project relevance, resource feasibility, and verification dimensions. UNKNOWN is a first-class result and describes which missing evidence could resolve it. Heuristic evidence weights are not presented as calibrated probabilities.

Resource feasibility remains separate from compatibility. ARX records VRAM capacity and pressure, current physical-memory pressure, and system-drive pressure. It does not invent model memory requirements or treat current resource pressure as permanent machine incompatibility. Estimates, where supported by explicit inputs, remain visibly ESTIMATED rather than OBSERVED.

## Reports, desktop, and provenance

- Integrates the layered model into JSON reports, the Machine DNA compute summary, and the Windows GPU/AI Compute view.
- Keeps Evidence Inspector references connected to derived findings and preserves the source-defined evidence provenance enum. Semantic verification remains separate from fact provenance.
- Centralizes versioned CUDA/framework compatibility knowledge with authority, knowledge date, scope, constraint, and rule quality instead of scattering version constants through detectors.
- Keeps AI advisory output non-authoritative. AI may explain bounded redacted ARX evidence, but cannot create observed facts, mutate Machine or Project DNA, change deterministic compatibility, or promote UNKNOWN to GREEN.

## Packaging and supply chain

Windows release tooling now accepts stable (`X.Y.Z`), release-candidate (`X.Y.ZrcN`), and Beta (`X.Y.ZbN`) package versions through shared normalization. For this release, `4.0.0b5` maps to artifact version `4.0.0-b5`, display name `ARX 4.0.0 Beta 5`, and numeric Windows version `4.0.0.5`.

The Windows binaries in this release are unsigned. Their expected state is `UNSIGNED_EXPECTED_PRE_SIGNING` because no approved publisher-controlled production signing identity was used. SHA-256 manifests, SBOM data, CodeQL, deterministic tests, and security gates provide separate evidence; none constitutes Authenticode signing.

## Security model

ARX remains read-only and advisory. Inspected applications and project code are not executed. Trusted diagnostics use fixed commands and argument arrays, `shell=False`, bounded timeouts and output, controlled decoding, and explicit failure records. ARX does not install drivers or packages, edit PATH or the registry, uninstall runtimes, or apply recovery recommendations.

## Remaining UNKNOWN and limitations

- GPU compute capability remains UNKNOWN when neither a trusted framework/device probe nor authoritative device mapping supplies it.
- Framework binary SM coverage can remain UNKNOWN when the installed framework does not expose its compiled architecture list.
- cuDNN and TensorRT compatibility remains UNKNOWN when version metadata or runtime relationships cannot be established safely.
- Project VRAM feasibility remains UNKNOWN without trustworthy workload/model requirements; ARX does not manufacture an exact requirement.
- NVIDIA driver/toolkit/framework compatibility is not inferred from naive numeric ordering.
- Real multi-monitor/DPI, complete screen-reader accessibility, and the full interactive install/upgrade/uninstall lifecycle remain manual acceptance gates.
- Windows Server, Windows ARM64, and non-Windows desktop packaging have not received equivalent release acceptance.

Beta 5 is intended for evaluation and development feedback. It is not ARX 4 stable and makes no universal claim that every CUDA, TensorRT, cuDNN, or framework combination is compatible.

# AI Compute

AI Compute is an explicit, local workflow alongside the existing read-only
machine and project scanners. It inventories Python environments, runs bounded
tests in the selected interpreter, benchmarks small workloads, and copies
installed package files into a unique preservation directory. It never installs
frameworks, changes PATH, replaces drivers, or changes an existing environment.

## Desktop

Open **AI Compute**, select **Discover environments**, and select a Python
environment. **Add search folder** includes another bounded search root.
**Verify selected** runs imports and functional tests. **Benchmark selected**
adds six short benchmarks. Each selected environment has its own evidence and
timestamp; choosing another environment never carries over a successful result.

**Preserve selected** writes a unique snapshot under the displayed preservation
destination. **Choose destination** changes the parent for future snapshots.
Cancellation retains completed copies and records an incomplete snapshot; it
does not delete or move source files. **Export reports** writes the seven report
files. **Load saved evidence** labels the display as historical evidence; run
verification to refresh it.

The desktop also accepts `--ai-report PATH_TO_INVENTORY_JSON` to open saved
results directly. A separately built portable application can be used alongside
an existing installed ARX version.

## Command line and Python API

```powershell
arx ai-compute --verify --benchmark --reports-dir C:\ARX-Evidence\AI
arx ai-compute --python C:\Python315\python.exe --verify --preserve --preserve-to D:\AI-Backups
python -m arx.ai_compute --root C:\Development --verify
```

Preservation from the CLI requires exactly one explicit interpreter and a fully
verified isolated context. GUI preservation can also capture a partially working
environment for diagnosis; the verification outcome remains separate.

```python
from arx.ai_compute import discover, verify, preserve, write_reports

report = discover(extra_roots=[r"C:\Development"])
environment = report["environments"][0]  # Select the intended interpreter.
report["verification"].append(verify(environment, benchmark=True))
report["preservation"].append(preserve(environment, r"D:\AI-Backups"))
write_reports(report, r"C:\ARX-Evidence\AI")
```

The CLI returns 2 if requested verification is incomplete, including environments
that lack companion packages, or if preservation is incomplete. That does not
mean an existing CPU-only or torch-only installation should be replaced.

## Discovery and evidence

Discovery consults PATH, the Python launcher, both Windows registry views,
known system/profile Python locations, virtual-environment layouts, Conda's
environment registry, and bounded development roots. Explicit roots take
priority. Directory links, package caches, standard-library trees, node_modules,
and preserved snapshots are not recursively followed. The default traversal
budget is 12,000 entries, depth 5, and 12 seconds; interpreter count is capped at
64. Absence outside that scope is not proof of uninstallation.

Each interpreter runs a fixed probe with `-I -B` from a temporary neutral
directory. This ignores inherited PYTHONHOME/PYTHONPATH, avoids importing project
scripts from the working directory, and avoids writing Python bytecode. A
separate user-site context is inventoried when it changes the package set.
Frozen builds temporarily clear their DLL search-directory override while
spawning a child, then restore it; this prevents embedded-runtime contamination.
Imports execute code in the selected installed packages, not a submitted project.

Driver version, CUDA Toolkit compiler/version, PyTorch's bundled CUDA runtime,
and cuDNN are separate facts. DLL inventory is detection, not proof of loading.
ONNX Runtime provider enumeration is not model inference. TensorRT import or
library detection is not functional inference verification.

States are explicit: DETECTED, INSTALLED, IMPORTABLE, FUNCTIONAL, BENCHMARKED,
PRESERVED, UNAVAILABLE, UNTESTED, FAILED. Overall VERIFIED requires core Python,
torch, TorchVision and TorchAudio imports, NumPy round-trip interoperability,
GPU tensor/matrix operations, synchronization, and a real cuDNN convolution.

## Functional verification and benchmarks

The matrix test reproduces a 1024 × 1024 CUDA multiplication and also compares
a small deterministic matrix against a CPU reference. cuDNN verification calls
the explicit `aten::cudnn_convolution` backend operator, synchronizes, and checks
the result against CPU convolution. A detected cuDNN version alone never passes
this test. If that operator is unavailable in an older framework, the test fails
explicitly rather than silently accepting another backend.

CPU/GPU elementwise operations, CPU-to-GPU transfer, GPU-to-CPU transfer, GPU
matrix multiplication and cuDNN convolution use one warmup and three measured
iterations. GPU and transfer timing synchronizes before and after each sample;
measurements include host dispatch and allocation, not just kernel time. Reports
include dimensions, dtype, device, versions, samples, mean and peak torch GPU
allocation. The allocator budget is at most 256 MiB and one quarter of free
memory. Work is deferred with less than 256 MiB free. Driver/context memory is
outside the torch allocator measurement. Each verification child has a 120-second
deadline. CUDA device 0 is tested; other devices are only inventoried.

References: [PyTorch CUDA timing](https://docs.pytorch.org/docs/stable/notes/cuda.html),
[peak memory statistics](https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.reset_peak_memory_stats.html),
[cuDNN operator declaration](https://github.com/pytorch/pytorch/blob/main/tools/autograd/derivatives.yaml).

## Preservation and restoration

The snapshot contains package versions, installation roots, declared dependency
requirements, pinned requirements, recorded package files, runtime identifiers,
and matching cached wheels. Both pip's wheel cache and wheel-shaped HTTP cache
bodies are inspected without extraction. A matching package version does not
alone establish wheel ABI/platform compatibility; review the recorded tags.

Copies use exclusive creation and SHA-256 verification, with source size/mtime
checks during copying. RECORD paths outside declared interpreter/package roots
are rejected. The interpreter's specific sysconfig Scripts location is allowed
even when an existing Windows junction relocates it. Missing/truncated package
records and copying errors prevent a complete preservation result.

Every snapshot has `RESTORE.md`. Use a matching official Python runtime and a
**new** virtual environment. Restore from exact compatible wheels when complete;
otherwise obtain missing exact versions from official sources. Copied package
directories and python.exe/DLLs are **not** a portable installation. Script paths,
compiled extensions, runtime DLLs, ABI and dependencies still matter. Successful
hash verification does not establish a successful restore. Re-run ARX's full
verification after restoration. NVIDIA drivers and system CUDA Toolkits are
inventoried but not bundled in these snapshots.

Reports retain local installation paths needed for selection and restoration;
review them before sharing. Passwords, tokens and credential-manager contents
are not collected. Existing normal ARX exports retain their own redaction policy.

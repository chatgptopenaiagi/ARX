# ARX 4.0.0-beta.7 | AI Compute Edition

Public Windows x64 prerelease based on the verified Mission 20 implementation
at `f334fab88a0ee460f87ac987560bd771533a090c`. Package version `4.0.0b7`,
Windows numeric version `4.0.0.7`, Git tag `v4.0.0-beta.7`.

## Download and run

Download `ARX-4.0.0-beta.7-Windows-x64.zip` and `SHA256SUMS-v4.0.0-beta.7.txt`
from this release. Verify the ZIP's SHA-256, extract the entire archive into
a new directory, then run `ARX-Desktop-win-x64/ARX.exe`. Keep the `_internal`
directory beside the executable. The Python/Tk runtime required by ARX is
included; a separate Python installation is not needed to launch the GUI.

This portable release does not replace the installed ARX application. Existing
Python environments, NVIDIA drivers and AI frameworks remain external.

## AI Compute

- Bounded discovery of Python interpreters, virtual/Conda environments, PyTorch,
  TorchVision, TorchAudio, CUDA toolkits/runtime libraries, cuDNN, GPU devices,
  ONNX Runtime providers and TensorRT installations.
- Select an environment and run isolated import, CUDA tensor/matrix, synchronization,
  NumPy interoperability and explicit cuDNN convolution checks.
- Six short synchronized benchmarks: CPU/GPU tensor operations, transfers in both
  directions, GPU matrix multiplication and cuDNN convolution.
- Copy selected package files and matching cached wheels to a chosen preservation
  destination, verify SHA-256 and document restoration requirements.
- Seven JSON/Markdown evidence reports distinguish detection, importability,
  functional verification, preservation, failures and untested capabilities.

## Verification

Mission 20 independently verified Python 3.15.2, PyTorch 2.15.0+cu134,
TorchVision 0.29.2+cu134, TorchAudio 2.11.1+cu134, CUDA runtime 13.4,
cuDNN 9.26.0 and NVIDIA GeForce RTX 3050. All 11 required checks and six
benchmarks passed. Its regression suite passed 290 tests with one opt-in skip.
Beta 7 release acceptance additionally tests fresh discovery and GPU verification
through the extracted executable, plus the existing quick/deep scan, static
inspection, compatibility, project and export workflows.

## Known limitations

- CUDA/PyTorch are detected from existing local environments, not bundled. The
  5.66 GB workstation preservation snapshot is excluded from this release.
- Results depend on the selected environment. CPU-only environments and missing
  optional packages are reported honestly. The tested older cu132 environment
  lacks TorchVision/TorchAudio; ONNX Runtime/TensorRT were absent in the cu134 target.
- Discovery is bounded, not an exhaustive disk scan. Add a search folder for
  environments outside the default locations.
- GPU execution checks use device 0 and small workloads; benchmark results are
  not sustained-stress or application-performance guarantees.
- Preserved package files are not a portable Python installation. Restoration
  requires compatible Python/ABI/platform packages; restoration was not tested.
- AI evidence contains local paths needed for recovery. Review reports before sharing.
- This unsigned prerelease is tested on Windows 11 x64; this release has not
  been independently validated on Windows 10, Server, ARM64 or a second computer.
- Existing static inspection and compatibility limitations remain; ARX does not
  certify software safety or guarantee arbitrary application startup.

No installer, AI framework, GPU driver or Python-environment backup is included.

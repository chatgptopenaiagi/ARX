# ARX reproducible-build policy

ARX distinguishes raw byte reproducibility from structural equivalence. A successful build is not automatically reproducible, and structural comparison must never be labeled bit-for-bit equality.

## Controlled inputs

Release builds derive `SOURCE_DATE_EPOCH` from the checked-out Git commit timestamp unless an explicit, validated epoch is supplied. This preserves source provenance; it does not invent or rewrite a timestamp. The build scripts also set `PYTHONHASHSEED=0` and `TZ=UTC` for child build tools, then restore the caller's environment.

Windows release builds use CPython 3.12.13 x64 and the exact tool versions in `packaging/release-build-requirements.txt`. `scripts/new-release-environment.ps1` refuses to overwrite an environment or create one inside the checkout, verifies the base interpreter identity, installs that lock, and runs `pip check`. The two-build evidence records the resolved versions independently; a toolchain mismatch blocks comparison rather than producing a reproducibility classification.

The release pipeline uses these controls:

- Python wheel build under the controlled environment;
- bounded sdist reconstruction with ordinal member ordering, source-commit timestamps, zeroed portable owner identity, preserved file bytes/modes, and rejection of traversal or unsupported member types;
- PyInstaller `SOURCE_DATE_EPOCH` support for PE build timestamps and `--noupx` to prevent an ambient UPX installation from changing output;
- an ordinally sorted portable ZIP with every member timestamp normalized to the source commit time;
- fixed checksum-manifest ordering;
- Inno Setup single-threaded LZMA match finding and block compression;
- Inno Setup `notimestamp` file flags and `TimeStampsInUTC=yes`.

Inno Setup documents `notimestamp` specifically as a reproducible-build aid: <https://jrsoftware.org/ishelp/topic_filessection.htm>. Its compression-thread controls are documented at <https://jrsoftware.org/ishelp/topic_setup_compressionthreads.htm>.

## Required experiment

Before release publication, build the same exact candidate commit twice in independent clean worktrees and independent virtual environments with identical frozen tool versions. For every public artifact, record:

- filename, byte length, and SHA-256 from each build;
- whether the hashes are identical;
- structural comparison method when hashes differ;
- the precise remaining source of nondeterminism;
- whether signing has changed the bytes.

Allowed classifications are:

- `BIT_FOR_BIT_REPRODUCIBLE`;
- `STRUCTURALLY_EQUIVALENT`;
- `NOT_REPRODUCIBLE`;
- `UNRESOLVED`.

The portable executable is also compared separately from its containing ZIP. `SHA256SUMS.txt` is classified independently even though its values necessarily follow the artifact bytes. Deterministic sdist reconstruction changes archive metadata only during the candidate build; it does not rewrite a published artifact or alter source-file content.

## Signing boundary

The reproducibility experiment applies to unsigned pre-signing candidates. Production Authenticode and RFC3161 timestamping intentionally change bytes. Final public hashes and attestations must therefore be generated only after signing, and must bind the actual signed bytes. ARX does not patch PE, ZIP, or installer metadata after a build merely to force hashes to match.

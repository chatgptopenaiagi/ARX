# Python package publishing

ARX publishes the Python distribution as `arx-prescanner`. Application version `3.0.0rc1` is a PEP 440 pre-release and is independent from ARX report schemas `0.1` and `0.2`.

The Python package requires Python 3.10 or newer and installs two console entry points:

- `arx` for deterministic CLI inspection and project preflight;
- `arx-desktop` for the Windows Tk desktop application.

The PyPI package, portable Windows ZIP, and Inno Setup installer are separate delivery formats. PyPI serves Python-managed environments. The portable package provides a self-contained `ARX.exe` folder, while the installer integrates that portable payload with Windows Program Files, Start Menu, and uninstall infrastructure.

## Trusted Publishing boundary

`.github/workflows/publish-pypi.yml` is the only workflow authorized to publish Python distributions. It uses GitHub OIDC and the official PyPA publishing action without a stored PyPI username, password, or long-lived API token. A short-lived OIDC identity is exchanged for an index-scoped credential during the publishing job and is never stored in the repository.

The workflow follows this sequence:

```text
explicit existing published release tag
                    |
                    v
       unprivileged build and metadata checks
                    |
                    v
         immutable GitHub Actions artifact
                    |
                    v
    OIDC publish to TestPyPI (testpypi environment)
                    |
                    v
 fresh TestPyPI install and entry-point verification
                    |
                    v
       protected pypi environment approval
                    |
                    v
      OIDC publish of the same files to PyPI
                    |
                    v
 fresh production install and entry-point verification
```

Only the two publishing jobs receive `id-token: write`. The build and verification jobs do not. Normal CI has no publishing permission. The publishing jobs download an already built workflow artifact and invoke the publishing action once; they do not check out or build project source while holding OIDC permission.

Every third-party action is pinned to a full commit SHA. Pull requests, arbitrary branches, `pull_request_target`, reusable workflows, stored publishing credentials, and `skip-existing` are not part of the publishing path.

The public `v3.0.0-rc1` tag predates this publishing workflow and the expanded installation section on `main`. The tag remains immutable: the workflow definition runs from the default branch but checks out and builds the exact tagged source. Consequently, the RC package's PyPI long description is the already verified README stored in that tag; later documentation is not injected into or used to rebuild the tagged source. Future release tags must include their final installation documentation before the tag is published.

## Publisher registration

PyPI and TestPyPI are separate services and require separate publisher registrations. For a new project, register a pending GitHub publisher on each index with these exact claims:

| Field | PyPI | TestPyPI |
|---|---|---|
| Project | `arx-prescanner` | `arx-prescanner` |
| Owner | `chatgptopenaiagi` | `chatgptopenaiagi` |
| Repository | `ARX` | `ARX` |
| Workflow | `publish-pypi.yml` | `publish-pypi.yml` |
| Environment | `pypi` | `testpypi` |

The `pypi` GitHub environment should require a maintainer approval. TestPyPI is the mandatory rehearsal and uses its own `testpypi` environment. A public-index 404 is not proof that a project name is available; pending-publisher registration and the first trusted upload are the authoritative creation boundary.

## Release identity and artifact invariants

Registry publication is never triggered automatically by a GitHub Release. An authorized maintainer must manually dispatch the workflow with an already published release tag. This prevents a GitHub-only release from being uploaded to TestPyPI or PyPI. The workflow then:

1. accepts only a `vX.Y.Z`, `vX.Y.Z-aN`, `vX.Y.Z-bN`, or `vX.Y.Z-rcN` tag;
2. checks out that tag with full history and verifies that `HEAD` is the tag target;
3. verifies that a non-draft GitHub Release exists for the tag;
4. converts the package's PEP 440 version to tag form and requires an exact match;
5. requires package name `arx-prescanner`;
6. builds exactly one wheel and one source distribution;
7. requires strict Twine metadata and README rendering checks;
8. passes the same preserved artifact files through TestPyPI and production PyPI.

PyPI versions and filenames are immutable. A failed or partial upload must be investigated; the workflow does not silently accept duplicates or rebuild a different distribution under an existing version.

## Release gate

Before dispatching publication, run:

```powershell
python -m pip install -e ".[release]"
python -m pytest
python scripts/run-isolated-gui-tests.py
python -m build
python -m twine check --strict dist\*
python -m check_wheel_contents dist\*.whl
git diff --check
```

Inspect the wheel metadata, entry points, contents, and credential scan. Install the wheel in a fresh environment outside the checkout and run `arx --help` and `arx quick`. The automated workflow repeats package construction, strict metadata checks, and clean index installation on GitHub-hosted runners.

For the existing RC release, dispatch from the default branch with:

```console
gh workflow run publish-pypi.yml -f tag=v3.0.0-rc1
```

Do not approve the `pypi` environment until the TestPyPI publish and clean-install verification jobs have passed.

## Installation semantics

Install this exact pre-release from PyPI with:

```console
python -m pip install arx-prescanner==3.0.0rc1
```

`python -m pip install --pre arx-prescanner` opts into pre-release discovery. A normal unpinned `python -m pip install arx-prescanner` becomes the recommended command after stable `3.0.0` exists.

Index installation verification must run outside the source checkout with `PYTHONPATH` unset so the result cannot accidentally import local source.

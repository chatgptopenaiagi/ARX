# Python package publishing

ARX publishes the Python distribution under the existing package identity `arx-prescanner`. The ARX 4.0.0 Beta 4 candidate is package version `4.0.0b4`; if separately approved for an index, it is a new version of the same project already present on both PyPI and TestPyPI. Do not create or rename either project, delete historical files, or replace an existing version. Application versions remain independent from ARX report schemas `0.1` and `0.2`.

## Verified existing publication identity

The release-engineering audit on 2026-08-24 confirmed:

- PyPI and TestPyPI both expose the existing `arx-prescanner` project and historical `3.0.0rc1` version;
- GitHub environments are named `testpypi` and `pypi`, and both require a reviewer;
- the prior `Publish Python package` run completed TestPyPI publication, TestPyPI installation verification, production PyPI publication, and production installation verification through Trusted Publishing;
- the workflow contains no PyPI username, password, long-lived API token, or stored publishing secret;
- the same workflow filename, repository identity, package identity, and environment names are retained so the existing Trusted Publisher configuration is not replaced unnecessarily.

This evidence verifies that the configured OIDC identities worked for the prior version. It does not authorize another upload. The remote publication workflow remains deliberately disabled during ARX 4 Beta 4 preparation and must stay disabled until an explicit Python-index publication decision.

## Separation from GitHub releases

GitHub artifacts and Python-index publication are separate operations:

```text
reviewed tag
   |
   +--> manual release-assets workflow --> draft GitHub prerelease assets
   |
   +--> separate manual publish-pypi workflow
             |
             +--> explicit target: testpypi
             |      publish with OIDC -> compare exact files -> isolated install
             |
             +--> explicit target: production
                    first require exact files on TestPyPI
                    -> protected pypi environment approval
                    -> publish the same reviewed files with OIDC
                    -> compare exact production files
```

Creating or publishing a GitHub Release does not trigger `.github/workflows/publish-pypi.yml`. The workflow has only `workflow_dispatch`; it has no `release`, `push`, `pull_request`, `pull_request_target`, or `workflow_run` publication trigger. Publishing the ARX 4 GitHub prerelease therefore cannot silently publish to either Python index.

The release-assets build job receives OIDC only for GitHub Artifact Attestations and cannot publish a Python package. Its attestation permission is separate from PyPI Trusted Publishing, and it contains no PyPI publishing action or index environment. Only the final attachment job receives `contents: write`, and then only to attach already verified artifacts to an existing empty draft prerelease.

## Trusted Publishing boundary

Both index-publishing jobs use the existing PyPI Trusted Publisher configuration:

| GitHub environment | Existing project | Index | OIDC audience selected by the publishing action |
|---|---|---|---|
| `testpypi` | `arx-prescanner` | TestPyPI | TestPyPI |
| `pypi` | `arx-prescanner` | production PyPI | PyPI |

Only the mutually exclusive publishing jobs receive job-scoped `id-token: write`. Build, release download, checksum, package validation, index verification, and installation jobs receive no OIDC permission. `actions/checkout` uses `persist-credentials: false`, and every third-party action is pinned to a reviewed full commit SHA.

The publishing action exchanges GitHub's short-lived OIDC identity for a short-lived index credential. ARX does not use `PYPI_TOKEN`, `TEST_PYPI_TOKEN`, `TWINE_PASSWORD`, or another stored API-token secret. The `testpypi` and `pypi` environments remain the human review gates for their respective existing publishers.

## Reviewed distribution invariant

The manual publication workflow consumes the wheel and source distribution attached to an existing reviewed, published GitHub release. It does not rebuild source while holding publishing authority. Before either target can run, it:

1. checks out the exact tag with full history and no persisted checkout credential;
2. proves the checkout commit equals the annotated tag target;
3. requires an existing non-draft GitHub Release for that tag;
4. verifies tag, package name, and PEP 440 version identity;
5. downloads the release assets;
6. verifies `SHA256SUMS.txt`, package metadata, console entry points, wheel contents, portable payload shape, and release privacy scan;
7. passes the reviewed wheel and source distribution through an immutable, short-retention GitHub Actions artifact.

The TestPyPI verification job compares the SHA-256 digest and downloaded bytes of both published files with the reviewed GitHub Release files, then installs the exact version in a fresh environment outside the checkout and exercises `import arx`, `arx --help`, `arx quick`, and the `arx-desktop` entry point.

A production-target dispatch does not republish to TestPyPI. It first requires the exact reviewed wheel and source distribution to already exist on TestPyPI, then reaches the separately protected `pypi` environment. The production verification job compares both production files with the reviewed release assets.

## Explicit publication procedure

Neither command below is part of ARX 4 Beta 4 GitHub-release preparation. TestPyPI remains blocked until explicit TestPyPI approval. Production PyPI remains blocked until a separate explicit production approval. Run one only after explicit authorization, after this workflow has reached the approved branch, and after the deliberately disabled workflow has been reviewed and re-enabled.

TestPyPI gate:

```console
gh workflow run publish-pypi.yml --ref main -f tag=v4.0.0-b4 -f target=testpypi
```

Review its build, TestPyPI publication, digest comparison, and isolated-install jobs. Only after that evidence and a separate production authorization may production be selected:

```console
gh workflow run publish-pypi.yml --ref main -f tag=v4.0.0-b4 -f target=production
```

The `pypi` environment review is an additional production gate, not a substitute for the explicit dispatch target or TestPyPI evidence.

## Installation after publication

Install this exact prerelease only after its index publication is confirmed:

```console
python -m pip install arx-prescanner==4.0.0b4
```

`python -m pip install --pre arx-prescanner` opts into prerelease discovery. A normal unpinned install selects the newest stable version and does not opt into Beta 4.

## Security rules

- Never place PyPI/TestPyPI credentials in source, workflow variables, release assets, command-line arguments, or logs.
- Never use a GitHub Release publication event as index-publishing authority.
- Never introduce `pull_request_target` or allow untrusted pull-request code to reach OIDC publication jobs.
- Never enable `skip-existing`; immutable-version collisions are release failures.
- Never delete or replace historical PyPI/TestPyPI releases.
- Never report a successful GitHub Release, TestPyPI upload, or build as production PyPI publication.
- Keep production PyPI blocked until the user explicitly authorizes it.

PyPI's official [Trusted Publishing documentation](https://docs.pypi.org/trusted-publishers/using-a-publisher/) describes the OIDC boundary and recommends job-scoped `id-token: write`. GitHub documents that a published draft prerelease emits the general `published` release event, which is why ARX does not subscribe the PyPI workflow to release events.

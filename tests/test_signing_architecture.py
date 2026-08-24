import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "security" / "signing" / "signing-policy.schema.json"
TEMPLATE = ROOT / "security" / "signing" / "signing-policy.template.json"
VALIDATOR = ROOT / "scripts" / "validate-signing-policy.py"
VERIFIER = ROOT / "scripts" / "verify-authenticode.ps1"


def _load_validator():
    spec = importlib.util.spec_from_file_location("signing_policy_validator", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unconfigured_signing_policy_is_valid_and_secret_free():
    policy = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    _load_validator().validate_policy(policy, schema)
    serialized = json.dumps(policy).casefold()
    assert policy["state"] == "UNCONFIGURED"
    assert policy["certificate_selector"] is None
    for forbidden in ("private_key", "password", "pfx", "api_secret"):
        assert forbidden not in serialized


def test_signing_policy_cli_validates_template():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(TEMPLATE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Signing policy: VALID (UNCONFIGURED)"


@pytest.mark.parametrize(
    "timestamp_url",
    [
        "http://timestamp.example.test/path",
        "https://user@timestamp.example.test/path",
        "https://timestamp.example.test:444/path",
        "https://timestamp.example.test/path?credential=value",
        "https://timestamp.example.test/path#fragment",
    ],
)
def test_configured_policy_rejects_unsafe_timestamp_url(timestamp_url):
    policy = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    policy.update(
        state="CONFIGURED",
        signing_provider="approved-provider",
        certificate_selector={"kind": "provider_key_id", "reference": "public-id"},
        timestamp_url=timestamp_url,
        expected_publisher_subject="CN=Example Publisher",
        expected_issuer_subjects=["CN=Example Issuer"],
    )
    with pytest.raises(ValueError):
        _load_validator().validate_policy(policy, schema)


def test_verifier_is_verification_only_and_fail_closed():
    script = VERIFIER.read_text(encoding="utf-8")
    folded = script.casefold()
    assert "get-authenticodesignature" in folded
    assert "verify /pa /all /tw /v" in folded
    assert "pass_signed" in folded
    assert "unsigned_expected_pre_signing" in folded
    assert "expected_publisher_subject" in folded
    assert "expected_issuer_subjects" in folded
    assert "timestamp certificate is missing" in folded
    assert "x509chain" in folded
    for forbidden in (
        "set-authenticodesignature",
        "certutil -addstore",
        "import-pfxcertificate",
        "signtool sign",
    ):
        assert forbidden not in folded


def test_trust_document_preserves_independent_signals_and_signing_order():
    document = (ROOT / "docs" / "TRUSTED_INSTALLATION.md").read_text(encoding="utf-8")
    folded = document.casefold()
    for signal in (
        "sha-256",
        "authenticode",
        "rfc 3161 timestamp",
        "github artifact attestation",
        "sbom",
        "malware scan",
        "smartscreen / smart app control",
    ):
        assert signal in folded
    assert "1. build the candidate `arx.exe`." in folded
    assert "15. publish." in folded
    assert "blocked_no_production_certificate" in folded
    assert "single `trusted` flag" in folded


def test_security_trust_viewer_is_design_only_and_has_no_combined_badge():
    document = (ROOT / "docs" / "SECURITY_TRUST_VIEWER.md").read_text(encoding="utf-8")
    assert "design only" in document.casefold()
    assert "must not combine" in document.casefold()
    assert "single `TRUSTED`" in document


def test_msix_is_feasibility_only():
    document = (ROOT / "docs" / "MSIX_FEASIBILITY.md").read_text(encoding="utf-8")
    folded = document.casefold()
    assert "feasibility only" in folded
    assert "no store submission" in folded
    assert "classic signed inno setup installer and portable zip" in folded

"""Build the canonical portable-report input from reviewed Beta 1 audit evidence."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

AUDIT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = AUDIT_ROOT / "evidence"

SEVERITY_SQL = """WITH severity_order(severity, ordinal) AS (
    VALUES ('CRITICAL', 1), ('HIGH', 2), ('MEDIUM', 3), ('LOW', 4)
)
SELECT
    s.severity,
    COUNT(f.id) AS count,
    COALESCE(SUM(CASE WHEN f.release_blocking LIKE 'Yes%' THEN 1 ELSE 0 END), 0) AS release_blocking_count,
    COUNT(f.id) - COALESCE(SUM(CASE WHEN f.release_blocking LIKE 'Yes%' THEN 1 ELSE 0 END), 0) AS review_only_count,
    'Reviewed non-informational findings' AS scope
FROM severity_order AS s
LEFT JOIN reviewed_findings AS f ON f.severity = s.severity
GROUP BY s.severity, s.ordinal
ORDER BY s.ordinal"""

TABLE_SQL = {
    "security_tests": "SELECT * FROM security_tests ORDER BY sequence",
    "findings": "SELECT * FROM findings ORDER BY priority",
    "fuzz_failures": "SELECT * FROM fuzz_failures ORDER BY test",
    "defender_observations": "SELECT * FROM defender_observations ORDER BY observed_at",
    "malware": "SELECT * FROM malware ORDER BY artifact",
    "sboms": "SELECT * FROM sboms ORDER BY filename",
    "reproducibility": "SELECT * FROM reproducibility ORDER BY artifact",
    "tools": "SELECT * FROM tools ORDER BY environment, tool",
}


def _load(name: str) -> dict[str, Any]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _source(source_id: str, label: str, path: str) -> dict[str, str]:
    return {"id": source_id, "label": label, "path": path}


def _query_source(
    source_id: str,
    label: str,
    sql: str,
    table_name: str,
    upstream: list[str],
    description: str,
) -> dict[str, Any]:
    return {
        "id": source_id,
        "label": label,
        "path": "scripts/build_security_report_artifact.py",
        "query": {
            "engine": "sqlite",
            "language": "sql",
            "description": description,
            "sql": sql,
            "tables_used": [table_name, *upstream],
        },
    }


def _select_rows(rows: list[dict[str, Any]], table_name: str, sql: str) -> list[dict[str, Any]]:
    """Load reviewed rows into SQLite and return the exact query result."""
    if not rows:
        return []
    columns = list(rows[0])
    if not table_name.isidentifier() or any(not column.isidentifier() for column in columns):
        raise ValueError("Report dataset identifiers must be safe SQLite identifiers")
    column_types = {
        column: "INTEGER"
        if all(isinstance(row[column], int) and not isinstance(row[column], bool) for row in rows)
        else "TEXT"
        for column in columns
    }
    definitions = ", ".join(f'"{column}" {column_types[column]}' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(f'CREATE TABLE "{table_name}" ({definitions})')
        connection.executemany(
            f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})',
            [[row[column] for column in columns] for row in rows],
        )
        return [dict(row) for row in connection.execute(sql)]


def _table(
    table_id: str,
    title: str,
    description: str,
    dataset: str,
    columns: list[tuple[str, str]],
    source_id: str,
    sort_field: str,
    sort_direction: str = "asc",
) -> dict[str, Any]:
    return {
        "id": table_id,
        "title": title,
        "description": description,
        "dataset": dataset,
        "sourceId": source_id,
        "density": "dense",
        "columns": [{"field": field, "label": label} for field, label in columns],
        "defaultSort": {"field": sort_field, "direction": sort_direction},
    }


def build_artifact(generated_at: str) -> tuple[dict[str, Any], dict[str, Any]]:
    tools = _load("tool-matrix.json")
    dependency = _load("dependency-cve-summary.json")
    sbom = _load("sbom-status.json")
    defender_status = _load("defender-status.json")
    defender = _load("defender-scan.json")
    clamav = _load("clamav-scan.json")
    binskim = _load("binskim-evidence.json")
    codeql = _load("codeql-evidence.json")
    fuzz = _load("fuzz-triage.json")
    privilege = _load("privilege-elevation-audit.json")
    tamper = _load("tamper-tests.json")
    signing = _load("authenticode-audit.json")
    reproducibility = _load("reproducibility-summary.json")
    attestations = _load("attestation-audit.json")
    dast = _load("dast-scope.json")
    identity = _load("artifact-identity-reconciliation.json")
    secret_scan = _load("secret-scan.json")
    regression = _load("regression-validation.json")

    tests = [
        {
            "sequence": 1,
            "test": "Artifact identity reconciliation",
            "tool": "SHA-256, GitHub Release, PE VersionInfo",
            "version": "native/GitHub",
            "scope": "Published portable ZIP and its ARX.exe",
            "result": identity["artifact_identity_gate"],
            "findings": "Published ZIP contains c904c0…; the earlier 1a1f03… executable is a different local build.",
            "provenance": "evidence/artifact-identity-reconciliation.json",
            "recommendation": "Continue anchoring binary tests to a fresh copy whose container hash matches the public release.",
            "blocker": "No",
        },
        {
            "sequence": 2,
            "test": "Defender protection state",
            "tool": "Microsoft Defender Get-MpComputerStatus",
            "version": "4.18.26070.9; signatures 1.457.316.0",
            "scope": "Native Windows host protection state",
            "result": defender_status["status"],
            "findings": "Three repeated measurements agree: Normal; service, AV, antispyware, real-time, behavior, I/O, network, and tamper protection enabled.",
            "provenance": "evidence/defender-status.json",
            "recommendation": "Do not alter Defender; retain timestamped raw fields when measuring release scans.",
            "blocker": "No",
        },
        {
            "sequence": 3,
            "test": "Dependency/CVE audit",
            "tool": "pip-audit / OSV-Scanner",
            "version": "2.10.1 / 2.4.0",
            "scope": "Exact wheel dependency closures for Python 3.10 and 3.11+",
            "result": dependency["result"],
            "findings": "0 known advisories; Python 3.10 resolves direct conditional tomli 2.4.1; 3.11+ has no runtime dependency.",
            "provenance": "evidence/dependency-cve-summary.json",
            "recommendation": "Repeat against exact release metadata; review rather than auto-upgrade any future finding.",
            "blocker": "No",
        },
        {
            "sequence": 4,
            "test": "SBOM generation and validation",
            "tool": "CycloneDX BOM / Syft / OSV-Scanner",
            "version": "7.3.1 / 1.45.1 / 2.4.0",
            "scope": "Python 3.10 and 3.14 dependency identities",
            "result": sbom["result"],
            "findings": "Two CycloneDX 1.6 and two SPDX 2.3 documents parse; privacy scan found no forbidden marker.",
            "provenance": "evidence/sbom-status.json",
            "recommendation": "Generate from final reviewed distributions and associate the validated SBOM with future provenance.",
            "blocker": "No",
        },
        {
            "sequence": 5,
            "test": "Primary malware scan",
            "tool": "Microsoft Defender MpCmdRun",
            "version": "4.18.26070.9; signatures 1.457.316.0",
            "scope": "Exact wheel, sdist, portable ZIP, published ARX.exe, installer",
            "result": defender["result"],
            "findings": "5/5 exact reviewed targets returned NO_THREATS_FOUND.",
            "provenance": "evidence/defender-scan.json",
            "recommendation": "Rescan final bytes after any future build or signing operation.",
            "blocker": "No",
        },
        {
            "sequence": 6,
            "test": "Independent second-engine malware scan",
            "tool": "ClamAV clamscan",
            "version": "1.5.3; 3,628,027 signatures",
            "scope": "Exact copied Beta 1 artifacts in isolated WSL",
            "result": clamav["result"],
            "findings": "5/5 exact reviewed targets returned OK; no upload and no resident daemon.",
            "provenance": "evidence/clamav-scan.json",
            "recommendation": "Keep second-engine scans isolated and require explicit approval before any third-party upload.",
            "blocker": "No",
        },
        {
            "sequence": 7,
            "test": "Python SAST",
            "tool": "Bandit",
            "version": "1.9.4",
            "scope": "src, scripts, packaging",
            "result": "REVIEWED_FINDINGS",
            "findings": "Reviewed: 0 critical, 0 high, 1 medium, 9 low, 13 informational. Medium: package-index download URL lacks an independent exact-host/redirect/size boundary.",
            "provenance": "evidence/bandit-classification.json",
            "recommendation": "Harden the future index verifier without changing immutable Beta 1; preserve all scanner evidence.",
            "blocker": "Review required; no HIGH/CRITICAL blocker",
        },
        {
            "sequence": 8,
            "test": "Rule-based SAST",
            "tool": "Semgrep",
            "version": "1.174.0",
            "scope": "Python source/tests and GitHub Actions",
            "result": "PARTIAL_COVERAGE",
            "findings": "Python: 1 low environment trust-boundary finding. Actions: 0 findings, but approximately 79.1% parsed with 6 pwsh-as-Bash warnings.",
            "provenance": "evidence/semgrep-classification.json",
            "recommendation": "Validate the vswhere path from a trusted Windows source; retain CodeQL and workflow tests for Actions coverage.",
            "blocker": "No HIGH/CRITICAL blocker; coverage caveat",
        },
        {
            "sequence": 9,
            "test": "CodeQL evidence",
            "tool": "GitHub CodeQL",
            "version": "CLI 2.26.3; action v4.37.0 pinned",
            "scope": "Exact release commit; Python and GitHub Actions",
            "result": codeql["result"],
            "findings": "0 results across 43 Python and 17 Actions rules; 0 open or closed repository alerts at observation time.",
            "provenance": "evidence/codeql-evidence.json",
            "recommendation": "Keep the pinned workflow and treat zero alerts as a defined query result, not proof of absence.",
            "blocker": "No",
        },
        {
            "sequence": 10,
            "test": "Bounded Hypothesis fuzz campaign",
            "tool": "Hypothesis / pytest",
            "version": "6.165.10 / 9.1.1",
            "scope": "ARX-owned parsers, response parsing, redaction, and serialization",
            "result": fuzz["gate"]["result"],
            "findings": "10 tests: 5 passed, 5 failed in 67.012 s. Failures classify as 2 test-assumption errors and 3 harness defects; 0 confirmed product defects.",
            "provenance": "evidence/fuzz-triage.json",
            "recommendation": "Correct and independently review the harness, then rerun all three properties that never reached product code.",
            "blocker": "Yes — 3 incomplete properties",
        },
        {
            "sequence": 11,
            "test": "Privilege/elevation boundary review",
            "tool": "mt.exe, ACL inspection, source review, pytest",
            "version": "Windows SDK 10.0.26100.8249 / native",
            "scope": "Manifest, paths, installer policy, access-denial behavior",
            "result": privilege["gate"]["result"],
            "findings": "asInvoker; protected Program Files/per-user credential ACLs; permission-failure regression passed. Direct standard-user lifecycle was unavailable on the elevated host.",
            "provenance": "evidence/privilege-elevation-audit.json",
            "recommendation": "Run standard-user install/upgrade/uninstall/UAC cases in a disposable Windows VM.",
            "blocker": "Yes — future Windows production gate",
        },
        {
            "sequence": 12,
            "test": "Copied-artifact tamper detection",
            "tool": "ARX release verifier / SHA-256",
            "version": "Beta 1 release commit",
            "scope": "Copies only: mutation, truncation, corruption, manifest, extra/missing public artifacts",
            "result": tamper["gate"]["result"],
            "findings": "6/6 required copied-artifact cases rejected. Auxiliary non-public .txt files are outside verifier scope.",
            "provenance": "evidence/tamper-tests.json",
            "recommendation": "Retain exact upload allowlists; add independent authenticity through signing/provenance in a future release.",
            "blocker": "No for defined cases",
        },
        {
            "sequence": 13,
            "test": "Authenticode inspection",
            "tool": "Get-AuthenticodeSignature / signtool",
            "version": "native / 10.0.26100.8249",
            "scope": "Published ARX.exe and installer",
            "result": signing["gate"]["beta1_status"],
            "findings": "Both binaries are NotSigned; no trusted production code-signing certificate was found.",
            "provenance": "evidence/authenticode-audit.json",
            "recommendation": "Use a protected, human-gated signing system for a future release and verify final signed bytes before checksums/provenance.",
            "blocker": "Yes — future signed Windows release",
        },
        {
            "sequence": 14,
            "test": "Two-build reproducibility experiment",
            "tool": "ARX build scripts / PyInstaller / Inno Setup / structural analyzer",
            "version": "PyInstaller 6.22.2 / Inno Setup 7.1.0",
            "scope": "Two detached clean builds at the exact release commit",
            "result": reproducibility["gate"]["result"],
            "findings": "0 bit-for-bit; 5 structurally equivalent; installer conservatively NOT REPRODUCIBLE.",
            "provenance": "evidence/reproducibility-summary.json",
            "recommendation": "Normalize timestamps/order, fix hash seed/build inputs, and add an Inno 7-compatible payload comparison.",
            "blocker": "Yes — 2 future reproducibility items",
        },
        {
            "sequence": 15,
            "test": "TestPyPI publish attestation",
            "tool": "pypi-attestations / PyPI Integrity API",
            "version": "0.0.30 / publish-v1",
            "scope": "Exact TestPyPI wheel and sdist",
            "result": attestations["gate"]["testpypi_publish_attestation"],
            "findings": "Both subjects and SHA-256 digests cryptographically verify to the expected GitHub repository, workflow, and testpypi environment.",
            "provenance": "evidence/attestation-audit.json",
            "recommendation": "Preserve the existing Trusted Publisher identity and exact subject checks.",
            "blocker": "No",
        },
        {
            "sequence": 16,
            "test": "GitHub release artifact attestation",
            "tool": "GitHub CLI attestation verification",
            "version": "gh 2.98.0",
            "scope": "All five exact GitHub release artifacts",
            "result": attestations["gate"]["github_release_artifact_attestation"],
            "findings": "No GitHub artifact attestation was found for any reviewed Beta 1 SHA-256.",
            "provenance": "evidence/attestation-audit.json",
            "recommendation": "Attest all future release artifacts and the checksum manifest with OIDC; do not retrofit Beta 1.",
            "blocker": "Yes — future provenance claim",
        },
        {
            "sequence": 17,
            "test": "Dynamic network boundary",
            "tool": "pytest / localhost HTTP server",
            "version": "pytest 9.1.1 / stdlib",
            "scope": "Mocked provider transports and localhost only",
            "result": dast["gate"]["result"],
            "findings": "48 mocked and 2 localhost tests passed; redirect and oversized response rejection reached the real urllib transport. ARX exposes no inbound service, so conventional DAST is not applicable.",
            "provenance": "evidence/dast-scope.json",
            "recommendation": "Keep external targets out of DAST; exercise outbound behavior with mocks/localhost.",
            "blocker": "No",
        },
        {
            "sequence": 18,
            "test": "Tracked and audit-output secret scan",
            "tool": "ARX tracked scanner / Gitleaks",
            "version": "release script / 8.30.1",
            "scope": "Tracked/staged files and exact public release artifacts",
            "result": secret_scan["gate"]["result"],
            "findings": "0 credential-shaped or host-identity findings in staged durable evidence; exact release verifier privacy scan passed.",
            "provenance": "evidence/secret-scan.json",
            "recommendation": "Keep raw local logs with host/synthetic-secret metadata out of Git while retaining hashes and sanitized classifications.",
            "blocker": "No",
        },
        {
            "sequence": 19,
            "test": "Published-executable BinSkim analysis",
            "tool": "BinSkim PE/MSIL Analysis Driver",
            "version": "4.4.9.11",
            "scope": "ARX.exe from the checksum-verified published portable ZIP",
            "result": binskim["gate"]["result"],
            "findings": "The target was not evaluated because no loadable PDB was available; ignorePdbLoadError changed the process exit but still produced executionSuccessful=false and zero rule results.",
            "provenance": "evidence/binskim-evidence.json",
            "recommendation": "Preserve a compatible reviewed PDB or establish documented symbol-independent BinSkim coverage for a future build; never call zero results from an unsuccessful invocation clean.",
            "blocker": "No — low binary-SAST coverage gap",
        },
        {
            "sequence": 20,
            "test": "Complete local regression suite",
            "tool": "pytest",
            "version": "host project environment",
            "scope": "Repository tests plus audit localhost tests",
            "result": regression["runs"][0]["result"],
            "findings": "221 passed, 0 failed in 13.67 seconds.",
            "provenance": "evidence/regression-validation.json",
            "recommendation": "Retain the same no-external-target test boundary for future audit branches.",
            "blocker": "No",
        },
        {
            "sequence": 21,
            "test": "Isolated Windows GUI regression",
            "tool": "scripts/run-isolated-gui-tests.py / pytest",
            "version": "release commit runner",
            "scope": "41 GUI tests, one isolated Windows process per test",
            "result": regression["runs"][1]["result"],
            "findings": "41 passed, 0 failed.",
            "provenance": "evidence/regression-validation.json",
            "recommendation": "Keep GUI tests process-isolated to prevent Tk state contamination.",
            "blocker": "No",
        },
        {
            "sequence": 22,
            "test": "Production publication boundary",
            "tool": "GitHub workflow/API inspection",
            "version": "publish-pypi.yml at release commit",
            "scope": "arx-prescanner 4.0.0b1 production PyPI state",
            "result": "BLOCKED_BY_HUMAN_GATE",
            "findings": "Production PyPI has no 4.0.0b1 version; publication workflow remains disabled_manually.",
            "provenance": "evidence/attestation-audit.json",
            "recommendation": "Do not enable or dispatch production publication until every human and security gate is explicitly reviewed.",
            "blocker": "Yes — policy",
        },
    ]

    findings = [
        {"priority": 1, "id": "SIGN-001", "severity": "MEDIUM", "classification": "RELEASE_READINESS_BLOCKER", "finding": "Published Windows executable and installer are unsigned; no production signing identity exists.", "security_relevance": "Users cannot authenticate Windows publisher identity through Authenticode.", "release_blocking": "Yes — future signed Windows release", "evidence": "evidence/authenticode-audit.json", "remediation": "Acquire/approve a trusted hardware-backed signing identity and use a protected human gate."},
        {"priority": 2, "id": "REPRO-001", "severity": "MEDIUM", "classification": "SUPPLY_CHAIN_REPRODUCIBILITY_GAP", "finding": "No tested artifact is bit-for-bit reproducible; the installer is not independently structurally verified.", "security_relevance": "Independent rebuilds cannot reproduce the published bytes exactly.", "release_blocking": "Yes — future reproducibility claim", "evidence": "evidence/reproducibility-summary.json", "remediation": "Normalize time/order/hash inputs and establish an Inno 7 payload comparison."},
        {"priority": 3, "id": "ATTEST-001", "severity": "MEDIUM", "classification": "SUPPLY_CHAIN_PROVENANCE_GAP", "finding": "The five GitHub release artifacts have no GitHub artifact attestations.", "security_relevance": "The GitHub assets lack an OIDC-bound build provenance record.", "release_blocking": "Yes — future provenance claim", "evidence": "evidence/attestation-audit.json", "remediation": "Attest future exact outputs with a pinned action and minimal OIDC permissions."},
        {"priority": 4, "id": "BANDIT-B310", "severity": "MEDIUM", "classification": "VALID_HARDENING_FINDING", "finding": "The package-index verifier downloads an index-supplied file URL without a separate exact-host, redirect, or size boundary.", "security_relevance": "A compromised/malformed index response could redirect the verifier before the existing digest check.", "release_blocking": "Review required; not HIGH/CRITICAL", "evidence": "evidence/bandit-classification.json", "remediation": "Validate HTTPS host/port, reject redirects, and bound bytes while retaining exact SHA-256."},
        {"priority": 5, "id": "FUZZ-HARNESS", "severity": "LOW", "classification": "HARNESS_DEFECT", "finding": "Three Hypothesis properties stopped at a function-scoped tmp_path health check before product code ran.", "security_relevance": "PE, directory metadata, and archive robustness properties remain unexecuted.", "release_blocking": "Yes — 3 fuzz properties", "evidence": "evidence/fuzz-triage.json", "remediation": "Correct the audit harness, independently review it, and rerun the bounded campaign."},
        {"priority": 6, "id": "PRIV-001", "severity": "LOW", "classification": "TEST_COVERAGE_GAP", "finding": "Direct standard-user and full installer lifecycle behavior was unavailable on the elevated non-disposable host.", "security_relevance": "The observed static boundaries do not replace real standard-user/UAC lifecycle evidence.", "release_blocking": "Yes — future Windows production gate", "evidence": "evidence/privilege-elevation-audit.json", "remediation": "Exercise separate standard-user/admin accounts in a disposable Windows VM."},
        {"priority": 7, "id": "SEMGREP-ENV", "severity": "LOW", "classification": "ENVIRONMENT_TRUST_BOUNDARY", "finding": "ProgramFiles(x86) can influence the absolute vswhere executable path used for a fixed discovery probe.", "security_relevance": "A hostile same-privilege environment can redirect local tool execution.", "release_blocking": "No HIGH/CRITICAL blocker", "evidence": "evidence/semgrep-classification.json", "remediation": "Derive the installation root from a trusted native source or validate path ownership/location."},
        {"priority": 8, "id": "BINSKIM-001", "severity": "LOW", "classification": "TOOL_COVERAGE_GAP", "finding": "BinSkim could not evaluate the published PyInstaller executable because no loadable PDB was available.", "security_relevance": "PE/MSIL rule coverage was not obtained; zero rule results came from an unsuccessful invocation and are not clean evidence.", "release_blocking": "No — optional binary-SAST coverage gap", "evidence": "evidence/binskim-evidence.json", "remediation": "Preserve a compatible reviewed PDB or establish documented symbol-independent BinSkim coverage for a future build."},
    ]

    fuzz_rows = [
        {
            "test": item["test_name"],
            "property": item["intended_property"],
            "counterexample": item["minimal_counterexample_category"],
            "observed": item["observed_behavior"],
            "expected": item["expected_behavior"],
            "classification": item["classification"],
            "security_relevance": item["security_relevance"],
            "severity": item["severity"],
            "release_blocking": "Yes" if item["release_blocking"] else "No",
            "evidence": "; ".join(item["evidence_location"]),
        }
        for item in fuzz["failures"]
    ]

    reproducibility_rows = [
        {
            "artifact": item["artifact"],
            "classification": item["classification"],
            "published_sha256": item["published"]["sha256"],
            "build_a_sha256": item["build_a"]["sha256"],
            "build_b_sha256": item["build_b"]["sha256"],
            "basis": item["basis"],
        }
        for item in reproducibility["artifacts"]
    ]

    sbom_rows = [
        {
            "filename": item["filename"],
            "format": item["format"],
            "sha256": item["sha256"],
            "root": item["root"],
            "dependencies": ", ".join(item["dependencies"]) or "None",
            "validation": "; ".join(item["validation"]),
        }
        for item in sbom["artifacts"]
    ]

    clamav_by_name = {item["filename"]: item for item in clamav["targets"]}
    malware_rows = [
        {
            "artifact": item["filename"],
            "sha256": item["sha256"],
            "defender": item["result"],
            "clamav": clamav_by_name[item["filename"]]["result"],
        }
        for item in defender["targets"]
    ]

    defender_rows = [
        {
            "observed_at": item["observed_at"],
            "mode": item["AMRunningMode"],
            "service": str(item["AMServiceEnabled"]),
            "antivirus": str(item["AntivirusEnabled"]),
            "antispyware": str(item["AntispywareEnabled"]),
            "real_time": str(item["RealTimeProtectionEnabled"]),
            "behavior": str(item["BehaviorMonitorEnabled"]),
            "ioav": str(item["IoavProtectionEnabled"]),
            "nis": str(item["NISEnabled"]),
            "tamper": str(item["IsTamperProtected"]),
            "product": item["AMProductVersion"],
            "signatures": item["AntivirusSignatureVersion"],
            "signature_updated": item["AntivirusSignatureLastUpdated"],
        }
        for item in defender_status["observations"]
    ]

    tool_rows = [
        {
            "environment": item["environment"],
            "tool": item["tool"],
            "version": item["version"] or "Not installed",
            "source": item["source"],
            "purpose": item["purpose"],
            "status": item["status"],
        }
        for item in tools["tools"]
    ]

    tests = _select_rows(tests, "security_tests", TABLE_SQL["security_tests"])
    findings = _select_rows(findings, "findings", TABLE_SQL["findings"])
    fuzz_rows = _select_rows(fuzz_rows, "fuzz_failures", TABLE_SQL["fuzz_failures"])
    defender_rows = _select_rows(defender_rows, "defender_observations", TABLE_SQL["defender_observations"])
    malware_rows = _select_rows(malware_rows, "malware", TABLE_SQL["malware"])
    sbom_rows = _select_rows(sbom_rows, "sboms", TABLE_SQL["sboms"])
    reproducibility_rows = _select_rows(reproducibility_rows, "reproducibility", TABLE_SQL["reproducibility"])
    tool_rows = _select_rows(tool_rows, "tools", TABLE_SQL["tools"])

    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            "CREATE TABLE reviewed_findings (id TEXT, severity TEXT, release_blocking TEXT)"
        )
        connection.executemany(
            "INSERT INTO reviewed_findings (id, severity, release_blocking) VALUES (?, ?, ?)",
            [(row["id"], row["severity"], row["release_blocking"]) for row in findings],
        )
        severity_rows = [dict(row) for row in connection.execute(SEVERITY_SQL)]

    sources = [
        _source("audit_summary", "Consolidated security gate summary", "evidence/security-gate-summary.json"),
        _query_source("security_tests_source", "Defined security gate query", TABLE_SQL["security_tests"], "security_tests", ["evidence/security-gate-summary.json"], "Returns every gate with tool, version, scope, result, findings, provenance, recommendation, and blocker status."),
        _query_source("findings_source", "Reviewed finding register query", TABLE_SQL["findings"], "findings", ["evidence/security-gate-summary.json"], "Returns the reviewed non-informational findings in remediation priority order."),
        _query_source("fuzz_table_source", "Fuzz failure triage query", TABLE_SQL["fuzz_failures"], "fuzz_failures", ["evidence/fuzz-triage.json"], "Returns every failed property classification from the preserved fuzz triage."),
        _query_source("defender_table_source", "Defender measurement query", TABLE_SQL["defender_observations"], "defender_observations", ["evidence/defender-status.json"], "Returns all three repeated native Defender observations in time order."),
        _query_source("malware_table_source", "Exact artifact malware result query", TABLE_SQL["malware"], "malware", ["evidence/defender-scan.json", "evidence/clamav-scan.json", "evidence/artifact-identity-reconciliation.json"], "Joins the reviewed Defender and ClamAV result rows by exact filename and SHA-256."),
        _query_source("sbom_table_source", "Validated SBOM query", TABLE_SQL["sboms"], "sboms", ["evidence/sbom-status.json"], "Returns every generated SBOM with exact identity, hash, dependency closure, and validation evidence."),
        _query_source("repro_table_source", "Reproducibility classification query", TABLE_SQL["reproducibility"], "reproducibility", ["evidence/reproducibility-summary.json"], "Returns the published/build hashes and conservative classification for every artifact."),
        _query_source("tools_table_source", "Security toolchain inventory query", TABLE_SQL["tools"], "tools", ["evidence/tool-matrix.json"], "Returns the host and audit-isolated tool inventory ordered by environment and tool."),
        {
            "id": "severity_counts_source",
            "label": "Reviewed finding severity aggregation",
            "path": "scripts/build_security_report_artifact.py",
            "query": {
                "engine": "sqlite",
                "language": "sql",
                "description": "Counts the reviewed non-informational finding register by severity and release-blocking disposition after loading the exact reviewed rows into an in-memory SQLite table.",
                "sql": SEVERITY_SQL,
                "tables_used": ["reviewed_findings"],
                "filters": ["severity in CRITICAL, HIGH, MEDIUM, LOW", "informational observations excluded"],
                "metric_definitions": {
                    "count": "Number of reviewed non-informational findings at the stated severity.",
                    "release_blocking_count": "Rows whose release_blocking field begins with Yes.",
                    "review_only_count": "Count minus release_blocking_count."
                }
            }
        },
        _source("fuzz_triage", "Bounded fuzz failure triage", "evidence/fuzz-triage.json"),
        _source("repro_summary", "Two-build reproducibility summary", "evidence/reproducibility-summary.json"),
        _source("sbom_status", "SBOM generation and validation evidence", "evidence/sbom-status.json"),
        _source("defender_status", "Repeated native Defender state observations", "evidence/defender-status.json"),
        _source("tool_matrix", "Host and isolated security tool inventory", "evidence/tool-matrix.json"),
    ]

    tables = [
        _table("gate_table", "Defined security gates", "Exact results, scope, evidence, and blocker status for each reviewed gate.", "security_tests", [("sequence", "#"), ("test", "Test"), ("tool", "Tool"), ("version", "Version"), ("scope", "Scope"), ("result", "Result"), ("findings", "Findings"), ("provenance", "Provenance"), ("recommendation", "Recommendation"), ("blocker", "Blocker")], "security_tests_source", "sequence"),
        _table("findings_table", "Findings requiring review or remediation", "Reviewed medium and low findings; scanner output is not silently suppressed.", "findings", [("priority", "Priority"), ("id", "ID"), ("severity", "Severity"), ("classification", "Classification"), ("finding", "Finding"), ("security_relevance", "Security relevance"), ("release_blocking", "Release blocking"), ("evidence", "Evidence"), ("remediation", "Recommendation")], "findings_source", "priority"),
        _table("fuzz_table", "Every failed fuzz property", "Individual property classifications from the preserved JUnit/pytest evidence.", "fuzz_failures", [("test", "Test name"), ("property", "Intended property"), ("counterexample", "Minimal counterexample category"), ("observed", "Observed behavior"), ("expected", "Expected behavior"), ("classification", "Classification"), ("security_relevance", "Security relevance"), ("severity", "Severity"), ("release_blocking", "Release blocking"), ("evidence", "Evidence location")], "fuzz_table_source", "test"),
        _table("defender_table", "Three consistent native Defender measurements", "Raw requested fields and timestamps; no Defender setting was changed.", "defender_observations", [("observed_at", "Observed at"), ("mode", "AMRunningMode"), ("service", "AMService"), ("antivirus", "Antivirus"), ("antispyware", "Antispyware"), ("real_time", "Real-time"), ("behavior", "Behavior"), ("ioav", "IOAV"), ("nis", "NIS"), ("tamper", "Tamper"), ("product", "Product version"), ("signatures", "Signature version"), ("signature_updated", "Signatures updated")], "defender_table_source", "observed_at"),
        _table("malware_table", "Exact artifact malware scan results", "The GitHub Release hashes anchor both Defender and isolated ClamAV observations.", "malware", [("artifact", "Artifact"), ("sha256", "SHA-256"), ("defender", "Defender"), ("clamav", "ClamAV")], "malware_table_source", "artifact"),
        _table("sbom_table", "Validated SBOM artifacts", "Exact release package identities for Python 3.10 and 3.14.", "sboms", [("filename", "Filename"), ("format", "Format"), ("sha256", "SHA-256"), ("root", "Root package"), ("dependencies", "Dependencies"), ("validation", "Validation")], "sbom_table_source", "filename"),
        _table("repro_table", "Reproducibility classification by artifact", "Bit equality is distinguished from structural equivalence.", "reproducibility", [("artifact", "Artifact"), ("classification", "Classification"), ("published_sha256", "Published SHA-256"), ("build_a_sha256", "Build A SHA-256"), ("build_b_sha256", "Build B SHA-256"), ("basis", "Basis")], "repro_table_source", "artifact"),
        _table("tools_table", "Host and audit-isolated security toolchain", "Exact observed versions, source, purpose, and installation state.", "tools", [("environment", "Environment"), ("tool", "Tool"), ("version", "Version"), ("source", "Source"), ("purpose", "Purpose"), ("status", "Status")], "tools_table_source", "environment"),
    ]

    charts = [
        {
            "id": "severity_chart",
            "title": "Reviewed remediation items by severity",
            "description": "Eight non-informational items; counts are audit classifications, not a composite security score.",
            "type": "bar",
            "dataset": "severity_counts",
            "sourceId": "severity_counts_source",
            "encodings": {
                "x": {"field": "severity", "type": "nominal"},
                "y": {"field": "count", "type": "quantitative"},
            },
        }
    ]

    blocks = [
        {"id": "title", "type": "markdown", "layout": "full", "body": "# ARX 4.0.0 Beta 1 Security Audit"},
        {"id": "technical_summary", "type": "markdown", "layout": "full", "body": "## Technical summary\n\n- **Beta 1 passed the defined dependency, SBOM, two-engine malware, CodeQL, copied-artifact tamper, secret-scan, and outbound-provider boundary checks.** These are bounded claims tied to the exact published hashes and release commit.\n- **This is not a production-readiness pass.** The fuzz gate is `FAIL_INCOMPLETE`; direct standard-user lifecycle evidence is partial; the Windows binaries are unsigned; no artifact is bit-for-bit reproducible; the installer is conservatively `NOT REPRODUCIBLE`; and GitHub artifact attestations are absent.\n- **No confirmed CRITICAL or HIGH finding was established.** Medium findings remain in release-verifier transport hardening, Windows signing, reproducibility, and GitHub provenance.\n- **The immutable Beta 1 release was not modified.** Production PyPI remains blocked, and this report does not claim that ARX is secure."},
        {"id": "key_findings", "type": "markdown", "layout": "full", "body": "## Defined controls passed, but production readiness remains blocked\n\nThe strongest positive evidence is artifact-specific: exact GitHub release hashes anchored malware, tamper, signature, identity, and attestation checks. The strongest negative evidence is also specific: three fuzz properties never reached ARX code, signed publisher identity is absent, rebuild bytes diverge, and GitHub provenance was never created for Beta 1. These limitations must remain visible rather than being averaged into a single score."},
        {"id": "gate_table_block", "type": "table", "layout": "full", "tableId": "gate_table"},
        {"id": "remediation_findings", "type": "markdown", "layout": "full", "body": "## Four medium findings and four lower-severity gaps need explicit review\n\nThe medium items are not interchangeable: one hardens a verification download boundary, one blocks signed Windows distribution, one blocks reproducibility claims, and one blocks GitHub provenance claims. The low items preserve incomplete, same-privilege trust-boundary, and BinSkim coverage evidence. None was automatically patched or suppressed during this read-only audit."},
        {"id": "severity_chart_block", "type": "chart", "layout": "full", "chartId": "severity_chart"},
        {"id": "findings_table_block", "type": "table", "layout": "full", "tableId": "findings_table"},
        {"id": "fuzz_findings", "type": "markdown", "layout": "full", "body": "## The fuzz gate failed because three properties never exercised product code\n\nThe campaign completed with exit code 1: five tests passed and five failed over 67.012 seconds. Two failures are demonstrably incorrect test assumptions. Three are harness defects caused by a function-scoped temporary-path fixture, so the PE, directory metadata, and archive properties remain untested. This is `FAIL_INCOMPLETE`, not PASS, even though the failures confirm no ARX product defect."},
        {"id": "fuzz_table_block", "type": "table", "layout": "full", "tableId": "fuzz_table"},
        {"id": "defender_findings", "type": "markdown", "layout": "full", "body": "## Defender was normal and enabled in three repeated native measurements\n\nAll requested protection fields agreed across the three observations. An earlier brief transition is preserved in the underlying evidence rather than hidden; no setting was changed during the audit."},
        {"id": "defender_table_block", "type": "table", "layout": "full", "tableId": "defender_table"},
        {"id": "malware_findings", "type": "markdown", "layout": "full", "body": "## Both on-demand engines found no threat in the five exact reviewed targets\n\nMicrosoft Defender and isolated WSL ClamAV scanned byte-identical artifact copies. The portable executable was first reconciled to the published ZIP; the differing local executable was not treated as equivalent. No artifact was uploaded to a third party."},
        {"id": "malware_table_block", "type": "table", "layout": "full", "tableId": "malware_table"},
        {"id": "sbom_findings", "type": "markdown", "layout": "full", "body": "## Dependency and SBOM checks found no known advisory in the exact runtime closure\n\nThe immutable wheel declares only conditional `tomli>=2` below Python 3.11. Python 3.10 resolved `tomli 2.4.1`; newer Python has no runtime dependency. Pip-audit and OSV reported no advisory, and all four SBOM documents parsed successfully. This is a database-at-observation-time result, not a guarantee against unknown vulnerabilities."},
        {"id": "sbom_table_block", "type": "table", "layout": "full", "tableId": "sbom_table"},
        {"id": "repro_findings", "type": "markdown", "layout": "full", "body": "## Five outputs are structurally equivalent; the installer is not reproducible\n\nTwo independent detached builds used identical pinned tool environments at the exact release commit. Wheel, sdist, portable ZIP, ARX.exe, and the checksum manifest preserve reviewed structure or normalized semantics but not bytes. Inno Setup 7.1 payload equivalence could not be independently extracted, so the installer remains conservatively `NOT REPRODUCIBLE`."},
        {"id": "repro_table_block", "type": "table", "layout": "full", "tableId": "repro_table"},
        {"id": "scope_definitions", "type": "markdown", "layout": "full", "body": "## Scope and trust anchors\n\n**Release population.** The audit covers ARX 4.0.0 Beta 1, tag `v4.0.0-b1`, release commit `f3bce58552578df2795f292b1d4f572ee6af8e0b`, and the five public release assets identified by their published SHA-256 values.\n\n**Result vocabulary.** `PASS_DEFINED_GATE` means only that the stated tool, scope, inputs, and rule completed as recorded. `PARTIAL`, `FAIL_INCOMPLETE`, `FAIL_ABSENT`, and `NOT REPRODUCIBLE` preserve missing evidence. A scanner severity is evidence to classify, not an automatic product conclusion.\n\n**Exclusions.** No external target scanning, exploit development, third-party artifact upload, production signing, API-key access, paid OpenAI generation, production PyPI publication, or Phase C work occurred."},
        {"id": "methodology", "type": "markdown", "layout": "full", "body": "## Methodology was read-only, bounded, and release-anchored\n\nArtifact tests began with fresh GitHub release copies and exact SHA-256 reconciliation. Source analysis used saved scanner output plus manual classification. Fuzzing targeted only ARX-owned input boundaries under bounded generation. Privilege work used manifest, ACL, source, and mocked failure evidence; destructive lifecycle testing was withheld from the non-disposable host. Network dynamics used injected mocks and ephemeral localhost servers only.\n\nOne bounded bar chart shows the reviewed finding count by severity and is explicitly not a composite risk score. Identities, categorical gate states, hashes, and exception text remain in exact tables because additional visual aggregation would obscure their distinctions."},
        {"id": "toolchain", "type": "markdown", "layout": "full", "body": "## The host and audit-isolated toolchains were inventoried separately\n\nExisting host tools were reused, including the intentional `arx-sec` Conda environment and the exact BinSkim path supplied for the audit. ClamAV, innoextract, and the PyPI attestation verifier were isolated from the ARX runtime; innoextract 1.9 was recorded as incompatible with Inno Setup 7.1 rather than treated as successful."},
        {"id": "tools_table_block", "type": "table", "layout": "full", "tableId": "tools_table"},
        {"id": "limitations", "type": "markdown", "layout": "full", "body": "## Limitations and robustness checks\n\n- Vulnerability databases and malware signatures are time-bound observations.\n- CodeQL covered Python and Actions queries, not runtime behavior or binaries. Semgrep Actions parsing was partial.\n- BinSkim did not evaluate ARX.exe without a loadable PDB; its zero rule results are no clean-scan evidence.\n- The fuzz campaign is incomplete until the three harness-blocked properties run.\n- Privilege conclusions lack a disposable standard-user Windows lifecycle.\n- Unsigned checksums detect independent mutation but do not authenticate a coordinated replacement.\n- Structural equivalence is not bit-for-bit reproducibility, and installer payload equivalence remains unproven.\n- TestPyPI publish attestations verify the wheel and sdist publisher path; they do not create provenance for GitHub Windows assets."},
        {"id": "next_steps", "type": "markdown", "layout": "full", "body": "## Recommended next steps before any production-publication review\n\n1. Correct and independently review the fuzz harness, then rerun the three unexecuted properties.\n2. Run standard-user install, launch, upgrade, denied-path, and uninstall cases in a disposable Windows VM.\n3. Harden package-index download URL/redirect/size controls and the environment-derived vswhere trust boundary in a future branch.\n4. Establish a trusted production signing identity and keep signing behind a protected human gate.\n5. Normalize build timestamps, ordering, hash seed, and PyInstaller/Inno inputs; add an Inno 7-compatible payload comparison.\n6. Add OIDC-backed GitHub artifact attestations for future exact outputs and associate the validated SBOM.\n7. Keep production PyPI blocked until the user separately authorizes it after reviewing these preserved findings."},
        {"id": "further_questions", "type": "markdown", "layout": "full", "body": "## Further questions for the next gate\n\n- Do the corrected fuzz properties expose any product counterexample once they actually reach ARX code?\n- Does a disposable standard-user Windows lifecycle confirm the static privilege model and optional post-install token behavior?\n- Can the installer payload be independently compared with an Inno Setup 7-compatible method?\n- Which approved production code-signing and artifact-attestation service will own future release identities?\n- Which reproducibility claim—bit-for-bit or explicitly bounded structural equivalence—is required before production PyPI review?"},
    ]

    datasets = {
        "security_tests": tests,
        "findings": findings,
        "fuzz_failures": fuzz_rows,
        "defender_observations": defender_rows,
        "malware": malware_rows,
        "sboms": sbom_rows,
        "reproducibility": reproducibility_rows,
        "tools": tool_rows,
        "severity_counts": severity_rows,
    }

    summary = {
        "schema_version": 1,
        "release": {"name": "ARX 4.0.0 Beta 1", "tag": "v4.0.0-b1", "commit": "f3bce58552578df2795f292b1d4f572ee6af8e0b"},
        "generated_at": generated_at,
        "published_release_modified": False,
        "production_pypi": "BLOCKED",
        "confirmed_critical_findings": 0,
        "confirmed_high_findings": 0,
        "tests": tests,
        "findings_requiring_review": findings,
        "source_evidence": [source["path"] for source in sources],
    }

    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "ARX 4.0.0 Beta 1 Security Audit",
            "description": "Read-only release security audit and preserved gate evidence.",
            "generatedAt": generated_at,
            "blocks": blocks,
            "cards": [],
            "charts": charts,
            "tables": tables,
            "sources": sources,
        },
        "snapshot": {
            "version": 1,
            "generatedAt": generated_at,
            "status": "ready",
            "datasets": datasets,
        },
        "sources": sources,
    }
    return artifact, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=AUDIT_ROOT / "artifact.json")
    parser.add_argument("--summary-output", type=Path, default=EVIDENCE / "security-gate-summary.json")
    parser.add_argument("--generated-at", default=datetime.now().astimezone().isoformat(timespec="seconds"))
    args = parser.parse_args()

    artifact, summary = build_artifact(args.generated_at)
    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.summary_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

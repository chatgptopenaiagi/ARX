import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
BENCHMARKS = ROOT / "benchmarks"
BENCHMARK = BENCHMARKS / "ARX-BENCH-PY-001"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_claims_registry_contains_only_non_publishable_unverified_hypotheses():
    registry = load(BENCHMARKS / "claims-registry.yaml")

    assert registry["classification_vocabulary"] == [
        "MEASURED",
        "DERIVED",
        "ESTIMATED",
        "INFERRED",
        "UNKNOWN",
    ]
    assert registry["policy"]["automatic_claim_promotion"] is False
    assert set(registry["policy"]["prohibited_reports_at_this_phase"]) == {
        "ENERGY",
        "TOKEN_SAVINGS",
        "TIME_SAVINGS",
        "ECONOMIC",
    }
    assert registry["claims"]
    assert all(item["status"] in {"HYPOTHESIS", "UNVERIFIED"} for item in registry["claims"])
    assert all(item["evidence_classification"] == "UNKNOWN" for item in registry["claims"])
    assert all(item["evidence_refs"] == [] for item in registry["claims"])
    assert all(item["publishable"] is False for item in registry["claims"])


def test_canonical_python_yellow_fixture_is_exact_and_contains_no_benchmark_result():
    scenario = load(BENCHMARK / "fixture" / "scenario.yaml")
    expected = load(BENCHMARK / "fixture" / "expected-result.yaml")

    assert scenario["project"]["requires_python"] == ">=3.12,<3.13"
    assert scenario["execution_context"]["resolved_provider_id"] == "python-current-3.14.6-x64"
    providers = {item["provider_id"]: item for item in scenario["providers"]}
    assert providers["python-current-3.14.6-x64"]["version"] == "3.14.6"
    assert providers["python-existing-3.12.13-x64"]["version"] == "3.12.13"
    assert providers["python-existing-3.12.13-x64"]["health"] == "HEALTHY"
    assert expected["values"]["verdict"] == {
        "value": "YELLOW",
        "classification": "DERIVED",
    }
    assert expected["values"]["blocker_ids"]["value"] == []
    assert expected["performance_evidence"] == {
        "value": "NONE",
        "classification": "UNKNOWN",
    }


def test_arms_are_matched_except_for_registered_arx_treatment():
    baseline = load(BENCHMARK / "baseline" / "arm.yaml")
    assisted = load(BENCHMARK / "arx-assisted" / "arm.yaml")
    matched = {
        "scenario",
        "task",
        "start_rule",
        "stop_rule",
        "allowed_inputs",
        "allowed_tools",
        "result_schema",
        "results",
    }

    assert all(baseline[field] == assisted[field] for field in matched)
    assert baseline["arx_semantic_assistance"] is False
    assert assisted["arx_semantic_assistance"] is True
    assert assisted["arx_treatment"]["host_mutation"] is False


def test_protocol_requires_measured_raw_values_and_derived_comparisons():
    protocol = load(BENCHMARK / "protocol.yaml")

    assert all(
        item["observation_classification"] == "MEASURED"
        and item["comparison_classification"] == "DERIVED"
        for item in protocol["direct_metrics"]
    )
    assert all(
        item["observation_classification"] == "MEASURED"
        for item in protocol["direct_results"]
    )
    assert protocol["claim_gate"]["initial_state"] == "UNVERIFIED"
    assert protocol["claim_gate"]["automatic_promotion"] is False


def test_empty_arms_generate_unknown_comparison_without_metrics_or_claims():
    for arm_id in ("baseline", "arx-assisted"):
        results = load(BENCHMARK / arm_id / "results.json")
        assert results["records"] == []
        assert results["collection_status"] == {
            "value": "NOT_STARTED",
            "classification": "MEASURED",
        }

    process = subprocess.run(
        [
            sys.executable,
            str(BENCHMARKS / "generate_comparison.py"),
            "ARX-BENCH-PY-001",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    comparison = json.loads(process.stdout)
    assert comparison["comparison_status"] == {
        "value": "NO_PAIRED_EVIDENCE",
        "classification": "UNKNOWN",
    }
    assert comparison["source_record_counts"] == {
        "baseline": {"value": 0, "classification": "DERIVED"},
        "arx-assisted": {"value": 0, "classification": "DERIVED"},
    }
    assert comparison["metrics"] == {}
    assert comparison["claim_status"] == {
        "value": "UNVERIFIED",
        "classification": "UNKNOWN",
    }
    assert "improvement" not in process.stdout.lower()
    assert "savings" not in process.stdout.lower()

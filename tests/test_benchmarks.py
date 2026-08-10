import json
from pathlib import Path

from arx.benchmark import discover_benchmarks, run_benchmark, run_suite
from arx.cli import main, parser
from arx.core.models import serialize
from arx.efficiency import MetricClassification


BENCHMARKS = Path(__file__).parents[1] / "benchmarks" / "fixtures"


def test_three_python_benchmarks_are_discoverable():
    scenarios = discover_benchmarks(BENCHMARKS)
    assert [item.benchmark_id for item in scenarios] == [
        "ARX-BENCH-PY-001",
        "ARX-BENCH-PY-002",
        "ARX-BENCH-PY-003",
    ]


def test_benchmark_001_reuses_existing_compatible_provider():
    result = run_benchmark(BENCHMARKS / "ARX-BENCH-PY-001")

    assert result.result == "PASS"
    assert result.semantic_result["decision"] == "YELLOW"
    assert result.semantic_result["resolved_provider"] == "python-3.14.6"
    assert result.semantic_result["preferred_provider"] == "python-3.12.13"
    assert result.efficiency["existing_provider_reused"] is True
    assert result.efficiency["new_installation_required"] is False
    assert result.efficiency["global_mutations"] == 0
    assert result.reuse.provider_observations_reused == 3


def test_benchmark_002_is_green_with_no_provider_change():
    result = run_benchmark(BENCHMARKS / "ARX-BENCH-PY-002")

    assert result.result == "PASS"
    assert result.semantic_result["decision"] == "GREEN"
    assert result.semantic_result["resolved_provider"] == "python-3.12.13"
    assert result.semantic_result["preferred_provider"] == "python-3.12.13"
    assert result.semantic_result["selected_candidate"] == "ARX-CANDIDATE-NO-ACTION"
    assert result.efficiency["new_installation_required"] is False


def test_benchmark_003_is_red_and_core_does_not_install():
    result = run_benchmark(BENCHMARKS / "ARX-BENCH-PY-003")

    assert result.result == "PASS"
    assert result.semantic_result["decision"] == "RED"
    assert result.semantic_result["preferred_provider"] is None
    assert result.semantic_result["selected_candidate"] == "ARX-CANDIDATE-PROVISION-PROJECT-PYTHON"
    assert result.efficiency["new_installation_required"] is True
    assert result.efficiency["global_mutations"] == 0
    assert result.efficiency["automatic_execution"] is False


def test_benchmark_metrics_have_provenance_and_no_energy_claim():
    result = run_benchmark(BENCHMARKS / "ARX-BENCH-PY-001")

    assert result.compression.raw_context_chars.classification is MetricClassification.MEASURED
    assert result.compression.semantic_contract_chars.classification is MetricClassification.MEASURED
    assert result.compression.ratio.value is not None
    assert result.token_estimate.raw_context.classification is MetricClassification.ESTIMATED
    assert result.metrics.unknown["cloud_energy_saved"].value is None
    assert result.metrics.unknown["cloud_cost_saved"].value is None


def test_benchmark_suite_is_reproducible():
    first = serialize(run_suite(BENCHMARKS))
    second = serialize(run_suite(BENCHMARKS))

    assert first == second
    assert first["passed"] == 3
    assert first["failed"] == 0
    assert all(item["result"] == "PASS" for item in first["results"])


def test_benchmark_report_contains_no_private_absolute_paths():
    encoded = json.dumps(serialize(run_suite(BENCHMARKS)))
    assert str(BENCHMARKS.resolve()) not in encoded
    assert "USERPROFILE" not in encoded


def test_benchmark_cli_is_additive_and_machine_readable(capsys):
    assert parser().parse_args(["benchmark", str(BENCHMARKS), "--json"]).command == "benchmark"
    assert main(["benchmark", str(BENCHMARKS), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "0.1"
    assert report["passed"] == 3
    assert report["failed"] == 0

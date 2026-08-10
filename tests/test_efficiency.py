import json
import os
from pathlib import Path

from arx.core.models import serialize
from arx.efficiency import (
    CacheStatus,
    MetricClassification,
    SemanticAnalysisSession,
    estimate_token_reduction,
    measure_compression,
    measure_report_efficiency,
)
from arx.exporters import project_codex_report
from arx.project import ExecutionContext, ProviderKind, inspect_project, make_provider, preflight, resolve_python


FIXTURES = Path(__file__).parent / "fixtures" / "python"


def machine(*versions):
    return {
        "python_installations": [
            {
                "path": path,
                "version": version,
                "healthy": healthy,
                "health_probe": "fixture",
                "evidence": [],
            }
            for path, version, healthy in versions
        ]
    }


def report_for(path, current_version="3.14.6", compatible=True):
    project = inspect_project(path)
    current = make_provider(path=r"C:\Python314\python.exe", version=current_version, kind=ProviderKind.CPYTHON, discovery_method="fixture", healthy=True)
    providers = [current]
    if compatible:
        providers.append(make_provider(path=project.root / ".venv" / "Scripts" / "python.exe", version="3.12.13", kind=ProviderKind.VIRTUAL_ENVIRONMENT, discovery_method="fixture", healthy=True))
    context = ExecutionContext.capture(project.root, environment={"PATH": os.pathsep.join(item.path for item in providers)})
    resolution = resolve_python(providers, context, command_paths=[current.path])
    return preflight(project, providers, resolution)


def test_semantic_compression_uses_exact_character_and_byte_measurements():
    compression = measure_compression("abcdefgh", "ab")

    assert compression.raw_context_chars.value == 8
    assert compression.semantic_contract_chars.value == 2
    assert compression.raw_context_bytes.value == 8
    assert compression.semantic_contract_bytes.value == 2
    assert compression.ratio.value == 4.0
    assert compression.ratio.classification is MetricClassification.MEASURED
    assert compression.ratio.method == "raw_context_chars / semantic_contract_chars"


def test_semantic_compression_handles_empty_contract_without_division():
    compression = measure_compression("raw", "")

    assert compression.ratio.value is None
    assert compression.ratio.classification is MetricClassification.UNKNOWN
    assert "zero" in compression.ratio.method


def test_token_reduction_is_transparently_estimated():
    estimate = estimate_token_reduction("a" * 100, "b" * 20)

    assert estimate.raw_context.value == 25
    assert estimate.semantic_contract.value == 5
    assert estimate.reduction.value == 20
    assert estimate.percent.value == 80.0
    assert estimate.raw_context.classification is MetricClassification.ESTIMATED
    assert estimate.method == "ceil(characters / 4.0); local approximation"


def test_report_efficiency_separates_measured_inferred_estimated_and_unknown():
    report = report_for(FIXTURES / "case_b")
    contract = project_codex_report(report, "0.3.0")
    metrics = measure_report_efficiency(report, contract)

    assert metrics.measured["providers_discovered"].value == 2
    assert metrics.measured["providers_considered"].value == 2
    assert metrics.measured["providers_rejected"].value == 1
    assert metrics.measured["requirements_evaluated"].value == len(report.evaluations)
    assert metrics.inferred["existing_provider_reused"].value is True
    assert metrics.inferred["new_runtime_installation_required"].value is False
    assert metrics.estimated["raw_context_tokens"].classification is MetricClassification.ESTIMATED
    assert metrics.unknown["external_ai_turns_avoided"].value is None
    assert metrics.unknown["cloud_energy_saved"].value is None


def test_ai_contract_efficiency_section_is_optional_and_provenanced():
    report = report_for(FIXTURES / "case_b")
    base = project_codex_report(report, "0.3.0")
    assert "efficiency" not in base

    metrics = measure_report_efficiency(report, base)
    enriched = project_codex_report(report, "0.3.0", efficiency=metrics)

    assert enriched["schema_version"] == "0.2"
    assert enriched["efficiency"]["measured"]["raw_context_chars"]["classification"] == "MEASURED"
    assert enriched["efficiency"]["estimated"]["raw_context_tokens"]["classification"] == "ESTIMATED"
    assert enriched["efficiency"]["unknown"]["cloud_energy_saved"]["classification"] == "UNKNOWN"


def test_analysis_session_actually_reuses_fresh_observations(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="cache"\nrequires-python=">=3.12,<3.13"', encoding="utf-8")
    current_path = str(tmp_path / "providers" / "python.exe")
    fixture_machine = machine((current_path, "3.12.13", True))
    session = SemanticAnalysisSession()

    first = session.analyze(tmp_path, fixture_machine, environment={"PATH": current_path}, command_paths=[current_path])
    second = session.analyze(tmp_path, fixture_machine, environment={"PATH": current_path}, command_paths=[current_path])

    assert first.freshness["project"].status is CacheStatus.MISS
    assert first.freshness["resolution"].status is CacheStatus.MISS
    assert second.freshness["project"].status is CacheStatus.HIT
    assert second.freshness["providers"].status is CacheStatus.HIT
    assert second.freshness["resolution"].status is CacheStatus.HIT
    assert second.freshness["semantic_conclusion"].status is CacheStatus.HIT
    assert second.reuse.project_observations_reused == 1
    assert second.reuse.provider_observations_reused == 1
    assert second.reuse.resolutions_reused == 1
    assert second.reuse.semantic_conclusions_reused == 1


def test_manifest_fingerprint_invalidates_project_and_conclusion(tmp_path):
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text('[project]\nname="cache"\nrequires-python=">=3.12,<3.13"', encoding="utf-8")
    current_path = str(tmp_path / "providers" / "python.exe")
    fixture_machine = machine((current_path, "3.12.13", True))
    session = SemanticAnalysisSession()
    session.analyze(tmp_path, fixture_machine, environment={"PATH": current_path}, command_paths=[current_path])

    manifest.write_text('[project]\nname="cache"\nrequires-python=">=3.13,<3.14"', encoding="utf-8")
    changed = session.analyze(tmp_path, fixture_machine, environment={"PATH": current_path}, command_paths=[current_path])

    assert changed.freshness["project"].status is CacheStatus.STALE
    assert changed.freshness["semantic_conclusion"].status is CacheStatus.MISS
    assert changed.report.project.primary_python_requirement.constraint == ">=3.13,<3.14"


def test_execution_context_change_invalidates_resolution_only(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="context"\nrequires-python=">=3.12,<3.13"', encoding="utf-8")
    current_path = str(tmp_path / "providers" / "python.exe")
    fixture_machine = machine((current_path, "3.12.13", True))
    session = SemanticAnalysisSession()
    first = session.analyze(tmp_path, fixture_machine, environment={"PATH": "one"}, command_paths=[current_path])
    changed = session.analyze(tmp_path, fixture_machine, environment={"PATH": "two"}, command_paths=[current_path])

    assert first.report.context.id != changed.report.context.id
    assert changed.freshness["project"].status is CacheStatus.HIT
    assert changed.freshness["providers"].status is CacheStatus.HIT
    assert changed.freshness["resolution"].status is CacheStatus.MISS
    assert changed.freshness["semantic_conclusion"].status is CacheStatus.MISS


def test_provider_freshness_expiry_invalidates_dependent_resolution(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="ttl"\nrequires-python=">=3.12,<3.13"', encoding="utf-8")
    current_path = str(tmp_path / "providers" / "python.exe")
    fixture_machine = machine((current_path, "3.12.13", True))
    now = [100.0]
    session = SemanticAnalysisSession(clock=lambda: now[0], provider_ttl_seconds=10.0)
    session.analyze(tmp_path, fixture_machine, environment={"PATH": current_path}, command_paths=[current_path])
    now[0] = 111.0
    expired = session.analyze(tmp_path, fixture_machine, environment={"PATH": current_path}, command_paths=[current_path])

    assert expired.freshness["providers"].status is CacheStatus.STALE
    assert expired.freshness["resolution"].status is CacheStatus.MISS
    assert expired.freshness["providers"].fresh is True
    assert expired.freshness["providers"].source_fingerprint
    assert "created_at" not in json.dumps(serialize(expired.reuse))

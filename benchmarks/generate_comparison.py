from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any


CLASSIFICATIONS = {"MEASURED", "DERIVED", "ESTIMATED", "INFERRED", "UNKNOWN"}


class BenchmarkValidationError(ValueError):
    pass


def load_document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkValidationError(f"Cannot read benchmark document {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkValidationError(f"Benchmark document must be an object: {path}")
    return value


def classified(value: Any, classification: str) -> dict[str, Any]:
    if classification not in CLASSIFICATIONS:
        raise BenchmarkValidationError(f"Unknown classification: {classification}")
    return {"value": value, "classification": classification}


def validate_classified(item: Any, label: str, *, measured_only: bool = False) -> None:
    if not isinstance(item, dict) or set(item) != {"value", "classification"}:
        raise BenchmarkValidationError(
            f"{label} must contain exactly value and classification."
        )
    classification = item["classification"]
    if classification not in CLASSIFICATIONS:
        raise BenchmarkValidationError(f"{label} has unknown classification {classification!r}.")
    if measured_only and classification != "MEASURED":
        raise BenchmarkValidationError(f"{label} must be a direct MEASURED observation.")


def validate_protocol(protocol: dict[str, Any], benchmark_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if protocol.get("benchmark_id") != benchmark_id:
        raise BenchmarkValidationError("Protocol benchmark_id does not match the requested benchmark.")
    vocabulary = set(protocol["observation_record_requirements"]["classification_vocabulary"])
    if vocabulary != CLASSIFICATIONS:
        raise BenchmarkValidationError("Protocol classification vocabulary is incomplete or unexpected.")
    metrics = {item["metric_id"]: item for item in protocol.get("direct_metrics", [])}
    results = {item["result_id"]: item for item in protocol.get("direct_results", [])}
    if len(metrics) != len(protocol.get("direct_metrics", [])) or len(results) != len(
        protocol.get("direct_results", [])
    ):
        raise BenchmarkValidationError("Metric and result identifiers must be unique.")
    if not metrics or not results:
        raise BenchmarkValidationError("Protocol must define direct metrics and results.")
    for identifier, definition in metrics.items():
        if definition.get("observation_classification") != "MEASURED":
            raise BenchmarkValidationError(f"Raw metric {identifier} must be MEASURED.")
        if definition.get("comparison_classification") != "DERIVED":
            raise BenchmarkValidationError(f"Comparison metric {identifier} must be DERIVED.")
    for identifier, definition in results.items():
        if definition.get("observation_classification") != "MEASURED":
            raise BenchmarkValidationError(f"Raw result {identifier} must be MEASURED.")
    return metrics, results


def validate_matched_arms(baseline: dict[str, Any], assisted: dict[str, Any]) -> None:
    matched_fields = (
        "scenario",
        "task",
        "start_rule",
        "stop_rule",
        "allowed_inputs",
        "allowed_tools",
        "result_schema",
        "results",
    )
    for field in matched_fields:
        if baseline.get(field) != assisted.get(field):
            raise BenchmarkValidationError(f"Experimental arms differ in controlled field {field}.")
    if baseline.get("arx_semantic_assistance") is not False:
        raise BenchmarkValidationError("Baseline arm must not receive ARX semantic assistance.")
    if assisted.get("arx_semantic_assistance") is not True:
        raise BenchmarkValidationError("ARX-assisted arm must receive the registered treatment.")
    if assisted.get("arx_treatment", {}).get("host_mutation") is not False:
        raise BenchmarkValidationError("ARX treatment must remain read-only.")


def _validate_numeric(value: Any, definition: dict[str, Any], label: str) -> None:
    expected_type = definition["value_type"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkValidationError(f"{label} must be numeric.")
    if expected_type == "integer" and not isinstance(value, int):
        raise BenchmarkValidationError(f"{label} must be an integer.")
    if value < definition.get("minimum", value):
        raise BenchmarkValidationError(f"{label} is below its registered minimum.")


def _validate_result_value(value: Any, definition: dict[str, Any], label: str) -> None:
    if "allowed_values" in definition and value not in definition["allowed_values"]:
        raise BenchmarkValidationError(f"{label} is not an allowed result value.")
    value_type = definition.get("value_type")
    if value_type == "array" and not isinstance(value, list):
        raise BenchmarkValidationError(f"{label} must be an array.")
    if value_type == "string_or_null" and value is not None and not isinstance(value, str):
        raise BenchmarkValidationError(f"{label} must be a string or null.")


def validate_results(
    document: dict[str, Any],
    *,
    benchmark_id: str,
    arm_id: str,
    metric_definitions: dict[str, Any],
    result_definitions: dict[str, Any],
    required_fields: set[str],
) -> list[dict[str, Any]]:
    if document.get("benchmark_id") != benchmark_id or document.get("arm_id") != arm_id:
        raise BenchmarkValidationError(f"Results identity does not match arm {arm_id}.")
    validate_classified(document.get("collection_status"), f"{arm_id}.collection_status", measured_only=True)
    records = document.get("records")
    if not isinstance(records, list):
        raise BenchmarkValidationError(f"{arm_id}.records must be an array.")
    seen_trials: set[str] = set()
    for index, record in enumerate(records):
        label = f"{arm_id}.records[{index}]"
        if not isinstance(record, dict) or not required_fields.issubset(record):
            raise BenchmarkValidationError(f"{label} is missing required observation fields.")
        if record["arm_id"] != arm_id:
            raise BenchmarkValidationError(f"{label}.arm_id is contradictory.")
        if record["trial_id"] in seen_trials:
            raise BenchmarkValidationError(f"Duplicate trial_id {record['trial_id']!r} in {arm_id}.")
        seen_trials.add(record["trial_id"])
        if set(record["metrics"]) != set(metric_definitions):
            raise BenchmarkValidationError(f"{label}.metrics must match the registered metrics exactly.")
        if set(record["results"]) != set(result_definitions):
            raise BenchmarkValidationError(f"{label}.results must match the registered results exactly.")
        for identifier, definition in metric_definitions.items():
            observation = record["metrics"][identifier]
            validate_classified(observation, f"{label}.metrics.{identifier}", measured_only=True)
            _validate_numeric(observation["value"], definition, f"{label}.metrics.{identifier}.value")
        for identifier, definition in result_definitions.items():
            observation = record["results"][identifier]
            validate_classified(observation, f"{label}.results.{identifier}", measured_only=True)
            _validate_result_value(observation["value"], definition, f"{label}.results.{identifier}.value")
        deviations = record["protocol_deviations"]
        if not isinstance(deviations, list):
            raise BenchmarkValidationError(f"{label}.protocol_deviations must be an array.")
        for deviation_index, deviation in enumerate(deviations):
            validate_classified(
                deviation,
                f"{label}.protocol_deviations[{deviation_index}]",
                measured_only=True,
            )
    return records


def _records_by_pair(records: list[dict[str, Any]], arm_id: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        pair_id = record["pair_id"]
        if pair_id in result:
            raise BenchmarkValidationError(f"Duplicate pair_id {pair_id!r} in {arm_id}.")
        result[pair_id] = record
    return result


def generate(benchmark_root: Path) -> dict[str, Any]:
    benchmark_id = benchmark_root.name
    protocol = load_document(benchmark_root / "protocol.yaml")
    metric_definitions, result_definitions = validate_protocol(protocol, benchmark_id)
    arms = {item["arm_id"]: item for item in protocol["arms"]}
    if set(arms) != {"baseline", "arx-assisted"}:
        raise BenchmarkValidationError("Protocol must define baseline and arx-assisted arms.")
    arm_documents = {
        arm_id: load_document(benchmark_root / definition["definition"])
        for arm_id, definition in arms.items()
    }
    validate_matched_arms(arm_documents["baseline"], arm_documents["arx-assisted"])
    required_fields = set(protocol["observation_record_requirements"]["required_fields"])
    records = {
        arm_id: validate_results(
            load_document(benchmark_root / definition["results"]),
            benchmark_id=benchmark_id,
            arm_id=arm_id,
            metric_definitions=metric_definitions,
            result_definitions=result_definitions,
            required_fields=required_fields,
        )
        for arm_id, definition in arms.items()
    }
    paired = {
        arm_id: _records_by_pair(items, arm_id) for arm_id, items in records.items()
    }
    pair_ids = sorted(set(paired["baseline"]) & set(paired["arx-assisted"]))
    comparison: dict[str, Any] = {
        "schema_version": "1.0",
        "benchmark_id": benchmark_id,
        "comparison_status": classified(
            "PAIRED_COMPARISON_AVAILABLE" if pair_ids else "NO_PAIRED_EVIDENCE",
            "DERIVED" if pair_ids else "UNKNOWN",
        ),
        "source_record_counts": {
            arm_id: classified(len(items), "DERIVED") for arm_id, items in records.items()
        },
        "paired_trial_count": classified(len(pair_ids), "DERIVED"),
        "paired_trial_ids": classified(pair_ids, "DERIVED"),
        "metrics": {},
        "claim_status": classified("UNVERIFIED", "UNKNOWN"),
        "interpretation": "Signed differences only; no directional interpretation or claim is generated.",
    }
    if not pair_ids:
        return comparison
    for identifier, definition in metric_definitions.items():
        baseline_values = [
            paired["baseline"][pair_id]["metrics"][identifier]["value"]
            for pair_id in pair_ids
        ]
        assisted_values = [
            paired["arx-assisted"][pair_id]["metrics"][identifier]["value"]
            for pair_id in pair_ids
        ]
        baseline_mean = statistics.fmean(baseline_values)
        assisted_mean = statistics.fmean(assisted_values)
        comparison["metrics"][identifier] = {
            "unit": definition["unit"],
            "baseline_mean": classified(baseline_mean, "DERIVED"),
            "arx_assisted_mean": classified(assisted_mean, "DERIVED"),
            "arx_assisted_minus_baseline": classified(
                assisted_mean - baseline_mean, "DERIVED"
            ),
        }
    return comparison


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Validate matched ARX benchmark observations and generate a neutral comparison."
    )
    value.add_argument("benchmark_id", help="Benchmark directory name, for example ARX-BENCH-PY-001")
    value.add_argument("--output", type=Path, help="Optional JSON output path; stdout is always used otherwise")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    benchmark_root = Path(__file__).resolve().parent / args.benchmark_id
    try:
        comparison = generate(benchmark_root)
    except BenchmarkValidationError as exc:
        print(f"benchmark validation failed: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(comparison, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

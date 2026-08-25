import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from arx import __version__
from arx.cli import envelope
from arx.core.models import serialize
from arx.exporters import project_codex_report
from arx.project import (
    ExecutionContext,
    inspect_project,
    make_provider,
    preflight,
    resolve_python,
)

SCHEMAS = Path(__file__).parents[1] / "schemas"


def load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def validate(name, instance):
    schemas = [
        load(item)
        for item in (
            "project-dna.schema.json",
            "project-preflight.schema.json",
            "ai-contract.schema.json",
        )
    ]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    Draft202012Validator(load(name), registry=registry).validate(instance)


def semantic_report(tmp_path, resolved_version, extra_version=None):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="schema-fixture"\nrequires-python=">=3.12,<3.13"',
        encoding="utf-8",
    )
    project = inspect_project(tmp_path)
    current = make_provider(
        path=r"C:\Current\python.exe",
        version=resolved_version,
        discovery_method="schema fixture",
        healthy=True,
    )
    providers = [current]
    if extra_version:
        providers.append(
            make_provider(
                path=r"C:\Other\python.exe",
                version=extra_version,
                discovery_method="schema fixture",
                healthy=True,
            )
        )
    context = ExecutionContext.capture(
        project.root, environment={"PATH": r"C:\Current"}
    )
    resolution = resolve_python(providers, context, command_paths=[current.path])
    return project, preflight(project, providers, resolution)


def test_project_schema_files_are_valid_json():
    for name in ("project-dna.schema.json", "project-preflight.schema.json", "ai-contract.schema.json"):
        assert load(name)["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_preflight_schema_defines_each_semantic_dimension():
    definitions = load("project-preflight.schema.json")["$defs"]
    assert set(definitions) >= {
        "requirement",
        "provider",
        "providerGraph",
        "executionContext",
        "resolution",
        "relevance",
        "satisfaction",
        "conflict",
        "severity",
        "policy",
        "resolutionPlan",
        "explanationGraph",
    }


def test_ai_contract_schema_version_is_independent_from_application_version():
    schema = load("ai-contract.schema.json")
    assert schema["properties"]["schema_version"]["const"] == "0.2"
    assert "const" not in schema["properties"]["producer"]["properties"]["version"]
    assert set(schema["required"]) >= {
        "facts",
        "decisions",
        "selected_providers",
        "blockers",
        "warnings",
        "recommendations",
        "constraints",
        "unknowns",
        "evidence_references",
    }
    finding = schema["$defs"]["finding"]
    assert set(finding["required"]) >= {
        "finding_id",
        "severity",
        "category",
        "message",
        "evidence_refs",
    }
    selected = schema["properties"]["selected_providers"]
    assert set(selected["required"]) >= {
        "resolved",
        "compatible",
        "preferred",
        "pinned",
        "pinned_constraints",
    }


def test_application_and_legacy_schema_versions_remain_independent():
    assert __version__ == "4.0.0b4"
    assert 'version = "4.0.0b4"' in (SCHEMAS.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert envelope()["schema_version"] == "0.1"


def test_project_dna_and_preflight_instances_validate_against_schema(tmp_path):
    project, report = semantic_report(tmp_path, "3.12.13")

    validate("project-dna.schema.json", serialize(project))
    validate("project-preflight.schema.json", serialize(report))


@pytest.mark.parametrize(
    ("resolved_version", "extra_version", "decision"),
    [
        ("3.12.13", None, "GREEN"),
        ("3.14.6", "3.12.13", "YELLOW"),
        ("3.14.6", "3.11.9", "RED"),
    ],
)
def test_canonical_ai_contracts_validate_against_schema(
    tmp_path, resolved_version, extra_version, decision
):
    _, report = semantic_report(tmp_path, resolved_version, extra_version)
    contract = project_codex_report(report, __version__)

    assert contract["decision"] == decision
    validate("ai-contract.schema.json", contract)

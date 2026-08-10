import json
from pathlib import Path


SCHEMAS = Path(__file__).parents[1] / "schemas"


def load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


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

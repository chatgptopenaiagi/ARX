import importlib.util
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check-architecture.py"
SPEC = importlib.util.spec_from_file_location("arx_architecture_check", CHECKER_PATH)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


def test_current_arx_dependency_graph_is_allowed_and_acyclic():
    report = CHECKER.analyze_source_tree(ROOT / "src" / "arx")

    assert report.passed
    assert not report.violations
    assert not report.cycles
    assert not any(source in {"core", "machine", "software", "project"} and target == "advisory" for source, target in report.edges)


def test_forbidden_import_mutation_proves_fail_revert_pass(tmp_path):
    source = ROOT / "src" / "arx"
    mutated = tmp_path / "arx"
    shutil.copytree(source, mutated)

    pristine = CHECKER.analyze_source_tree(mutated)
    assert pristine.passed

    core_models = mutated / "core" / "models.py"
    original = core_models.read_text(encoding="utf-8")
    core_models.write_text(original + "\nfrom arx.advisory import OpenAIProvider\n", encoding="utf-8")
    failed = CHECKER.analyze_source_tree(mutated)
    assert not failed.passed
    assert any(item.source_layer == "core" and item.target_layer == "advisory" for item in failed.violations)

    core_models.write_text(original, encoding="utf-8")
    reverted = CHECKER.analyze_source_tree(mutated)
    assert reverted.passed

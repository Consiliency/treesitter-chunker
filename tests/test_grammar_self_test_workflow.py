"""Grammar self-test utilities use current APIs without network installation."""

import sys
from pathlib import Path

from chunker.grammar_management.core import load_compiled_grammar
from chunker.grammar_management.testing import IntegrationTester, SystemValidator
from tree_sitter_language_pack import cache_dir


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"


def test_isolated_workflow_parses_fixture_and_rejects_missing_grammar(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    grammar_path = ROOT / "build" / f"python{suffix}"
    if not grammar_path.exists():
        grammar_path = Path(cache_dir()) / f"libtree_sitter_python{suffix}"
    assert grammar_path.exists()
    assert (
        not load_compiled_grammar(grammar_path, "python")
        .parse(source)
        .root_node.has_error
    )
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    work_dir = tmp_path / "self-test"
    tester = IntegrationTester(work_dir)
    assert tester.dir_manager.base_dir == work_dir
    assert tester.cache_manager.cache_dir == work_dir / "cache"

    valid = tester.test_complete_workflow(FIXTURE, "python", grammar_path)
    assert valid["status"] == "pass", valid
    assert valid["workflows_tested"] == ["discovery", "validation"]
    assert valid["errors"] == []

    invalid_path = tmp_path / "invalid.py"
    invalid_path.write_text("def broken(\n", encoding="utf-8")
    invalid = tester.test_complete_workflow(invalid_path, "python", grammar_path)
    assert invalid["status"] == "fail", invalid
    assert "Sample contains parse errors" in invalid["errors"]

    missing = tester.test_complete_workflow(FIXTURE, "missing_grammar", grammar_path)
    assert missing["status"] == "fail", missing
    assert missing["errors"]
    assert tester.test_results["complete_workflow"] == missing

    health = SystemValidator(tester.grammar_manager, tester.config)
    assert health.check_system_health()["status"] == "healthy"
    integration = tester.test_cross_component_integration()
    assert integration["status"] == "pass", integration
    assert "config-cache" in integration["integration_points"]
    tester.cleanup()
    assert work_dir.exists()
    assert list(home.iterdir()) == []

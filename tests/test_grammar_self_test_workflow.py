"""Grammar self-test utilities use current APIs without network installation."""

from pathlib import Path

from chunker import get_parser
from chunker.grammar_management.testing import IntegrationTester, SystemValidator


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)


def test_isolated_workflow_parses_fixture_and_rejects_missing_grammar(
    tmp_path: Path,
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    work_dir = tmp_path / "self-test"
    tester = IntegrationTester(work_dir)
    assert tester.dir_manager.base_dir == work_dir
    assert tester.cache_manager.cache_dir == work_dir / "cache"

    valid = tester.test_complete_workflow(FIXTURE, "python")
    assert valid["status"] == "pass", valid
    assert valid["workflows_tested"] == ["discovery", "validation"]
    assert valid["errors"] == []

    invalid_path = tmp_path / "invalid.py"
    invalid_path.write_text("def broken(\n", encoding="utf-8")
    invalid = tester.test_complete_workflow(invalid_path, "python")
    assert invalid["status"] == "fail", invalid
    assert "Sample contains parse errors" in invalid["errors"]

    missing = tester.test_complete_workflow(FIXTURE, "missing_grammar")
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

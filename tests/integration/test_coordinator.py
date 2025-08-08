"""Tests for the integration coordinator."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.coordinator import (
    IntegrationCoordinator,
    TestResult,
    TestScenario,
)


class TestIntegrationCoordinator:
    """Test the IntegrationCoordinator class."""

    @classmethod
    @pytest.fixture
    def coordinator(cls, tmp_path):
        """Create a coordinator instance."""
        base_path = tmp_path / "worktrees"
        main_repo = tmp_path / "main"
        base_path.mkdir()
        main_repo.mkdir()
        return IntegrationCoordinator(base_path, main_repo)

    @classmethod
    def test_register_scenario(cls, coordinator):
        """Test scenario registration."""
        scenario = TestScenario(
            name="test_scenario",
            description="Test description",
            worktree="test-worktree",
            test_file="test_file.py",
        )
        coordinator.register_scenario(scenario)
        assert "test_scenario" in coordinator.scenarios
        assert coordinator.scenarios["test_scenario"] == scenario

    @classmethod
    def test_register_scenarios_from_config(cls, coordinator, tmp_path):
        """Test loading scenarios from config file."""
        config_file = tmp_path / "test_scenarios.json"
        config_data = {
            "scenarios": [
                {
                    "name": "scenario1",
                    "description": "Test 1",
                    "worktree": "wt1",
                    "test_file": "test1.py",
                },
                {
                    "name": "scenario2",
                    "description": "Test 2",
                    "worktree": "wt2",
                    "test_file": "test2.py",
                    "dependencies": ["scenario1"],
                    "tags": ["important"],
                },
            ],
        }
        with Path(config_file).open("w", encoding="utf-8") as f:
            json.dump(config_data, f)
        coordinator.register_scenarios_from_config(config_file)
        assert len(coordinator.scenarios) == 2
        assert "scenario1" in coordinator.scenarios
        assert "scenario2" in coordinator.scenarios
        assert coordinator.scenarios["scenario2"].dependencies == ["scenario1"]
        assert coordinator.scenarios["scenario2"].tags == ["important"]

    @staticmethod
    def test_verify_worktree_setup(coordinator):
        """Test worktree verification."""
        worktree_path = coordinator.base_path / "test-worktree"
        worktree_path.mkdir()
        assert not coordinator.verify_worktree_setup("test-worktree")
        (worktree_path / ".git").touch()
        assert not coordinator.verify_worktree_setup("test-worktree")
        (worktree_path / ".venv").mkdir()
        assert not coordinator.verify_worktree_setup("test-worktree")
        build_dir = worktree_path / "build"
        build_dir.mkdir()
        (build_dir / "test.so").touch()
        assert coordinator.verify_worktree_setup("test-worktree")

    @classmethod
    @patch("subprocess.run")
    def test_setup_worktree(cls, mock_run, coordinator):
        """Test worktree setup."""
        mock_run.return_value = MagicMock(returncode=0)
        result = coordinator.setup_worktree("test-worktree", "test-branch")
        assert result is True
        assert mock_run.call_count == 4
        resources = coordinator.resource_tracker.get_all_resources()
        assert len(resources) == 1
        assert resources[0]["resource_type"] == "worktree"

    @staticmethod
    @patch("subprocess.run")
    def test_setup_worktree_failure(mock_run, coordinator):
        """Test worktree setup failure handling."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = coordinator.setup_worktree("test-worktree", "test-branch")
        assert result is False
        assert len(coordinator.results) == 1
        assert coordinator.results[0].status == "error"

    @classmethod
    @patch("subprocess.run")
    def test_run_scenario(cls, mock_run, coordinator):
        """Test running a single scenario."""
        scenario = TestScenario(
            name="test",
            description="Test",
            worktree="test-wt",
            test_file="test.py",
        )
        worktree_path = coordinator.base_path / "test-wt"
        worktree_path.mkdir()
        (worktree_path / ".venv" / "bin").mkdir(parents=True)
        (worktree_path / ".venv" / "bin" / "python").touch()
        mock_run.return_value = MagicMock(returncode=0, stdout="Test passed", stderr="")
        result = coordinator.run_scenario(scenario)
        assert result.status == "passed"
        assert result.output == "Test passed"
        assert result.duration > 0
        resources = coordinator.resource_tracker.get_all_resources(state="released")
        assert len(resources) == 1
        assert resources[0]["resource_type"] == "test_execution"

    @classmethod
    def test_check_dependencies(cls, coordinator):
        """Test dependency checking."""
        scenario1 = TestScenario(
            name="test1",
            description="Test 1",
            worktree="wt1",
            test_file="test1.py",
        )
        scenario2 = TestScenario(
            name="test2",
            description="Test 2",
            worktree="wt2",
            test_file="test2.py",
            dependencies=["test1"],
        )
        assert not coordinator.check_dependencies(scenario2)
        coordinator.results.append(
            TestResult(scenario=scenario1, status="failed", duration=1.0, output=""),
        )
        assert not coordinator.check_dependencies(scenario2)
        coordinator.results.append(
            TestResult(scenario=scenario1, status="passed", duration=1.0, output=""),
        )
        assert coordinator.check_dependencies(scenario2)

    @classmethod
    def test_topological_sort(cls, coordinator):
        """Test scenario sorting by dependencies."""
        s1 = TestScenario(name="s1", description="", worktree="", test_file="")
        s2 = TestScenario(
            name="s2",
            description="",
            worktree="",
            test_file="",
            dependencies=["s1"],
        )
        s3 = TestScenario(
            name="s3",
            description="",
            worktree="",
            test_file="",
            dependencies=["s1", "s2"],
        )
        s4 = TestScenario(name="s4", description="", worktree="", test_file="")
        coordinator.scenarios = {"s1": s1, "s2": s2, "s3": s3, "s4": s4}
        sorted_scenarios = coordinator._topological_sort_scenarios()
        names = [s.name for s in sorted_scenarios]
        assert names.index("s1") < names.index("s2")
        assert names.index("s2") < names.index("s3")
        assert "s4" in names

    @classmethod
    def test_circular_dependency_detection(cls, coordinator):
        """Test circular dependency detection."""
        s1 = TestScenario(
            name="s1",
            description="",
            worktree="",
            test_file="",
            dependencies=["s2"],
        )
        s2 = TestScenario(
            name="s2",
            description="",
            worktree="",
            test_file="",
            dependencies=["s1"],
        )
        coordinator.scenarios = {"s1": s1, "s2": s2}
        with pytest.raises(ValueError, match="Circular"):
            coordinator._topological_sort_scenarios()

    @classmethod
    def test_generate_report(cls, coordinator):
        """Test report generation."""
        scenario1 = TestScenario(
            name="test1",
            description="",
            worktree="wt1",
            test_file="",
        )
        scenario2 = TestScenario(
            name="test2",
            description="",
            worktree="wt2",
            test_file="",
        )
        coordinator.results = [
            TestResult(scenario=scenario1, status="passed", duration=1.5, output=""),
            TestResult(
                scenario=scenario2,
                status="failed",
                duration=2.0,
                output="",
                error="Test failed",
            ),
            TestResult(scenario=scenario1, status="passed", duration=1.0, output=""),
        ]
        coordinator.resource_tracker.track_resource(
            module="test",
            resource_type="process",
            resource_id="leaked_proc",
        )
        report = coordinator.generate_report()
        assert report["summary"]["total"] == 3
        assert report["summary"]["passed"] == 2
        assert report["summary"]["failed"] == 1
        assert report["summary"]["duration"] == 4.5
        assert report["summary"]["success_rate"] == pytest.approx(66.67, 0.01)
        assert report["by_worktree"]["wt1"]["total"] == 2
        assert report["by_worktree"]["wt1"]["passed"] == 2
        assert report["by_worktree"]["wt2"]["total"] == 1
        assert report["by_worktree"]["wt2"]["failed"] == 1
        assert len(report["failures"]) == 1
        assert report["failures"][0]["scenario"] == "test2"
        assert len(report["resource_leaks"]) == 1
        assert report["resource_leaks"][0]["resource_id"] == "leaked_proc"

    @classmethod
    def test_save_report(cls, coordinator, tmp_path):
        """Test saving report to file."""
        scenario = TestScenario(
            name="test",
            description="",
            worktree="wt",
            test_file="",
        )
        coordinator.results = [
            TestResult(scenario=scenario, status="passed", duration=1.0, output=""),
        ]
        report_file = tmp_path / "test_report.json"
        coordinator.save_report(report_file)
        assert report_file.exists()
        with Path(report_file).open("r", encoding="utf-8") as f:
            loaded_report = json.load(f)
        assert loaded_report["summary"]["total"] == 1
        assert loaded_report["summary"]["passed"] == 1

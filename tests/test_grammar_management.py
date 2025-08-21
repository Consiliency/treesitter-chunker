"""Tests for the grammar management system."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from chunker._internal.grammar_management import (
    GrammarCompatibility,
    GrammarHealth,
    SmartGrammarManager,
)
from chunker._internal.user_grammar_tools import UserGrammarTools


class TestGrammarHealth:
    """Test GrammarHealth dataclass."""

    def test_grammar_health_creation(self):
        """Test creating a GrammarHealth instance."""
        health = GrammarHealth(
            language="python",
            status="healthy",
            issues=["No issues"],
            recommendations=["Keep using it"],
        )

        assert health.language == "python"
        assert health.status == "healthy"
        assert health.issues == ["No issues"]
        assert health.recommendations == ["Keep using it"]
        assert health.last_checked is None

    def test_grammar_health_defaults(self):
        """Test GrammarHealth with default values."""
        health = GrammarHealth(language="rust", status="corrupted")

        assert health.language == "rust"
        assert health.status == "corrupted"
        assert health.issues == []
        assert health.recommendations == []
        assert health.last_checked is None


class TestGrammarCompatibility:
    """Test GrammarCompatibility dataclass."""

    def test_grammar_compatibility_creation(self):
        """Test creating a GrammarCompatibility instance."""
        compat = GrammarCompatibility(
            language="go",
            tree_sitter_version="0.20.8",
            system_architecture="x86_64",
            os_platform="Linux",
            compilation_date="2024-01-15T10:30:00",
            compatibility_score=0.95,
        )

        assert compat.language == "go"
        assert compat.tree_sitter_version == "0.20.8"
        assert compat.system_architecture == "x86_64"
        assert compat.os_platform == "Linux"
        assert compat.compilation_date == "2024-01-15T10:30:00"
        assert compat.compatibility_score == 0.95

    def test_grammar_compatibility_defaults(self):
        """Test GrammarCompatibility with default values."""
        compat = GrammarCompatibility(
            language="java",
            tree_sitter_version="unknown",
            system_architecture="unknown",
            os_platform="unknown",
        )

        assert compat.language == "java"
        assert compat.tree_sitter_version == "unknown"
        assert compat.system_architecture == "unknown"
        assert compat.os_platform == "unknown"
        assert compat.compilation_date is None
        assert compat.compatibility_score == 0.0


class TestSmartGrammarManager:
    """Test SmartGrammarManager class."""

    @pytest.fixture()
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir) / "build"
            grammars_dir = Path(temp_dir) / "grammars"
            build_dir.mkdir()
            grammars_dir.mkdir()
            yield build_dir, grammars_dir

    @pytest.fixture()
    def manager(self, temp_dirs):
        """Create a SmartGrammarManager instance."""
        build_dir, grammars_dir = temp_dirs
        return SmartGrammarManager(build_dir, grammars_dir)

    def test_manager_initialization(self, temp_dirs):
        """Test manager initialization."""
        build_dir, grammars_dir = temp_dirs
        manager = SmartGrammarManager(build_dir, grammars_dir)

        assert manager.build_dir == build_dir
        assert manager.grammars_dir == grammars_dir
        assert manager.health_cache == {}
        assert manager.compatibility_cache == {}

    def test_diagnose_grammar_missing(self, manager):
        """Test diagnosing a missing grammar."""
        health = manager.diagnose_grammar_issues("missing_lang")

        assert health.language == "missing_lang"
        assert health.status == "missing"
        assert len(health.issues) > 0
        assert len(health.recommendations) > 0
        assert "not found" in health.issues[0]

    def test_diagnose_grammar_corrupted(self, manager, temp_dirs):
        """Test diagnosing a corrupted grammar."""
        build_dir, _ = temp_dirs

        # Create an empty .so file (corrupted)
        so_file = build_dir / "corrupted_lang.so"
        so_file.touch()

        health = manager.diagnose_grammar_issues("corrupted_lang")

        assert health.language == "corrupted_lang"
        assert health.status == "corrupted"
        assert len(health.issues) > 0
        assert "empty" in health.issues[0] or "0 bytes" in health.issues[0]

    @patch("ctypes.CDLL")
    def test_diagnose_grammar_healthy(self, mock_cdll, manager, temp_dirs):
        """Test diagnosing a healthy grammar."""
        build_dir, _ = temp_dirs

        # Create a mock .so file with some content (not empty)
        so_file = build_dir / "healthy_lang.so"
        so_file.write_bytes(b"mock_so_content")

        # Mock the CDLL and symbol
        mock_lib = Mock()
        mock_lib.tree_sitter_healthy_lang = Mock()
        mock_cdll.return_value = mock_lib

        # Mock Language creation
        with patch(
            "chunker._internal.grammar_management.Language",
            create=True,
        ) as mock_language:
            mock_language.return_value = Mock()

            health = manager.diagnose_grammar_issues("healthy_lang")

            assert health.language == "healthy_lang"
            assert health.status == "healthy"
            assert len(health.recommendations) > 0

    @patch("ctypes.CDLL")
    def test_diagnose_grammar_incompatible(self, mock_cdll, manager, temp_dirs):
        """Test diagnosing an incompatible grammar."""
        build_dir, _ = temp_dirs

        # Create a mock .so file with some content (not empty)
        so_file = build_dir / "incompatible_lang.so"
        so_file.write_bytes(b"mock_so_content")

        # Mock CDLL to fail during loading (this triggers incompatible status)
        mock_cdll.side_effect = Exception("Incompatible architecture")

        health = manager.diagnose_grammar_issues("incompatible_lang")

        assert health.language == "incompatible_lang"
        assert health.status == "incompatible"
        assert len(health.issues) > 0
        assert "Incompatible architecture" in health.issues[0]

    def test_get_grammar_compatibility(self, manager):
        """Test getting grammar compatibility information."""
        compat = manager.get_grammar_compatibility("test_lang")

        assert compat.language == "test_lang"
        assert compat.tree_sitter_version in ["unknown", "0.20.8"]  # May be available
        assert compat.system_architecture in ["unknown", "x86_64"]  # May be available
        assert compat.os_platform in ["unknown", "Linux"]  # May be available
        assert compat.compatibility_score >= 0.0
        assert compat.compatibility_score <= 1.0

    def test_generate_recovery_plan_missing(self, manager):
        """Test generating recovery plan for missing grammar."""
        plan = manager.generate_recovery_plan("missing_lang")

        assert plan["language"] == "missing_lang"
        assert plan["current_status"] == "missing"
        assert plan["difficulty"] == "easy"
        assert plan["estimated_time"] == "5-15 minutes"
        assert len(plan["recovery_steps"]) > 0

    def test_generate_recovery_plan_corrupted(self, manager, temp_dirs):
        """Test generating recovery plan for corrupted grammar."""
        build_dir, _ = temp_dirs

        # Create an empty .so file
        so_file = build_dir / "corrupted_lang.so"
        so_file.touch()

        plan = manager.generate_recovery_plan("corrupted_lang")

        assert plan["language"] == "corrupted_lang"
        assert plan["current_status"] == "corrupted"
        assert plan["difficulty"] == "easy"
        assert plan["estimated_time"] == "3-10 minutes"
        assert len(plan["recovery_steps"]) > 0

    def test_generate_recovery_plan_incompatible(self, manager, temp_dirs):
        """Test generating recovery plan for incompatible grammar."""
        build_dir, _ = temp_dirs

        # Create a mock .so file with some content (not empty)
        so_file = build_dir / "incompatible_lang.so"
        so_file.write_bytes(b"mock_so_content")

        # Mock CDLL to fail during loading (this triggers incompatible status)
        with patch("ctypes.CDLL") as mock_cdll:
            mock_cdll.side_effect = Exception("Incompatible")

            plan = manager.generate_recovery_plan("incompatible_lang")

            assert plan["language"] == "incompatible_lang"
            assert plan["current_status"] == "incompatible"
            assert plan["difficulty"] == "medium"
            assert plan["estimated_time"] == "10-30 minutes"
            assert len(plan["recovery_steps"]) > 0

    def test_validate_all_grammars(self, manager, temp_dirs):
        """Test validating all grammars."""
        build_dir, _ = temp_dirs

        # Create some mock .so files
        (build_dir / "lang1.so").touch()
        (build_dir / "lang2.so").touch()

        all_health = manager.validate_all_grammars()

        assert len(all_health) == 2
        assert "lang1" in all_health
        assert "lang2" in all_health

    def test_get_system_requirements(self, manager):
        """Test getting system requirements."""
        requirements = manager.get_system_requirements()

        assert "tree_sitter_cli" in requirements
        assert "node_npm" in requirements
        assert "git" in requirements
        assert "compiler" in requirements
        assert "python_deps" in requirements

        # All should be boolean values
        for value in requirements.values():
            assert isinstance(value, bool)


class TestUserGrammarTools:
    """Test UserGrammarTools class."""

    @pytest.fixture()
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir) / "build"
            grammars_dir = Path(temp_dir) / "grammars"
            build_dir.mkdir()
            grammars_dir.mkdir()
            yield build_dir, grammars_dir

    @pytest.fixture()
    def tools(self, temp_dirs):
        """Create a UserGrammarTools instance."""
        build_dir, grammars_dir = temp_dirs
        return UserGrammarTools(build_dir, grammars_dir)

    def test_tools_initialization(self, temp_dirs):
        """Test tools initialization."""
        build_dir, grammars_dir = temp_dirs
        tools = UserGrammarTools(build_dir, grammars_dir)

        assert tools.build_dir == build_dir
        assert tools.grammars_dir == grammars_dir
        assert tools.manager is not None

    @patch("subprocess.run")
    def test_install_grammar_success(self, mock_run, tools):
        """Test successful grammar installation."""

        # Mock successful git clone and tree-sitter generate
        def mock_run_side_effect(*args, **kwargs):
            if "git" in args[0] and "clone" in args[0]:
                # Create the directory that git clone would create
                target_dir = tools.grammars_dir / "tree-sitter-test_lang"
                target_dir.mkdir()
                return Mock(returncode=0)
            if "tree-sitter" in args[0] and "generate" in args[0]:
                # Create the .so file that tree-sitter generate would create
                target_dir = tools.grammars_dir / "tree-sitter-test_lang"
                so_file = target_dir / "test_lang.so"
                so_file.write_bytes(b"mock_so_content")
                return Mock(returncode=0)
            return Mock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        # Mock the manager's diagnose_grammar_issues to return healthy status
        with patch.object(tools.manager, "diagnose_grammar_issues") as mock_diagnose:
            mock_diagnose.return_value = Mock(status="healthy")

            result = tools.install_grammar(
                "test_lang",
                "https://github.com/test/repo.git",
            )

            assert result["status"] == "success"
            assert len(result["steps_completed"]) > 0
            assert len(result["errors"]) == 0

    @patch("subprocess.run")
    def test_install_grammar_git_failure(self, mock_run, tools):
        """Test grammar installation with git failure."""

        # Mock git clone failure by making subprocess.run raise CalledProcessError
        def mock_run_side_effect(*args, **kwargs):
            if "git" in args[0] and "clone" in args[0]:
                raise subprocess.CalledProcessError(1, "git")
            return Mock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        result = tools.install_grammar("test_lang", "https://github.com/test/repo.git")

        assert result["status"] == "error"
        assert len(result["errors"]) > 0
        assert "Failed to clone repository" in result["errors"][0]

    @patch("subprocess.run")
    def test_install_grammar_tree_sitter_failure(self, mock_run, tools):
        """Test grammar installation with tree-sitter failure."""

        # Mock successful git clone but failed tree-sitter generate
        def mock_run_side_effect(*args, **kwargs):
            if "git" in args[0] and "clone" in args[0]:
                # Create the directory that git clone would create
                target_dir = tools.grammars_dir / "tree-sitter-test_lang"
                target_dir.mkdir()
                return Mock(returncode=0)
            if "tree-sitter" in args[0] and "generate" in args[0]:
                # Fail tree-sitter generate
                raise subprocess.CalledProcessError(1, "tree-sitter")
            return Mock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        result = tools.install_grammar("test_lang", "https://github.com/test/repo.git")

        assert result["status"] == "error"
        assert len(result["errors"]) > 0
        assert "Failed to generate grammar" in result["errors"][0]

    def test_remove_grammar_success(self, tools, temp_dirs):
        """Test successful grammar removal."""
        build_dir, _ = temp_dirs

        # Create mock .so file
        (build_dir / "test_lang.so").touch()

        # Create mock source directory
        source_dir = tools.grammars_dir / "tree-sitter-test_lang"
        source_dir.mkdir()
        (source_dir / "test_file.txt").touch()

        result = tools.remove_grammar("test_lang")

        assert result["status"] == "success"
        assert len(result["steps_completed"]) > 0
        assert len(result["errors"]) == 0

        # Check files were removed
        assert not (build_dir / "test_lang.so").exists()
        assert not source_dir.exists()

    def test_remove_grammar_not_found(self, tools):
        """Test removing non-existent grammar."""
        result = tools.remove_grammar("non_existent_lang")

        assert result["status"] == "success"
        assert len(result["warnings"]) > 0
        assert "No compiled grammar library found" in result["warnings"][0]

    @patch("subprocess.run")
    def test_update_grammar_success(self, mock_run, tools, temp_dirs):
        """Test successful grammar update."""
        build_dir, _ = temp_dirs

        # Create mock source directory
        source_dir = tools.grammars_dir / "tree-sitter-test_lang"
        source_dir.mkdir()
        (source_dir / ".git").mkdir()  # Mock git directory

        # Mock git commands
        mock_run.side_effect = [
            Mock(returncode=0),  # git fetch
            Mock(returncode=0, stdout=b"old_commit\n"),  # git rev-parse HEAD
            Mock(returncode=0, stdout=b"new_commit\n"),  # git rev-parse origin/main
            Mock(returncode=0),  # git checkout
            Mock(returncode=0),  # tree-sitter generate
        ]

        # Create mock .so file after generation
        (source_dir / "test_lang.so").touch()

        result = tools.update_grammar("test_lang")

        assert result["status"] == "success"
        assert len(result["steps_completed"]) > 0
        assert len(result["errors"]) == 0

    @patch("subprocess.run")
    def test_update_grammar_already_up_to_date(self, mock_run, tools, temp_dirs):
        """Test grammar update when already up to date."""
        # Create mock source directory
        source_dir = tools.grammars_dir / "tree-sitter-test_lang"
        source_dir.mkdir()
        (source_dir / ".git").mkdir()

        # Mock git commands - same commit
        mock_run.side_effect = [
            Mock(returncode=0),  # git fetch
            Mock(returncode=0, stdout=b"same_commit\n"),  # git rev-parse HEAD
            Mock(returncode=0, stdout=b"same_commit\n"),  # git rev-parse origin/main
        ]

        result = tools.update_grammar("test_lang")

        assert result["status"] == "success"
        assert "already up to date" in result["warnings"][0]

    def test_list_installed_grammars(self, tools, temp_dirs):
        """Test listing installed grammars."""
        build_dir, _ = temp_dirs

        # Create mock .so files
        (build_dir / "lang1.so").touch()
        (build_dir / "lang2.so").touch()

        result = tools.list_installed_grammars()

        assert result["total_grammars"] == 2
        assert "lang1" in result["grammars"]
        assert "lang2" in result["grammars"]

    def test_get_grammar_info(self, tools):
        """Test getting grammar information."""
        result = tools.get_grammar_info("test_lang")

        assert result["language"] == "test_lang"
        assert result["health"] is not None
        assert result["compatibility"] is not None
        assert (
            result["recovery_plan"] is not None
        )  # Should have recovery plan for missing grammar

    def test_check_system_health(self, tools):
        """Test checking system health."""
        result = tools.check_system_health()

        assert "system_requirements" in result
        assert "directory_permissions" in result
        assert "recommendations" in result

        # Check directory permissions
        assert "build directory" in result["directory_permissions"]
        assert "grammars directory" in result["directory_permissions"]


class TestCLICommands:
    """Test CLI command functions."""

    @pytest.fixture()
    def mock_args(self):
        """Create mock command line arguments."""
        args = Mock()
        args.language = "test_lang"
        args.repo_url = "https://github.com/test/repo.git"
        args.branch = "main"
        return args

    @patch("chunker.cli.grammar_commands.get_grammar_tools")
    def test_cmd_list_grammars_success(self, mock_get_tools, mock_args):
        """Test successful grammar listing command."""
        from chunker.cli.grammar_commands import cmd_list_grammars

        # Mock tools
        mock_tools = Mock()
        mock_tools.list_installed_grammars.return_value = {
            "total_grammars": 2,
            "healthy_grammars": 1,
            "problematic_grammars": 1,
            "grammars": {
                "lang1": {"status": "healthy", "issues": [], "recommendations": []},
                "lang2": {
                    "status": "missing",
                    "issues": ["Not found"],
                    "recommendations": ["Install it"],
                },
            },
        }
        mock_get_tools.return_value = mock_tools

        # Mock print to capture output
        with patch("builtins.print") as mock_print:
            result = cmd_list_grammars(mock_args)

            assert result == 0
            assert mock_print.called

    @patch("chunker.cli.grammar_commands.get_grammar_tools")
    def test_cmd_grammar_info_success(self, mock_get_tools, mock_args):
        """Test successful grammar info command."""
        from chunker.cli.grammar_commands import cmd_grammar_info

        # Mock tools
        mock_tools = Mock()
        mock_tools.get_grammar_info.return_value = {
            "language": "test_lang",
            "health": Mock(status="healthy", issues=[], recommendations=[]),
            "compatibility": Mock(
                tree_sitter_version="0.20.8",
                system_architecture="x86_64",
                os_platform="Linux",
                compilation_date="2024-01-15T10:30:00",
                compatibility_score=1.0,
            ),
            "recovery_plan": None,
            "source_info": None,
        }
        mock_get_tools.return_value = mock_tools

        # Mock print to capture output
        with patch("builtins.print") as mock_print:
            result = cmd_grammar_info(mock_args)

            assert result == 0
            assert mock_print.called

    @patch("chunker.cli.grammar_commands.get_grammar_tools")
    def test_cmd_install_grammar_success(self, mock_get_tools, mock_args):
        """Test successful grammar installation command."""
        from chunker.cli.grammar_commands import cmd_install_grammar

        # Mock tools
        mock_tools = Mock()
        mock_tools.install_grammar.return_value = {
            "status": "success",
            "steps_completed": ["Cloned repository", "Generated grammar"],
            "errors": [],
            "warnings": [],
        }
        mock_get_tools.return_value = mock_tools

        # Mock print to capture output
        with patch("builtins.print") as mock_print:
            result = cmd_install_grammar(mock_args)

            assert result == 0
            assert mock_print.called

    @patch("chunker.cli.grammar_commands.get_grammar_tools")
    def test_cmd_install_grammar_failure(self, mock_get_tools, mock_args):
        """Test failed grammar installation command."""
        from chunker.cli.grammar_commands import cmd_install_grammar

        # Mock tools
        mock_tools = Mock()
        mock_tools.install_grammar.return_value = {
            "status": "error",
            "steps_completed": [],
            "errors": ["Git clone failed"],
            "warnings": [],
        }
        mock_get_tools.return_value = mock_tools

        # Mock print to capture output
        with patch("builtins.print") as mock_print:
            result = cmd_install_grammar(mock_args)

            assert result == 1
            assert mock_print.called


if __name__ == "__main__":
    pytest.main([__file__])

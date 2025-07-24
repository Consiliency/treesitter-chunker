"""Unit tests for Development Environment Component"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chunker.devenv import DevelopmentEnvironment, QualityAssurance


class TestDevelopmentEnvironment:
    """Test development environment functionality"""
    
    def test_init_finds_executables(self):
        """Should find executables in PATH"""
        dev_env = DevelopmentEnvironment()
        
        # At least one of these should be found in a dev environment
        assert any([
            dev_env._ruff_path,
            dev_env._black_path,
            dev_env._mypy_path,
            dev_env._pre_commit_path
        ])
    
    def test_setup_pre_commit_hooks_validates_preconditions(self):
        """Should validate all preconditions before setup"""
        dev_env = DevelopmentEnvironment()
        
        # Test with non-existent directory
        result = dev_env.setup_pre_commit_hooks(Path("/nonexistent"))
        assert result is False
        
        # Test with file instead of directory
        with tempfile.NamedTemporaryFile() as tmp:
            result = dev_env.setup_pre_commit_hooks(Path(tmp.name))
            assert result is False
    
    def test_run_linting_default_paths(self):
        """Should default to current directory if no paths specified"""
        dev_env = DevelopmentEnvironment()
        
        with patch.object(dev_env, '_run_ruff') as mock_ruff:
            with patch.object(dev_env, '_run_mypy') as mock_mypy:
                mock_ruff.return_value = []
                mock_mypy.return_value = []
                
                success, issues = dev_env.run_linting()
                
                # Should call with default path
                mock_ruff.assert_called_with(["."], False)
                mock_mypy.assert_called_with(["."])
                
                assert success is True
                assert issues == []
    
    def test_run_linting_combines_issues(self):
        """Should combine issues from multiple tools"""
        dev_env = DevelopmentEnvironment()
        
        ruff_issues = [
            {"tool": "ruff", "file": "test.py", "line": 1, "message": "Issue 1"}
        ]
        mypy_issues = [
            {"tool": "mypy", "file": "test.py", "line": 2, "message": "Issue 2"}
        ]
        
        with patch.object(dev_env, '_run_ruff', return_value=ruff_issues):
            with patch.object(dev_env, '_run_mypy', return_value=mypy_issues):
                success, issues = dev_env.run_linting(["test.py"])
                
                assert success is False
                assert len(issues) == 2
                assert issues[0]["tool"] == "ruff"
                assert issues[1]["tool"] == "mypy"
    
    def test_format_code_check_only(self):
        """Should check formatting without modifying files"""
        dev_env = DevelopmentEnvironment()
        
        with patch.object(dev_env, '_run_ruff_format') as mock_format:
            mock_format.return_value = (False, ["test.py"])
            
            success, files = dev_env.format_code(["test.py"], check_only=True)
            
            mock_format.assert_called_with(["test.py"], True)
            assert success is False
            assert files == ["test.py"]
    
    def test_generate_ci_config_structure(self):
        """Should generate valid CI configuration structure"""
        dev_env = DevelopmentEnvironment()
        
        platforms = ["ubuntu-latest", "windows-latest"]
        versions = ["3.10", "3.11"]
        
        config = dev_env.generate_ci_config(platforms, versions)
        
        # Check structure
        assert "name" in config
        assert "on" in config
        assert "jobs" in config
        
        # Check jobs
        assert "test" in config["jobs"]
        assert "build" in config["jobs"]
        assert "deploy" in config["jobs"]
        
        # Check matrix
        test_job = config["jobs"]["test"]
        assert "strategy" in test_job
        assert "matrix" in test_job["strategy"]
        assert test_job["strategy"]["matrix"]["os"] == platforms
        assert test_job["strategy"]["matrix"]["python-version"] == versions
    
    @patch('subprocess.run')
    def test_run_ruff_json_parsing(self, mock_run):
        """Should parse ruff JSON output correctly"""
        dev_env = DevelopmentEnvironment()
        dev_env._ruff_path = "ruff"
        
        # Mock ruff JSON output
        ruff_output = json.dumps([{
            "filename": "test.py",
            "location": {"row": 10, "column": 5},
            "code": "F401",
            "message": "imported but unused",
            "fix": None
        }])
        
        mock_run.return_value = Mock(
            stdout=ruff_output,
            stderr="",
            returncode=1
        )
        
        issues = dev_env._run_ruff(["test.py"], False)
        
        assert len(issues) == 1
        assert issues[0]["file"] == "test.py"
        assert issues[0]["line"] == 10
        assert issues[0]["column"] == 5
        assert issues[0]["code"] == "F401"
    
    @patch('subprocess.run')
    def test_run_mypy_parsing(self, mock_run):
        """Should parse mypy output correctly"""
        dev_env = DevelopmentEnvironment()
        dev_env._mypy_path = "mypy"
        
        mock_run.return_value = Mock(
            stdout="test.py:5:10: error: Incompatible return value type",
            stderr="",
            returncode=1
        )
        
        issues = dev_env._run_mypy(["test.py"])
        
        assert len(issues) == 1
        assert issues[0]["file"] == "test.py"
        assert issues[0]["line"] == 5
        assert issues[0]["column"] == 10
        assert issues[0]["code"] == "error"


class TestQualityAssurance:
    """Test quality assurance functionality"""
    
    def test_init_finds_executables(self):
        """Should find QA executables in PATH"""
        qa = QualityAssurance()
        
        # At least one should be found
        assert any([
            qa._mypy_path,
            qa._pytest_path,
            qa._coverage_path
        ])
    
    def test_check_type_coverage_no_mypy(self):
        """Should handle missing mypy gracefully"""
        qa = QualityAssurance()
        qa._mypy_path = None
        
        coverage, report = qa.check_type_coverage()
        
        assert coverage == 0.0
        assert "error" in report
        assert "mypy not found" in report["error"]
    
    def test_check_test_coverage_no_pytest(self):
        """Should handle missing pytest gracefully"""
        qa = QualityAssurance()
        qa._pytest_path = None
        
        coverage, report = qa.check_test_coverage()
        
        assert coverage == 0.0
        assert "error" in report
        assert "pytest not found" in report["error"]
    
    def test_parse_mypy_linecount(self):
        """Should parse mypy linecount report correctly"""
        qa = QualityAssurance()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as tmp:
            tmp.write("chunker/main.py 100 80 80%\n")
            tmp.write("chunker/utils.py 50 30 60%\n")
            tmp.write("Total 150 110 73%\n")
            tmp.flush()
            
            data = qa._parse_mypy_linecount(Path(tmp.name))
            
            assert data["total_lines"] == 150
            assert data["typed_lines"] == 110
            assert len(data["files"]) == 2
            assert data["files"]["chunker/main.py"]["coverage"] == 80.0
    
    def test_estimate_type_coverage(self):
        """Should estimate coverage from error count"""
        qa = QualityAssurance()
        
        # No errors = 100% coverage
        output = "Success: no issues found in 1 source file"
        coverage, report = qa._estimate_type_coverage(output)
        assert coverage == 100.0
        
        # Few errors = 80% coverage
        output = "test.py:1: error: Missing type\ntest.py:2: error: Missing type"
        coverage, report = qa._estimate_type_coverage(output)
        assert coverage == 80.0
        assert report["error_count"] == 2
    
    def test_parse_coverage_text(self):
        """Should parse pytest coverage text output"""
        qa = QualityAssurance()
        
        output = """
Name                     Stmts   Miss  Cover
--------------------------------------------
chunker/__init__.py          2      0   100%
chunker/main.py            50     10    80%
chunker/utils.py           30     15    50%
--------------------------------------------
TOTAL                      82     25    70%
"""
        
        coverage, report = qa._parse_coverage_text(output)
        
        assert coverage == 70.0
        assert report["meets_minimum"] is False
        assert len(report["files"]) == 3
        assert report["files"]["chunker/main.py"]["coverage"] == 80.0
    
    @patch('subprocess.run')
    @patch('builtins.open')
    @patch('json.load')
    def test_check_test_coverage_json_parsing(self, mock_json_load, mock_open, mock_run):
        """Should parse coverage.json correctly"""
        qa = QualityAssurance()
        qa._pytest_path = "pytest"
        
        # Mock coverage data
        coverage_data = {
            "totals": {
                "percent_covered": 85.5,
                "covered_lines": 1000,
                "missing_lines": 150,
                "num_statements": 1150
            },
            "files": {
                "chunker/main.py": {
                    "summary": {
                        "percent_covered": 90.0,
                        "covered_lines": 90,
                        "missing_lines": 10
                    },
                    "missing_lines": [15, 20, 25]
                }
            }
        }
        
        mock_run.return_value = Mock(returncode=0)
        mock_json_load.return_value = coverage_data
        
        # Make Path.exists() return True for coverage.json
        with patch('pathlib.Path.exists', return_value=True):
            coverage, report = qa.check_test_coverage()
        
        assert coverage == 85.5
        assert report["meets_minimum"] is True
        assert report["lines_covered"] == 1000
        assert report["files"]["chunker/main.py"]["coverage"] == 90.0
        assert report["uncovered_lines"]["chunker/main.py"] == [15, 20, 25]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
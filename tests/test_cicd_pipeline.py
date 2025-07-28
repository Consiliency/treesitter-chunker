"""Unit tests for CI/CD Pipeline implementation"""

import tempfile
from pathlib import Path

import yaml

from chunker.cicd.pipeline import CICDPipelineImpl


class TestCICDPipelineImpl:
    """Test the CI/CD pipeline implementation"""

    def setup_method(self):
        """Set up test instance"""
        self.pipeline = CICDPipelineImpl()

    def test_validate_workflow_syntax_valid_workflow(self):
        """Test validation of a valid workflow"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            workflow = {
                "name": "Test Workflow",
                "on": ["push", "pull_request"],
                "jobs": {
                    "test": {
                        "runs-on": "ubuntu-latest",
                        "steps": [
                            {"uses": "actions/checkout@v3"},
                            {"run": 'echo "Hello World"'},
                        ],
                    },
                },
            }
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            valid, errors = self.pipeline.validate_workflow_syntax(workflow_path)
            assert valid is True
            assert errors == []
        finally:
            workflow_path.unlink()

    def test_validate_workflow_syntax_missing_required_fields(self):
        """Test validation catches missing required fields"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            # Missing 'name' and 'on'
            workflow = {
                "jobs": {
                    "test": {
                        "runs-on": "ubuntu-latest",
                        "steps": [{"run": "echo test"}],
                    },
                },
            }
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            valid, errors = self.pipeline.validate_workflow_syntax(workflow_path)
            assert valid is False
            assert len(errors) == 2
            assert any("Missing required field: 'name'" in e for e in errors)
            assert any("Missing required field: 'on'" in e for e in errors)
        finally:
            workflow_path.unlink()

    def test_validate_workflow_syntax_invalid_yaml(self):
        """Test validation handles invalid YAML"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("invalid: yaml:\n  - with bad: indentation:\nand syntax")
            workflow_path = Path(f.name)

        try:
            valid, errors = self.pipeline.validate_workflow_syntax(workflow_path)
            assert valid is False
            assert len(errors) == 1
            assert "Invalid YAML syntax" in errors[0]
        finally:
            workflow_path.unlink()

    def test_validate_workflow_syntax_nonexistent_file(self):
        """Test validation handles nonexistent files"""
        workflow_path = Path("/nonexistent/workflow.yml")
        valid, errors = self.pipeline.validate_workflow_syntax(workflow_path)
        assert valid is False
        assert len(errors) == 1
        assert "Workflow file not found" in errors[0]

    def test_validate_workflow_syntax_job_validation(self):
        """Test validation of job structure"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            workflow = {
                "name": "Test",
                "on": "push",
                "jobs": {
                    "bad-job": {
                        # Missing runs-on and steps
                    },
                    "invalid-steps": {
                        "runs-on": "ubuntu-latest",
                        "steps": "not-a-list",  # Should be a list
                    },
                },
            }
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            valid, errors = self.pipeline.validate_workflow_syntax(workflow_path)
            assert valid is False
            assert any("missing 'runs-on'" in e for e in errors)
            assert any("missing 'steps'" in e for e in errors)
            assert any("steps must be a list" in e for e in errors)
        finally:
            workflow_path.unlink()

    def test_run_test_matrix_basic(self):
        """Test running test matrix with basic inputs"""
        python_versions = ["3.8", "3.9", "3.10"]
        platforms = ["ubuntu-latest", "windows-latest"]

        results = self.pipeline.run_test_matrix(python_versions, platforms)

        # Check all combinations are present
        assert len(results) == len(python_versions) * len(platforms)

        # Check structure of results
        for version in python_versions:
            for platform in platforms:
                key = f"python-{version}-{platform}"
                assert key in results
                result = results[key]

                # Check required fields
                assert "status" in result
                assert result["status"] in ["passed", "failed"]
                assert isinstance(result["tests_run"], int)
                assert isinstance(result["tests_passed"], int)
                assert isinstance(result["duration"], float)
                assert isinstance(result["errors"], list)

                # Check test counts make sense
                assert result["tests_passed"] <= result["tests_run"]

    def test_run_test_matrix_windows_python38_failures(self):
        """Test that Windows + Python 3.8 shows expected failures"""
        results = self.pipeline.run_test_matrix(["3.8"], ["windows-latest"])

        key = "python-3.8-windows-latest"
        assert results[key]["status"] == "failed"
        assert results[key]["tests_passed"] < results[key]["tests_run"]
        assert len(results[key]["errors"]) > 0
        assert any("windows" in e.lower() for e in results[key]["errors"])

    def test_build_distribution_basic(self):
        """Test building distribution packages"""
        version = "1.2.3"
        platforms = ["linux", "darwin", "win32"]

        result = self.pipeline.build_distribution(version, platforms)

        # Check structure
        assert "wheels" in result
        assert "sdist" in result
        assert "checksums" in result
        assert "build_logs" in result

        # Check wheels
        assert isinstance(result["wheels"], list)
        assert len(result["wheels"]) == len(platforms)
        for wheel in result["wheels"]:
            assert version in wheel
            assert wheel.endswith(".whl")

        # Check sdist
        assert result["sdist"] is not None
        assert version in result["sdist"]
        assert result["sdist"].endswith(".tar.gz")

        # Check checksums
        assert len(result["checksums"]) == len(platforms) + 1  # wheels + sdist
        for checksum in result["checksums"].values():
            assert isinstance(checksum, str)
            assert len(checksum) == 64  # SHA256 hex length

        # Check build logs
        assert len(result["build_logs"]) == len(platforms)
        for logs in result["build_logs"].values():
            assert isinstance(logs, list)
            assert len(logs) > 0

    def test_build_distribution_creates_files(self):
        """Test that distribution building creates actual files"""
        version = "0.1.0"
        platforms = ["linux"]

        result = self.pipeline.build_distribution(version, platforms)

        # Check that files were created
        dist_dir = Path("dist")
        assert dist_dir.exists()

        # Check wheel exists
        for wheel_path in result["wheels"]:
            assert Path(wheel_path).exists()

        # Check sdist exists
        assert Path(result["sdist"]).exists()

    def test_create_release_success(self):
        """Test successful release creation"""
        version = "1.0.0"

        # Create dummy artifacts
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = []
            for name in ["package-1.0.0.whl", "package-1.0.0.tar.gz"]:
                artifact = Path(tmpdir) / name
                artifact.write_text("dummy content")
                artifacts.append(artifact)

            changelog = "## New Features\n- Initial release"

            result = self.pipeline.create_release(version, artifacts, changelog)

            # Check result structure
            assert result["status"] == "published"
            assert result["tag"] == "v1.0.0"
            assert "github.com" in result["release_url"]
            assert len(result["uploaded_artifacts"]) == 2
            assert all(a.name in result["uploaded_artifacts"] for a in artifacts)

    def test_create_release_invalid_version(self):
        """Test release creation with invalid version"""
        result = self.pipeline.create_release("", [], "changelog")

        assert result["status"] == "failed"
        assert result["release_url"] == ""
        assert result["tag"] == ""
        assert result["uploaded_artifacts"] == []

    def test_create_release_missing_artifacts(self):
        """Test release creation with missing artifacts"""
        version = "1.0.0"
        artifacts = [Path("/nonexistent/file.whl")]

        result = self.pipeline.create_release(version, artifacts, "changelog")

        assert result["status"] == "failed"
        assert result["uploaded_artifacts"] == []

    def test_create_release_version_formatting(self):
        """Test version tag formatting"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy artifact
            artifact = Path(tmpdir) / "dummy.whl"
            artifact.write_text("dummy")
            artifacts = [artifact]

            # Test without 'v' prefix
            result = self.pipeline.create_release("2.0.0", artifacts, "changelog")
            assert result["tag"] == "v2.0.0"

            # Test with 'v' prefix
            result = self.pipeline.create_release("v3.0.0", artifacts, "changelog")
            assert result["tag"] == "v3.0.0"

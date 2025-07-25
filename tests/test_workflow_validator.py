"""Tests for workflow validation utilities"""

import tempfile
from pathlib import Path

import yaml

from chunker.cicd.workflow_validator import WorkflowValidator, validate_all_workflows


class TestWorkflowValidator:
    """Test the workflow validator"""

    def setup_method(self):
        """Set up test instance"""
        self.validator = WorkflowValidator()

    def test_validate_valid_workflow(self):
        """Test validation of a complete valid workflow"""
        workflow = {
            "name": "CI",
            "on": ["push", "pull_request"],
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v3"},
                        {"name": "Run tests", "run": "pytest"},
                    ],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True
            assert len(errors) == 0
            # May have warning about action version
        finally:
            workflow_path.unlink()

    def test_validate_complex_workflow(self):
        """Test validation of complex workflow with matrix"""
        workflow = {
            "name": "Build",
            "on": {
                "push": {"branches": ["main", "develop"], "tags": ["v*"]},
                "pull_request": {"types": ["opened", "synchronize"]},
            },
            "env": {"PYTHON_VERSION": "3.10"},
            "jobs": {
                "test": {
                    "runs-on": "${{ matrix.os }}",
                    "strategy": {
                        "matrix": {
                            "os": ["ubuntu-latest", "windows-latest"],
                            "python": ["3.8", "3.9", "3.10"],
                        },
                    },
                    "steps": [
                        {"uses": "actions/checkout@v3"},
                        {
                            "uses": "actions/setup-python@v4",
                            "with": {"python-version": "${{ matrix.python }}"},
                        },
                        {"run": "python -m pytest"},
                    ],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True
            assert len(errors) == 0
        finally:
            workflow_path.unlink()

    def test_validate_missing_name(self):
        """Test validation catches missing name"""
        workflow = {
            "on": "push",
            "jobs": {
                "test": {"runs-on": "ubuntu-latest", "steps": [{"run": "echo test"}]},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is False
            assert any("Missing required field: 'name'" in e for e in errors)
        finally:
            workflow_path.unlink()

    def test_validate_invalid_job_id(self):
        """Test validation catches invalid job IDs"""
        workflow = {
            "name": "Test",
            "on": "push",
            "jobs": {
                "123-invalid": {  # Job IDs can't start with number
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo test"}],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is False
            assert any("Invalid job ID" in e for e in errors)
        finally:
            workflow_path.unlink()

    def test_validate_unknown_runner(self):
        """Test validation warns about unknown runners"""
        workflow = {
            "name": "Test",
            "on": "push",
            "jobs": {
                "test": {"runs-on": "custom-runner", "steps": [{"run": "echo test"}]},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True  # Unknown runner is a warning, not error
            assert any("unknown runner" in w for w in warnings)
        finally:
            workflow_path.unlink()

    def test_validate_self_hosted_runner(self):
        """Test validation accepts self-hosted runners"""
        workflow = {
            "name": "Test",
            "on": "push",
            "jobs": {
                "test": {"runs-on": "self-hosted", "steps": [{"run": "echo test"}]},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True
            assert not any("unknown runner" in w for w in warnings)
        finally:
            workflow_path.unlink()

    def test_validate_schedule_cron(self):
        """Test validation of schedule with cron"""
        workflow = {
            "name": "Scheduled",
            "on": {"schedule": [{"cron": "0 0 * * *"}]},  # Daily at midnight
            "jobs": {
                "nightly": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": 'echo "Nightly build"'}],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True
            assert len(errors) == 0
        finally:
            workflow_path.unlink()

    def test_validate_permissions(self):
        """Test validation of permissions"""
        workflow = {
            "name": "Deploy",
            "on": "push",
            "permissions": {
                "contents": "read",
                "packages": "write",
                "invalid-scope": "read",  # Should warn
            },
            "jobs": {
                "deploy": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo deploy"}],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True
            assert any("Unknown permission scope" in w for w in warnings)
        finally:
            workflow_path.unlink()

    def test_validate_action_without_version(self):
        """Test validation warns about actions without versions"""
        workflow = {
            "name": "Test",
            "on": "push",
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout"},  # No version
                        {"uses": "actions/setup-python@v4"},  # Has version
                    ],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True
            assert any("should specify action version" in w for w in warnings)
        finally:
            workflow_path.unlink()

    def test_validate_step_with_both_uses_and_run(self):
        """Test validation warns about steps with both uses and run"""
        workflow = {
            "name": "Test",
            "on": "push",
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v3", "run": 'echo "This is wrong"'},
                    ],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(workflow, f)
            workflow_path = Path(f.name)

        try:
            is_valid, errors, warnings = self.validator.validate_file(workflow_path)
            assert is_valid is True  # This is a warning, not error
            assert any("has both 'uses' and 'run'" in w for w in warnings)
        finally:
            workflow_path.unlink()


class TestValidateAllWorkflows:
    """Test the validate_all_workflows function"""

    def test_validate_directory(self):
        """Test validating all workflows in a directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflows_dir = Path(tmpdir) / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)

            # Create valid workflow
            valid_workflow = {
                "name": "Valid",
                "on": "push",
                "jobs": {
                    "test": {
                        "runs-on": "ubuntu-latest",
                        "steps": [{"run": "echo valid"}],
                    },
                },
            }
            with open(workflows_dir / "valid.yml", "w") as f:
                yaml.dump(valid_workflow, f)

            # Create invalid workflow
            invalid_workflow = {
                "name": "Invalid",
                # Missing 'on'
                "jobs": {
                    "test": {
                        # Missing 'runs-on'
                        "steps": [{"run": "echo invalid"}],
                    },
                },
            }
            with open(workflows_dir / "invalid.yaml", "w") as f:
                yaml.dump(invalid_workflow, f)

            # Validate all
            results = validate_all_workflows(workflows_dir)

            assert "valid.yml" in results
            assert "invalid.yaml" in results

            # Check valid workflow
            valid_is_valid, valid_errors, valid_warnings = results["valid.yml"]
            assert valid_is_valid is True
            assert len(valid_errors) == 0

            # Check invalid workflow
            invalid_is_valid, invalid_errors, invalid_warnings = results["invalid.yaml"]
            assert invalid_is_valid is False
            assert len(invalid_errors) > 0

    def test_validate_nonexistent_directory(self):
        """Test validating nonexistent directory returns empty results"""
        results = validate_all_workflows(Path("/nonexistent/workflows"))
        assert results == {}

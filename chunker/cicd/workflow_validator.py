"""GitHub Actions workflow validation utilities

This module provides additional utilities for validating and analyzing
GitHub Actions workflow files.
"""

import re
from pathlib import Path
from typing import ClassVar

import yaml


class WorkflowValidator:
    """Validates GitHub Actions workflow files"""

    # Common GitHub-hosted runners
    VALID_RUNNERS: ClassVar[set[str]] = {
        "ubuntu-latest",
        "ubuntu-22.04",
        "ubuntu-20.04",
        "windows-latest",
        "windows-2022",
        "windows-2019",
        "macos-latest",
        "macos-13",
        "macos-12",
        "macos-11",
    }

    # Valid events
    VALID_EVENTS: ClassVar[set[str]] = {
        "push",
        "pull_request",
        "workflow_dispatch",
        "schedule",
        "release",
        "issues",
        "issue_comment",
        "pull_request_review",
        "pull_request_review_comment",
        "workflow_call",
        "workflow_run",
        "repository_dispatch",
        "page_build",
        "project",
        "project_card",
        "project_column",
        "public",
        "watch",
        "fork",
        "create",
        "delete",
    }

    # Common actions
    COMMON_ACTIONS: ClassVar[set[str]] = {
        "actions/checkout",
        "actions/setup-python",
        "actions/setup-node",
        "actions/upload-artifact",
        "actions/download-artifact",
        "actions/cache",
        "actions/github-script",
    }

    def __init__(self):
        """Initialize the workflow validator"""
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def validate_file(self, workflow_path: Path) -> tuple[bool, list[str], list[str]]:
        """Validate a workflow file

        Args:
            workflow_path: Path to workflow file

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.warnings = []
        self.errors = []

        try:
            with workflow_path.open() as f:
                workflow = yaml.safe_load(f)

            if not isinstance(workflow, dict):
                self.errors.append("Workflow must be a YAML dictionary")
                return False, self.errors, self.warnings

            # Validate each section
            self._validate_name(workflow)
            self._validate_triggers(workflow)
            self._validate_env(workflow)
            self._validate_jobs(workflow)
            self._validate_permissions(workflow)

            return len(self.errors) == 0, self.errors, self.warnings

        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error: {e!s}")
            return False, self.errors, self.warnings
        except (OSError, ValueError) as e:
            self.errors.append(f"Validation error: {e!s}")
            return False, self.errors, self.warnings

    def _validate_name(self, workflow: dict):
        """Validate workflow name"""
        if "name" not in workflow:
            self.errors.append("Missing required field: 'name'")
        elif not isinstance(workflow["name"], str):
            self.errors.append("'name' must be a string")
        elif len(workflow["name"]) > 255:
            self.warnings.append("Workflow name is very long (>255 characters)")

    def _validate_triggers(self, workflow: dict):
        """Validate workflow triggers"""
        if "on" not in workflow:
            self.errors.append("Missing required field: 'on'")
            return

        triggers = workflow["on"]

        # Handle string trigger
        if isinstance(triggers, str) and triggers not in self.VALID_EVENTS:
            self.warnings.append(f"Unknown event trigger: {triggers}")
            return

        # Handle list of triggers
        if isinstance(triggers, list):
            for trigger in triggers:
                if trigger not in self.VALID_EVENTS:
                    self.warnings.append(f"Unknown event trigger: {trigger}")
            return

        # Handle dict of triggers with config
        if isinstance(triggers, dict):
            for event, config in triggers.items():
                if event not in self.VALID_EVENTS:
                    self.warnings.append(f"Unknown event trigger: {event}")

                # Validate common configurations
                if event == "push" and isinstance(config, dict):
                    self._validate_push_config(config)
                elif event == "pull_request" and isinstance(config, dict):
                    self._validate_pr_config(config)
                elif event == "schedule" and isinstance(config, list):
                    self._validate_schedule_config(config)

    def _validate_push_config(self, config: dict):
        """Validate push event configuration"""
        if "branches" in config:
            branches = config["branches"]
            if not isinstance(branches, list):
                self.errors.append("Push 'branches' must be a list")
            else:
                for branch in branches:
                    if not isinstance(branch, str):
                        self.errors.append("Branch patterns must be strings")

        if "tags" in config:
            tags = config["tags"]
            if not isinstance(tags, list):
                self.errors.append("Push 'tags' must be a list")

    def _validate_pr_config(self, config: dict):
        """Validate pull_request event configuration"""
        if "types" in config:
            types = config["types"]
            if not isinstance(types, list):
                self.errors.append("Pull request 'types' must be a list")
            else:
                valid_types = {
                    "opened",
                    "closed",
                    "reopened",
                    "synchronize",
                    "assigned",
                    "unassigned",
                    "labeled",
                    "unlabeled",
                    "review_requested",
                    "review_request_removed",
                    "ready_for_review",
                    "converted_to_draft",
                }
                for pr_type in types:
                    if pr_type not in valid_types:
                        self.warnings.append(f"Unknown PR type: {pr_type}")

    def _validate_schedule_config(self, schedules: list):
        """Validate schedule configuration"""
        for schedule in schedules:
            if not isinstance(schedule, dict) or "cron" not in schedule:
                self.errors.append("Schedule must have 'cron' field")
            else:
                cron = schedule["cron"]
                if not self._is_valid_cron(cron):
                    self.errors.append(f"Invalid cron expression: {cron}")

    def _is_valid_cron(self, cron: str) -> bool:
        """Check if cron expression is valid (basic validation)"""
        # Basic cron validation - 5 fields
        parts = cron.split()
        if len(parts) != 5:
            return False

        # Very basic validation - just check format
        return all(part for part in parts)

    def _validate_env(self, workflow: dict):
        """Validate environment variables"""
        if "env" in workflow:
            env = workflow["env"]
            if not isinstance(env, dict):
                self.errors.append("'env' must be a dictionary")
            else:
                for key in env:
                    if not isinstance(key, str):
                        self.errors.append("Environment variable names must be strings")
                    elif not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                        self.warnings.append(f"Non-standard env var name: {key}")

    def _validate_jobs(self, workflow: dict):
        """Validate jobs section"""
        if "jobs" not in workflow:
            self.errors.append("Missing required field: 'jobs'")
            return

        jobs = workflow["jobs"]
        if not isinstance(jobs, dict):
            self.errors.append("'jobs' must be a dictionary")
            return

        if not jobs:
            self.errors.append("Workflow must have at least one job")
            return

        for job_id, job in jobs.items():
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", job_id):
                self.errors.append(f"Invalid job ID: {job_id}")

            if not isinstance(job, dict):
                self.errors.append(f"Job '{job_id}' must be a dictionary")
                continue

            self._validate_job(job_id, job)

    def _validate_job(self, job_id: str, job: dict):
        """Validate individual job"""
        # Check required fields
        if "runs-on" not in job:
            self.errors.append(f"Job '{job_id}' missing required field: 'runs-on'")
        else:
            runner = job["runs-on"]
            if isinstance(runner, str):
                if runner not in self.VALID_RUNNERS and not runner.startswith(
                    "self-hosted",
                ):
                    self.warnings.append(
                        f"Job '{job_id}' uses unknown runner: {runner}",
                    )
            elif isinstance(runner, dict):
                # Matrix expression
                pass
            else:
                self.errors.append(
                    f"Job '{job_id}' 'runs-on' must be string or expression",
                )

        # Validate steps
        if "steps" not in job:
            self.errors.append(f"Job '{job_id}' missing required field: 'steps'")
        else:
            steps = job["steps"]
            if not isinstance(steps, list):
                self.errors.append(f"Job '{job_id}' steps must be a list")
            elif not steps:
                self.errors.append(f"Job '{job_id}' must have at least one step")
            else:
                for i, step in enumerate(steps):
                    self._validate_step(job_id, i, step)

        # Validate other job fields
        if "needs" in job:
            needs = job["needs"]
            if isinstance(needs, str):
                needs = [needs]
            elif not isinstance(needs, list):
                self.errors.append(f"Job '{job_id}' 'needs' must be string or list")

        if "strategy" in job:
            self._validate_strategy(job_id, job["strategy"])

    def _validate_step(self, job_id: str, step_index: int, step: dict):
        """Validate individual step"""
        if not isinstance(step, dict):
            self.errors.append(f"Job '{job_id}' step {step_index} must be a dictionary")
            return

        step_name = step.get("name", f"step {step_index}")

        # Each step needs either 'uses' or 'run'
        if "uses" not in step and "run" not in step:
            self.errors.append(f"Job '{job_id}' {step_name} must have 'uses' or 'run'")

        if "uses" in step and "run" in step:
            self.warnings.append(
                f"Job '{job_id}' {step_name} has both 'uses' and 'run'",
            )

        # Validate 'uses'
        if "uses" in step:
            action = step["uses"]
            if not isinstance(action, str):
                self.errors.append(
                    f"Job '{job_id}' {step_name} 'uses' must be a string",
                )
            else:
                # Check if it's a known action
                base_action = action.split("@")[0]
                if base_action in self.COMMON_ACTIONS and "@" not in action:
                    self.warnings.append(
                        f"Job '{job_id}' {step_name} should specify action version",
                    )

        # Validate 'with' parameters
        if "with" in step and not isinstance(step["with"], dict):
            self.errors.append(
                f"Job '{job_id}' {step_name} 'with' must be a dictionary",
            )

    def _validate_strategy(self, job_id: str, strategy: dict):
        """Validate job strategy"""
        if not isinstance(strategy, dict):
            self.errors.append(f"Job '{job_id}' strategy must be a dictionary")
            return

        if "matrix" in strategy:
            matrix = strategy["matrix"]
            if not isinstance(matrix, dict):
                self.errors.append(f"Job '{job_id}' matrix must be a dictionary")
            else:
                # Check for at least one dimension
                dimensions = [k for k in matrix if k not in ["include", "exclude"]]
                if not dimensions:
                    self.errors.append(
                        f"Job '{job_id}' matrix must define at least one dimension",
                    )

    def _validate_permissions(self, workflow: dict):
        """Validate permissions section"""
        if "permissions" in workflow:
            perms = workflow["permissions"]
            valid_scopes = {
                "actions",
                "checks",
                "contents",
                "deployments",
                "id-token",
                "issues",
                "packages",
                "pages",
                "pull-requests",
                "repository-projects",
                "security-events",
                "statuses",
            }

            if isinstance(perms, str) and perms not in ["read-all", "write-all"]:
                self.errors.append(f"Invalid permission level: {perms}")
            elif isinstance(perms, dict):
                for scope, level in perms.items():
                    if scope not in valid_scopes:
                        self.warnings.append(f"Unknown permission scope: {scope}")
                    if level not in ["read", "write", "none"]:
                        self.errors.append(
                            f"Invalid permission level for {scope}: {level}",
                        )


def validate_all_workflows(
    workflows_dir: Path,
) -> dict[str, tuple[bool, list[str], list[str]]]:
    """Validate all workflows in a directory

    Args:
        workflows_dir: Path to .github/workflows directory

    Returns:
        Dict mapping workflow names to validation results
    """
    validator = WorkflowValidator()
    results = {}

    if not workflows_dir.exists():
        return results

    for workflow_file in workflows_dir.glob("*.yml"):
        is_valid, errors, warnings = validator.validate_file(workflow_file)
        results[workflow_file.name] = (is_valid, errors, warnings)

    for workflow_file in workflows_dir.glob("*.yaml"):
        is_valid, errors, warnings = validator.validate_file(workflow_file)
        results[workflow_file.name] = (is_valid, errors, warnings)

    return results

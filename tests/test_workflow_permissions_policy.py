"""Least-privilege GitHub Actions permissions (treesitter-chunker#507).

Every workflow and every job declares ``permissions:`` explicitly, so the
repository's default token permission never decides what a job may do. Write
scopes are granted only to the publishing jobs listed in ``WRITE_GRANTS``.
This keeps the workflows correct when the repository default becomes
read-only (IF-0-CIFAST-2; the setting itself is changed only by the owner).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
# GitHub runs both extensions; a .yaml workflow must not escape the policy.
WORKFLOWS = sorted([*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")])

# (workflow, job, scope) -> the step that needs the write.
WRITE_GRANTS = {
    ("baml-grammar-wheels.yml", "publish", "id-token"): "pypa/gh-action-pypi-publish",
    ("docs.yml", "deploy", "contents"): "peaceiris/actions-gh-pages",
    ("release.yml", "create-release", "contents"): "softprops/action-gh-release",
    ("release.yml", "publish-to-pypi", "id-token"): "pypa/gh-action-pypi-publish",
}
ALLOWED_LEVELS = {"read", "write", "none"}

# Steps an ``id-token: write`` publishing job may contain: artifact download,
# the PyPI publisher, and the release job's checksum check. Any other ``run``
# step would execute with the OIDC token available.
OIDC_ACTIONS = {"actions/download-artifact", "pypa/gh-action-pypi-publish"}
OIDC_RUN_STEPS = {
    "cd dist\nsha256sum --check checksums.txt\nrm checksums.txt\n",
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _actions(job: dict) -> set[str]:
    return {
        step["uses"].split("@", 1)[0]
        for step in job.get("steps", [])
        if isinstance(step, dict) and "uses" in step
    }


def _scopes(permissions: object, where: str) -> dict[str, str]:
    # ``{}`` grants nothing; a bare ``read-all``/``write-all`` string is never
    # least privilege, so only mappings are accepted.
    assert isinstance(permissions, dict), f"{where}: permissions must be a mapping"
    for scope, level in permissions.items():
        assert level in ALLOWED_LEVELS, f"{where}: {scope}={level!r}"
    return permissions


def test_workflows_exist() -> None:
    assert WORKFLOWS


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_and_jobs_declare_least_privilege(path: Path) -> None:
    workflow = _load(path)
    assert "permissions" in workflow, f"{path.name}: no workflow permissions"
    top = _scopes(workflow["permissions"], path.name)
    assert "write" not in top.values(), f"{path.name}: workflow-level write"

    for name, job in workflow["jobs"].items():
        where = f"{path.name}:{name}"
        assert "uses" not in job, f"{where}: reusable workflows need a review"
        assert "permissions" in job, f"{where}: no job permissions"
        for scope, level in _scopes(job["permissions"], where).items():
            if level != "write":
                continue
            action = WRITE_GRANTS.get((path.name, name, scope))
            assert action, f"{where}: unlisted {scope}: write"
            assert action in _actions(job), f"{where}: {action} not used"


def test_every_write_grant_is_still_needed() -> None:
    granted = {
        (path.name, name, scope)
        for path in WORKFLOWS
        for name, job in _load(path)["jobs"].items()
        for scope, level in (job.get("permissions") or {}).items()
        if level == "write"
    }
    assert granted == set(WRITE_GRANTS)


def test_oidc_publishing_runs_only_behind_an_environment() -> None:
    for path in WORKFLOWS:
        for name, job in _load(path)["jobs"].items():
            if (job.get("permissions") or {}).get("id-token") != "write":
                continue
            where = f"{path.name}:{name}"
            assert job.get("environment"), where
            for step in job["steps"]:
                if "uses" in step:
                    assert step["uses"].split("@", 1)[0] in OIDC_ACTIONS, (
                        where,
                        step,
                    )
                else:
                    assert step.get("run") in OIDC_RUN_STEPS, (where, step)


def test_docs_build_never_holds_a_write_token() -> None:
    """Pull-request docs builds install the checkout; only deploy may write.

    The build job never gets ``contents: write`` back, even as a rollback
    (treesitter-chunker#507): the deploy job is fixed forward instead.
    """
    jobs = _load(ROOT / ".github/workflows/docs.yml")["jobs"]
    assert jobs["docs"]["permissions"] == {"contents": "read"}
    deploy = jobs["deploy"]
    assert deploy["needs"] == "docs"
    assert deploy["if"] == (
        "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    )
    assert not any(
        "run" in step for step in deploy["steps"] if isinstance(step, dict)
    ), "deploy must not run repository code"
    checkouts = [
        step
        for step in deploy["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]
    # The write token must not persist into the deploy job's git config.
    assert checkouts
    assert all(
        (step.get("with") or {}).get("persist-credentials") is False
        for step in checkouts
    )

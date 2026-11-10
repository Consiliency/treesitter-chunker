"""Routing, aggregate-result and workflow topology contracts for #647."""

from __future__ import annotations

import ast
import copy
import importlib.util
import py_compile
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


changes = load_script("ci_changes")
gate = load_script("ci_gate")
POLICIES = {
    "test_release_hygiene_policy.py",
    "test_workflow_permissions_policy.py",
    "test_lint_path_policy.py",
    "test_type_gate_policy.py",
    "test_scratch_root_policy.py",
    "test_hygiene_reachability.py",
    "test_repo_hygiene.py",
    "test_ci_scope_policy.py",
}


def workflow(name="ci.yml"):
    return yaml.safe_load(
        (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "path",
    [
        "chunker/x.py",
        "cli/a",
        "tests/a",
        "spec_tests/a",
        "scripts/a",
        "tools/a",
        "grammars/a",
        "packages/a",
        "examples/a",
        "api/a",
        "config/a",
        "templates/a",
        "generated/a",
        "artifacts/a",
        "benchmarks/a",
        "packaging/a",
        "conda/a",
        "homebrew/a",
        ".github/workflows/ci.yml",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        "requirements-build.txt",
        "MANIFEST.in",
        "Dockerfile.dev",
        ".chunkerrc.json",
        ".pre-commit-config.yaml",
        "treesitter-chunker.rb",
        "new/thing.md",
        ".hidden",
        "CHANGELOG.md",
        "docs/sphinx/index.rst",
        "docs/language-coverage.json",
        "docs/development/mypy-baseline.txt",
        "docs/interface-boundary-spec.md",
        "plans/hygiene-reachability-audit.txt",
        "specs/schema.json",
        "docs/config.py",
        "scripts/ci_changes.py",
        "scripts/ci_gate.py",
        "DOCS/index.md",
        "docs/a.MD",
    ],
)
def test_code_paths(path):
    assert changes.classify([("M", path)])["code"] == "true"
    assert changes.classify([("M", path)])["docs"] == "true"


@pytest.mark.parametrize(
    ("path", "docs"),
    [
        ("README.md", True),
        ("CONTRIBUTING.md", True),
        ("CODE_REVIEW_X.md", True),
        ("mkdocs.yml", True),
        ("docs/index.md", True),
        ("docs/deep/a.rst", True),
        ("docs/a.txt", True),
        ("docs/a.png", True),
        ("docs/a.jpg", True),
        ("docs/a.jpeg", True),
        ("docs/a.svg", True),
        ("docs/a.gif", True),
        ("docs/a.webp", True),
        ("docs/a.css", True),
        ("plans/a.md", False),
        ("specs/nested/a.md", False),
        ("docs/你好 a\nb.md", True),
    ],
)
def test_light_paths(path, docs):
    result = changes.classify([("M", path)])
    assert result["code"] == "false"
    assert result["docs"] == str(docs).lower()
    assert result["policy"] == "true"


def test_deleted_inputs_and_union():
    for path in changes.BUILD_INPUT_ROOT_FILES:
        assert changes.classify([("D", path)])["code"] == "true"
    assert changes.classify([])["docs"] == "false"
    assert changes.classify([("M", "docs/a.md"), ("M", "plans/a.md")])["docs"] == "true"
    assert (
        changes.classify([("D", "chunker/x.py"), ("A", "docs/x.md")])["code"] == "true"
    )
    assert (
        changes.classify([("M", f"docs/{i}.md") for i in range(401)])["code"] == "false"
    )
    assert (
        changes.classify(
            [("M", f"docs/{i}.md") for i in range(401)] + [("M", "unknown/x")]
        )["code"]
        == "true"
    )


def test_build_input_inventory():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    names = set()
    for field in ("readme", "license"):
        value = project.get(field)
        if isinstance(value, dict):
            value = value.get("file")
        if isinstance(value, str) and (ROOT / value).is_file():
            names.add(value)
    for pattern in project.get("license-files", []):
        names.update(
            p.name for p in ROOT.glob(pattern) if p.is_file() and p.parent == ROOT
        )
    for line in (ROOT / "MANIFEST.in").read_text().splitlines():
        if line.startswith("include "):
            for pattern in line.split()[1:]:
                if "/" not in pattern:
                    names.update(p.name for p in ROOT.glob(pattern) if p.is_file())
    assert names <= changes.BUILD_INPUT_ROOT_FILES


@pytest.mark.parametrize(
    "raw", [b"M\0a", b"M\0", b"R100\0a\0b\0", b"M\0\xff\0", b"M\0../a\0", b"M\0/a\0"]
)
def test_malformed_diff(raw):
    with pytest.raises((ValueError, UnicodeError)):
        changes.parse_diff(raw)


def test_nul_diff():
    assert changes.parse_diff("D\0README.md\0A\0docs/é\nx.md\0".encode()) == [
        ("D", "README.md"),
        ("A", "docs/é\nx.md"),
    ]


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


def test_real_pr_graph_and_force_push(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.test")
    git(repo, "config", "user.name", "fixture")

    def commit(path, text):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")
        return git(repo, "rev-parse", "HEAD")

    base = commit("README.md", "base")
    git(repo, "switch", "-c", "parent")
    parent = commit("chunker/x.py", "code")
    git(repo, "switch", "-c", "child")
    head = commit("docs/index.md", "docs")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(changes, "repo_url", lambda _repo: str(repo))
    event = {
        "repository": {"default_branch": "main"},
        "pull_request": {
            "base": {"sha": parent, "ref": "parent", "repo": {}},
            "head": {"sha": head, "repo": {}},
        },
    }
    assert changes.detect("pull_request", event)["code"] == "true"
    # Retargeting must preserve classification even without an edited-event run.
    event["pull_request"]["base"].update(sha=base, ref="main")
    assert changes.detect("pull_request", event)["code"] == "true"
    git(repo, "switch", "-c", "control", base)
    control = commit("docs/index.md", "control")
    event["pull_request"]["head"]["sha"] = control
    event["before"] = head  # never use old head / last push
    routed = changes.detect("pull_request", event)
    assert (routed["code"], routed["docs"]) == ("false", "true")
    event["repository"]["default_branch"] = "unreachable"
    with pytest.raises(subprocess.CalledProcessError):
        changes.detect("pull_request", event)
    event["pull_request"]["head"]["sha"] = "bad"
    with pytest.raises(ValueError):
        changes.detect("pull_request", event)


def test_non_default_base_diff_joins_the_union(tmp_path, monkeypatch):
    """A1 step 2: code that reaches the head only through newer main counts.

    The head merged a main that gained code after its non-default base
    branched. Against the main tip the PR is docs-only; against its own base
    it carries that code, so the union must route to code.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.test")
    git(repo, "config", "user.name", "fixture")

    def commit(path, text):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")
        return git(repo, "rev-parse", "HEAD")

    commit("README.md", "base")
    git(repo, "switch", "-c", "older")
    older = commit("docs/older.md", "older docs")
    git(repo, "switch", "main")
    commit("chunker/x.py", "code on main")
    git(repo, "switch", "-c", "child", "older")
    git(repo, "merge", "--no-edit", "main")
    head = commit("docs/index.md", "docs")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(changes, "repo_url", lambda _repo: str(repo))
    event = {
        "repository": {"default_branch": "main"},
        "pull_request": {
            "base": {"sha": older, "ref": "older", "repo": {}},
            "head": {"sha": head, "repo": {}},
        },
    }
    assert changes.detect("pull_request", event)["code"] == "true"


@pytest.mark.parametrize(
    ("event", "full"),
    [
        ("schedule", "true"),
        ("workflow_dispatch", "true"),
        ("merge_group", "false"),
        ("push", "false"),
    ],
)
def test_full_events(event, full):
    result = changes.detect(event, {})
    assert result == {
        "schema": "1",
        "code": "true",
        "docs": "true",
        "policy": "true",
        "full": full,
    }


def needs(code="true", docs="true", full="false"):
    data = {job: {"result": "success"} for job in gate.JOBS}
    data["changes"]["outputs"] = {
        "schema": "1",
        "code": code,
        "docs": docs,
        "policy": "true",
        "full": full,
    }
    return data


@pytest.mark.parametrize("phase", ["A", "C"])
@pytest.mark.parametrize("job", sorted(gate.JOBS))
@pytest.mark.parametrize("result", ["failure", "cancelled", "unknown", "", None])
def test_gate_rejects_nonpassing_results(phase, job, result):
    data = needs()
    data[job]["result"] = result
    assert not gate.evaluate(data, "pull_request", phase)[0]


def test_gate_skip_contract_and_mutations():
    data = needs("false", "false")
    for job in ("test", "platform", "controlled-linux", "docs"):
        data[job]["result"] = "skipped"
    assert gate.evaluate(data, "pull_request", "C")[0]
    assert not gate.evaluate(data, "pull_request", "A")[0]
    for job in ("policy", "changes"):
        bad = copy.deepcopy(data)
        bad[job]["result"] = "skipped"
        assert not gate.evaluate(bad, "pull_request", "C")[0]
    # Docs-only: heavy lanes may skip, but the required docs lane may not.
    docs_only = needs("false", "true")
    for job in ("test", "platform", "controlled-linux"):
        docs_only[job]["result"] = "skipped"
    assert gate.evaluate(docs_only, "pull_request", "C")[0]
    assert not gate.evaluate(docs_only, "pull_request", "A")[0]
    bad = copy.deepcopy(docs_only)
    bad["docs"]["result"] = "skipped"
    assert not gate.evaluate(bad, "pull_request", "C")[0]
    # Merge-queue runs need every lane; push runs no longer exist in phase C.
    assert gate.evaluate(needs(), "merge_group", "C")[0]
    assert not gate.evaluate(docs_only, "merge_group", "C")[0]
    assert gate.evaluate(needs(), "push", "A")[0]
    assert not gate.evaluate(needs(), "push", "C")[0]
    for flag in ("schema", "policy", "code", "docs", "full"):
        bad = needs()
        del bad["changes"]["outputs"][flag]
        assert not gate.evaluate(bad, "pull_request", "A")[0]
    for job in gate.JOBS:
        bad = needs()
        del bad[job]
        assert not gate.evaluate(bad, "pull_request", "A")[0]
    assert not gate.evaluate(needs("true", "false"), "pull_request", "C")[0]
    assert not gate.evaluate(needs(full="true"), "pull_request", "C")[0]
    assert not gate.evaluate(needs(), "workflow_dispatch", "A")[0]
    assert gate.evaluate(needs(full="true"), "workflow_dispatch", "A")[0]
    for job in ("test", "platform", "controlled-linux", "docs"):
        bad = needs()
        bad[job]["result"] = "skipped"
        assert not gate.evaluate(bad, "pull_request", "C")[0]
    # Even an unneeded job that actually ran and failed must reject.
    data["platform"]["result"] = "failure"
    assert not gate.evaluate(data, "pull_request", "C")[0]


def assert_topology(ci):
    jobs = ci["jobs"]
    phase = jobs["ci-gate"]["steps"][-1]["env"]["CI_PHASE"]
    assert phase in {"A", "C"}
    triggers = ci.get("on", ci.get(True))
    assert set(triggers["pull_request"]) == {"types"}
    assert triggers["pull_request"]["types"] == [
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
    ]
    assert "merge_group" in triggers and "workflow_dispatch" in triggers
    assert triggers["schedule"] == [{"cron": "17 3 * * *"}]
    assert ("push" in triggers) == (phase == "A")
    assert set(jobs["ci-gate"]["needs"]) == gate.JOBS
    assert jobs["ci-gate"]["if"] == "${{ always() }}"
    assert jobs["ci-gate"]["name"] == "CI gate"
    gate_step = jobs["ci-gate"]["steps"][-1]
    assert gate_step["env"]["NEEDS_JSON"] == "${{ toJSON(needs) }}"
    assert gate_step["run"] == "python scripts/ci_gate.py"
    for job in ("changes", "ci-gate"):
        setup = [
            s
            for s in jobs[job]["steps"]
            if s.get("uses", "").startswith("actions/setup-python@")
        ]
        assert len(setup) == 1 and str(setup[0]["with"]["python-version"]) == "3.14"
    for job, flag in [
        ("test", "code"),
        ("platform", "code"),
        ("controlled-linux", "code"),
        ("docs", "docs"),
    ]:
        assert jobs[job]["needs"] == "changes"
        if phase == "A":
            assert "if" not in jobs[job]
        else:
            assert (
                jobs[job]["if"] == "${{ needs.changes.outputs." + flag + " == 'true' }}"
            )
        assert not jobs[job].get("continue-on-error")
    assert jobs["policy"]["needs"] == "changes"
    policy = jobs["policy"]["steps"][-1]["run"]
    assert {
        s.removeprefix("tests/") for s in policy.split() if s.startswith("tests/")
    } == POLICIES
    assert "-n" not in policy
    assert not any(
        "prefetch" in str(s) or "build_lib" in str(s) for s in jobs["policy"]["steps"]
    )
    platform = jobs["platform"]
    assert platform["strategy"]["fail-fast"] is False
    assert "max-parallel" not in platform["strategy"]
    assert (
        platform["name"]
        == "test (${{ matrix.python-version }}, ${{ matrix.platform }}, ${{ matrix.platform-family }})"
    )
    assert {
        m["platform-family"]: m["pr-timeout"]
        for m in platform["strategy"]["matrix"]["include"]
    } == {"linux": 90, "macos": 45, "windows": 45}
    assert "120" in platform["timeout-minutes"]
    assert "90 || 25" in jobs["test"]["timeout-minutes"]
    for job in jobs.values():
        assert "timeout-minutes" in job
        for step in job.get("steps", []):
            if "timeout-minutes" in step:
                assert isinstance(job["timeout-minutes"], int)
                assert step["timeout-minutes"] <= job["timeout-minutes"]
    for job in jobs.values():
        for step in job.get("steps", []):
            if "matrix." in str(step.get("if", "")):
                assert step.get("name") == "Full suite on primary Python"
    assert ci["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}-${{ github.event_name }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }
    full = next(
        s for s in platform["steps"] if s.get("name") == "Full suite on primary Python"
    )
    assert (
        full["if"]
        == "needs.changes.outputs.full == 'true' && matrix.platform-family != 'linux'"
    )
    assert full["run"].endswith("scripts/run_full_suite.py")


def test_topology_and_mutations():
    ci = workflow()
    assert_topology(ci)
    bad = copy.deepcopy(ci)
    bad["jobs"]["ci-gate"]["needs"].remove("platform")
    with pytest.raises(AssertionError):
        assert_topology(bad)
    bad = copy.deepcopy(ci)
    bad["jobs"]["test"]["if"] = "${{ needs.changes.outputs.code }}"
    with pytest.raises(AssertionError):
        assert_topology(bad)


def test_no_duplicate_pr_contexts():
    contexts = []
    for path in (ROOT / ".github/workflows").glob("*.y*ml"):
        data = yaml.safe_load(path.read_text())
        if "pull_request" not in data.get("on", data.get(True, {})):
            continue
        for name, job in data["jobs"].items():
            if "matrix" in job.get("strategy", {}):
                matrix = job["strategy"]["matrix"]
                if name == "platform":
                    contexts.extend(
                        f"test ({m['python-version']}, {m['platform']}, {m['platform-family']})"
                        for m in matrix["include"]
                    )
                continue
            contexts.append(job.get("name", name))
    for name in (
        "test",
        "docs",
        "controlled-linux",
        "test (3.12, ubuntu-latest, linux)",
        "CI gate",
    ):
        assert contexts.count(name) == 1
    assert not (ROOT / ".github/workflows/test.yml").exists()
    assert "pull_request" not in workflow("docs.yml").get(True, {})


def test_cache_recipe_and_event_scope():
    warm = workflow("language-pack-cache.yml")
    triggers = warm.get("on", warm.get(True))
    assert triggers["push"]["paths"] == [
        "uv.lock",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        ".github/workflows/language-pack-cache.yml",
    ]
    steps = warm["jobs"]["warm"]["steps"]
    source = workflow()["jobs"]["platform"]["steps"]
    for name in (
        "Check language pack cache path",
        "Restore language pack",
        "Prefetch language pack",
        "Save language pack",
        "Verify exact language pack hit offline",
    ):
        assert next(s for s in steps if s.get("name") == name) == next(
            s for s in source if s.get("name") == name
        )
    assert not any(
        token in str(steps)
        for token in (
            "pytest",
            "build_lib.py",
            "fetch_grammars.py",
            "run_platform_core.py",
        )
    )
    assert warm["concurrency"]["cancel-in-progress"] is False


def test_scripts_compile_and_gate_env_only(tmp_path):
    for name in ("ci_changes", "ci_gate"):
        py_compile.compile(
            str(ROOT / "scripts" / f"{name}.py"),
            cfile=str(tmp_path / f"{name}.pyc"),
            doraise=True,
        )
        ast.parse(
            (ROOT / "scripts" / f"{name}.py").read_text(), feature_version=(3, 12)
        )
    source = (ROOT / "scripts/ci_gate.py").read_text()
    assert 'os.environ["NEEDS_JSON"]' in source
    assert "sys.argv" not in source and "argparse" not in source
    assert '"auto"' not in (ROOT / "scripts/run_ci_smoke.py").read_text()

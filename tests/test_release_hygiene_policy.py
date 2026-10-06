"""Release hygiene policy checks for warnings and tracked skip markers."""

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
DOCS = ROOT / "docs"
MKDOCS_CONFIG = ROOT / "mkdocs.yml"
POLICY_TEST = Path(__file__).name
XFAIL_INVENTORY = DOCS / "development/xfail-inventory.md"
FALLBACK_TEST_FILES = [
    TESTS / "test_auto.py",
    TESTS / "test_fallback_chunking.py",
    TESTS / "test_overlapping_fallback.py",
]
PUBLIC_BOUNDARY_DOCS = {
    "agent-interface-readiness.md",
    "interface-boundary-roadmap.md",
    "interface-boundary-spec.md",
    "grammar_management.md",
}
INTERNAL_DOCS = {
    "development/DEPLOYMENT.md",
    "development/RELEASE_CHECKLIST.md",
    "development/backlog-inventory-20261006.md",
    "development/native-validation-contract.md",
    "development/safeload-verification.md",
}
UNTRACKED_INTERNAL_DOCS = {
    "development/xfail-inventory.md",
    "language-coverage.md",
    # RELEASE traceability matrix — maintainer/internal, like xfail-inventory.
    "development/traceability-matrix.md",
}


def _test_sources() -> list[Path]:
    return [
        path
        for path in TESTS.rglob("test_*.py")
        if path.name != POLICY_TEST and "__pycache__" not in path.parts
    ]


def _mkdocs_config() -> dict:
    return yaml.safe_load(MKDOCS_CONFIG.read_text(encoding="utf-8"))


def _collect_nav_paths(items: list) -> set[str]:
    paths: set[str] = set()
    for item in items:
        if isinstance(item, str):
            paths.add(item)
            continue
        if isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    paths.add(value)
                elif isinstance(value, list):
                    paths.update(_collect_nav_paths(value))
    return paths


def test_xfail_markers_are_capped_and_tracked():
    """Every xfail must appear in the capped inventory with a clearing phase."""
    inventory = XFAIL_INVENTORY.read_text(encoding="utf-8")
    cap_match = re.search(r"^Maximum active xfails: (\d+)$", inventory, re.MULTILINE)
    assert cap_match is not None
    cap = int(cap_match.group(1))
    inventory_entries = [
        line for line in inventory.splitlines() if line.startswith("| tests/")
    ]
    assert len(inventory_entries) <= cap

    markers = []
    for path in _test_sources():
        text = path.read_text(encoding="utf-8")
        if "pytest.xfail(" in text:
            markers.append(f"{path.relative_to(ROOT)}: pytest.xfail")
        for test_name in re.findall(
            r"@pytest\.mark\.xfail\([\s\S]*?\n\s*def (test_\w+)", text
        ):
            markers.append(f"{path.relative_to(ROOT)}::{test_name}")

    assert len(markers) <= cap
    for marker in markers:
        assert any(marker in entry for entry in inventory_entries)


def test_conftest_has_no_collection_time_policy_mutation():
    """Keep xfail/skip and fallback-warning policy local to tests."""
    text = (TESTS / "conftest.py").read_text(encoding="utf-8")

    assert "pytest_collection_modifyitems" not in text
    assert "FallbackWarning" not in text
    assert "filterwarnings" not in text


def test_no_global_fallback_warning_filter():
    """Expected fallback warnings should be asserted where they are triggered."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "filterwarnings" not in text
    assert "FallbackWarning" not in text


def test_fallback_warning_tests_use_scoped_assertions():
    """Fallback-warning tests should assert local warning contracts."""
    for path in FALLBACK_TEST_FILES:
        text = path.read_text(encoding="utf-8")
        assert "warnings.catch_warnings(record=True)" not in text
        assert "pytest.warns" in text
        assert "FallbackWarning" in text


def test_mkdocs_tracks_every_phase7_doc_explicitly():
    """Public docs belong in nav; internal docs belong in exact not_in_nav entries."""
    config = _mkdocs_config()
    nav_paths = _collect_nav_paths(config["nav"])
    configured_not_in_nav = {
        line.strip().lstrip("/")
        for line in config["not_in_nav"].splitlines()
        if line.strip()
    }
    doc_paths = {
        path.relative_to(DOCS).as_posix()
        for path in DOCS.rglob("*.md")
        if path.is_file()
    }

    not_in_nav = {path for path in configured_not_in_nav if (DOCS / path).is_file()}
    assert "*" not in config["not_in_nav"]
    assert not_in_nav == INTERNAL_DOCS
    assert doc_paths == nav_paths | not_in_nav | UNTRACKED_INTERNAL_DOCS
    assert nav_paths >= PUBLIC_BOUNDARY_DOCS


def test_public_boundary_docs_are_linked_from_docs_index():
    """The landing page should expose the public Boundary IR entry points."""
    text = (DOCS / "index.md").read_text(encoding="utf-8")

    for path in sorted(PUBLIC_BOUNDARY_DOCS):
        assert f"({path})" in text


def test_internal_phase7_docs_keep_maintainer_notices():
    """Internal docs omitted from nav should declare that status near the top."""
    for path in INTERNAL_DOCS | {"development/xfail-inventory.md"}:
        lines = (DOCS / path).read_text(encoding="utf-8").splitlines()[:6]
        joined = "\n".join(lines)
        assert "Maintainer/internal documentation." in joined
        assert "intentionally omitted from" in joined


def test_publication_requires_full_validation_and_verified_artifacts():
    """A release cannot bypass failed source checks or missing build artifacts."""
    jobs = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())["jobs"]
    validation = jobs["release-validation"]
    assert not validation.get("continue-on-error", False)
    assert validation["strategy"]["matrix"]["python-version"] == [
        "3.11",
        "3.12",
        "3.13",
    ]
    assert any(
        "scripts/run_full_suite.py" in step.get("run", "")
        for step in validation["steps"]
    )
    assert all(not step.get("continue-on-error", False) for step in validation["steps"])
    build = jobs["build-distributions"]
    assert build["needs"] == "release-validation"
    uploads = [
        s for s in build["steps"] if "actions/upload-artifact@" in s.get("uses", "")
    ]
    assert "dist/checksums.txt" in uploads[0]["with"]["path"].splitlines()
    wheel_check = jobs["verify-installed-wheel"]
    assert wheel_check["needs"] == "build-distributions"
    assert wheel_check["strategy"]["matrix"]["python-version"] == ["3.12", "3.14"]
    assert any(
        "--only-binary=:all:" in step.get("run", "")
        and "--require-hashes" in step.get("run", "")
        for step in wheel_check["steps"]
    )
    assert "update-changelog" not in jobs
    for name in ("create-release", "publish-to-pypi"):
        job = jobs[name]
        assert job["needs"] == ["build-distributions", "verify-installed-wheel"]
        assert not job.get("continue-on-error", False)
        assert all(not s.get("continue-on-error", False) for s in job["steps"])
    for name in ("create-release", "publish-to-pypi"):
        steps = jobs[name]["steps"]
        verify = next(
            i for i, s in enumerate(steps) if "sha256sum --check" in s.get("run", "")
        )
        publish = next(
            i
            for i, s in enumerate(steps)
            if any(
                action in s.get("uses", "")
                for action in ("action-gh-release@", "gh-action-pypi-publish@")
            )
        )
        assert verify < publish


def test_native_distribution_stays_suspended():
    """Neither a tag nor manual dispatch may publish unvalidated native assets."""
    workflow = yaml.safe_load((ROOT / ".github/workflows/packages.yml").read_text())
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"native-packages-suspended"}
    job = workflow["jobs"]["native-packages-suspended"]
    assert "permissions" not in job
    assert not job.get("continue-on-error")
    assert len(job["steps"]) == 1
    step = job["steps"][0]
    assert set(step) == {"name", "run"}
    commands = step["run"].splitlines()
    assert len(commands) == 2
    assert commands[0].startswith('echo "::error::')
    assert "distribution is suspended for v5" in commands[0]
    assert commands[1] == "exit 1"

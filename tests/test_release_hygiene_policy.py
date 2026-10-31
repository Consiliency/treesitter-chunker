"""Release hygiene policy checks for warnings and tracked skip markers."""

import re
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest
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
    "development/backlog-decisions-v4.md",
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


def _python_floor() -> tuple[int, int]:
    """Return the supported floor from pyproject ``requires-python``."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    match = re.fullmatch(r">=\s*3\.(\d+)", pyproject["project"]["requires-python"])
    assert match, "requires-python must be a simple '>=3.X' floor"
    return (3, int(match.group(1)))


def _version(text: str) -> tuple[int, int]:
    major, minor = text.split(".")[:2]
    return (int(major), int(minor))


def _floor_text() -> str:
    return "{}.{}".format(*_python_floor())


def test_python_floor_declarations_agree():
    """Project, tool, interpreter-pin and CI declarations share the floor."""
    floor = _floor_text()
    nodot = floor.replace(".", "")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["ruff"]["target-version"] == f"py{nodot}"
    assert pyproject["tool"]["black"]["target-version"] == [f"py{nodot}"]
    assert pyproject["tool"]["mypy"]["python_version"] == floor
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == floor
    jobs = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())["jobs"]
    wheel_check = jobs["verify-installed-wheel"]
    assert wheel_check["env"]["UV_PYTHON"] == "${{ matrix.python-version }}"


def test_pyproject_classifiers_respect_python_floor():
    """No Python version classifier advertises an interpreter below the floor."""
    floor = _python_floor()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    versions = [
        _version(match.group(1))
        for classifier in pyproject["project"]["classifiers"]
        if (
            match := re.fullmatch(
                r"Programming Language :: Python :: (3\.\d+)", classifier
            )
        )
    ]
    assert versions, "expected explicit Python version classifiers"
    assert min(versions) == floor
    assert all(version >= floor for version in versions)


def test_conda_recipe_respects_python_floor():
    """The conda recipe's build, host and run Python pins match the floor."""
    text = (ROOT / "conda/meta.yaml").read_text(encoding="utf-8")
    pins = re.findall(r"^\s*-\s*python\s*>=\s*(\d+\.\d+)\s*$", text, re.MULTILINE)
    assert len(pins) == 3, pins
    assert set(pins) == {_floor_text()}


@pytest.mark.parametrize(
    "formula",
    [
        "homebrew/treesitter-chunker.rb",
        "packaging/homebrew/treesitter-chunker.rb",
        "treesitter-chunker.rb",
    ],
)
def test_homebrew_formulas_respect_python_floor(formula):
    """Every Homebrew formula depends on, and installs into, the floor Python."""
    floor = _floor_text()
    text = (ROOT / formula).read_text(encoding="utf-8")
    depends = re.findall(r'depends_on\s+"python@(\d+\.\d+)"', text)
    assert depends == [floor]
    site_packages = re.findall(r"python(\d+\.\d+)/site-packages", text)
    assert set(site_packages) <= {floor}


def test_wheel_builder_requires_python_matches_floor():
    """The builder's shared Requires-Python constant feeds both wheel paths."""
    from chunker.build import builder

    assert f">={_floor_text()}" == builder._WHEEL_REQUIRES_PYTHON
    source = (ROOT / "chunker/build/builder.py").read_text(encoding="utf-8")
    assert source.count("Requires-Python: {_WHEEL_REQUIRES_PYTHON}") == 2
    assert not re.search(r"Requires-Python:\s*>=", source)


def _build_wheel_metadata(tmp_path, monkeypatch) -> str:
    from chunker.build.builder import BuildSystem

    system = BuildSystem()
    monkeypatch.setattr(
        system.platform_support,
        "detect_platform",
        lambda: {"platform_tag": "linux_x86_64"},
    )
    monkeypatch.setattr(system, "_get_available_languages", lambda: ["python"])
    monkeypatch.setattr(system, "compile_grammars", lambda *_args: (True, {}))
    success, wheel_path = system.build_wheel("linux", "cp312", tmp_path)
    assert success, "wheel build failed"
    with zipfile.ZipFile(wheel_path) as wheel:
        [metadata] = [n for n in wheel.namelist() if n.endswith(".dist-info/METADATA")]
        return wheel.read(metadata).decode("utf-8")


def test_wheel_builder_zip_fallback_writes_requires_python(tmp_path, monkeypatch):
    """Without the ``wheel`` package the ZIP fallback still declares the floor."""
    monkeypatch.setitem(sys.modules, "wheel.metadata", None)
    metadata = _build_wheel_metadata(tmp_path, monkeypatch)
    assert f"Requires-Python: >={_floor_text()}" in metadata.splitlines()


def test_wheel_builder_wheel_path_writes_requires_python(tmp_path, monkeypatch):
    """The ``wheel``-library path declares the floor in METADATA."""
    pytest.importorskip("wheel.metadata")
    pytest.importorskip("wheel.wheelfile")
    metadata = _build_wheel_metadata(tmp_path, monkeypatch)
    assert f"Requires-Python: >={_floor_text()}" in metadata.splitlines()


def test_macos_build_script_rejects_python_below_floor():
    """The macOS build script's version guard uses the floor tuple."""
    major, minor = _python_floor()
    text = (ROOT / "scripts/build_macos.sh").read_text(encoding="utf-8")
    tuples = re.findall(r"sys\.version_info\s*<\s*\((\d+),\s*(\d+)\)", text)
    assert tuples == [(str(major), str(minor))]
    assert f"Python {major}.{minor} or higher" in text


def _workflow_jobs():
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (workflow.get("jobs") or {}).items():
            yield path.name, name, workflow.get("env") or {}, job


def _matrix_values(job: dict, key: str) -> list[str]:
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    values = [str(value) for value in matrix.get(key) or []]
    values += [str(item[key]) for item in matrix.get("include") or [] if key in item]
    return values


def _setup_python_versions(job: dict) -> list[str]:
    return [
        str((step.get("with") or {}).get("python-version"))
        for step in job.get("steps") or []
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    ]


def _resolve(job: dict, value: str) -> list[str]:
    expression = re.fullmatch(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}", value)
    return _matrix_values(job, expression.group(1)) if expression else [value]


def test_workflow_setup_python_versions_respect_floor():
    """Every setup-python version, including matrix values, is at least the floor."""
    floor = _python_floor()
    checked = 0
    for workflow, name, _env, job in _workflow_jobs():
        for value in _setup_python_versions(job):
            resolved = _resolve(job, value)
            assert resolved, f"{workflow}:{name} has no values for {value}"
            for version in resolved:
                assert re.fullmatch(r"\d+\.\d+", version), (workflow, name, version)
                assert _version(version) >= floor, (workflow, name, version)
                checked += 1
    assert checked


def test_workflow_uv_jobs_pin_uv_python_to_job_interpreter():
    """uv jobs on matrix or non-floor Python must override the .python-version pin."""
    floor = _floor_text()
    uv_command = re.compile(r"(^|[\s;&|(])uvx?\s+(run|sync|pip|export|build|tool)\b")
    for workflow, name, workflow_env, job in _workflow_jobs():
        steps = job.get("steps") or []
        uv_steps = [s for s in steps if uv_command.search(str(s.get("run", "")))]
        if not uv_steps:
            continue
        for value in _setup_python_versions(job):
            if set(_resolve(job, value)) == {floor}:
                continue
            for step in uv_steps:
                env = {
                    **workflow_env,
                    **(job.get("env") or {}),
                    **(step.get("env") or {}),
                }
                uv_python = str(env.get("UV_PYTHON"))
                assert uv_python == value or (
                    len(set(_resolve(job, value))) == 1
                    and _resolve(job, value) == _resolve(job, uv_python)
                ), f"{workflow}:{name} runs uv on Python {value} without UV_PYTHON"


_OLD_PYTHON = re.compile(
    r"(?i)(python[\s@-]*(>=\s*)?|>=\s*|requires-python\D*)3\.(8|9|10|11)(?!\d)"
)
_HISTORICAL = re.compile(r"6\.0\.0|0\.1\.0|[Pp]ublished|[\w-]+#\d+")


def test_docs_do_not_advertise_python_below_floor():
    """Docs paragraphs naming an old Python must be about a published release."""
    offenders = []
    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for paragraph in re.split(r"\n\s*\n", text):
            if _OLD_PYTHON.search(paragraph) and not _HISTORICAL.search(paragraph):
                offenders.append(f"{path.relative_to(ROOT)}: {paragraph.strip()[:120]}")
    assert not offenders, "\n".join(offenders)


def test_publication_requires_full_validation_and_verified_artifacts():
    """A release cannot bypass failed source checks or missing build artifacts."""
    jobs = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())["jobs"]
    validation = jobs["release-validation"]
    assert not validation.get("continue-on-error", False)
    assert validation["strategy"]["matrix"]["python-version"] == ["3.12"]
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

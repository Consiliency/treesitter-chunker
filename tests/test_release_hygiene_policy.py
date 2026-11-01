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
    "development/cache-transaction-contract.md",
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
    monkeypatch.setitem(sys.modules, "wheel.wheelfile", None)
    metadata = _build_wheel_metadata(tmp_path, monkeypatch)
    assert f"Requires-Python: >={_floor_text()}" in metadata.splitlines()


def test_wheel_builder_wheel_path_writes_requires_python(tmp_path, monkeypatch):
    """The ``wheel``-library path declares the floor in METADATA."""
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


def _workflow_paths() -> list[Path]:
    """Workflow files GitHub runs: both .yml and .yaml."""
    directory = ROOT / ".github/workflows"
    return sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")])


def _workflow_docs() -> dict[str, dict]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in _workflow_paths()
    }


def _workflow_texts() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in _workflow_paths()}


def _workflow_jobs(docs: dict[str, dict] | None = None):
    for name_, workflow in (docs if docs is not None else _workflow_docs()).items():
        for name, job in (workflow.get("jobs") or {}).items():
            yield name_, name, workflow.get("env") or {}, job


def _matrix_values(job: dict, key: str) -> list[str]:
    """Values of a literal matrix key; a computed matrix fails the calling test."""
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    assert isinstance(matrix, dict), f"computed matrix is not allowed: {matrix!r}"
    values = matrix.get(key) or []
    include = matrix.get("include") or []
    assert isinstance(values, list), f"computed matrix {key} is not allowed: {values!r}"
    assert isinstance(include, list) and all(
        isinstance(item, dict) for item in include
    ), f"computed matrix include is not allowed: {include!r}"
    return [str(value) for value in values] + [
        str(item[key]) for item in include if key in item
    ]


def _setup_python_versions(job: dict) -> list[str]:
    return [
        str((step.get("with") or {}).get("python-version"))
        for step in job.get("steps") or []
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    ]


_EVENT_CHOICE = re.compile(
    r"\$\{\{\s*github\.event_name\s*==\s*'([\w-]+)'\s*&&\s*'([^']+)'"
    r"\s*\|\|\s*'([^']+)'\s*\}\}"
)


def _event_choice(value: str) -> tuple[str, str, str] | None:
    """Parse ``${{ github.event_name == 'E' && 'A' || 'B' }}`` as (E, A, B)."""
    match = _EVENT_CHOICE.fullmatch(value)
    return match.groups() if match else None


def _resolve(job: dict, value: str) -> list[str]:
    expression = re.fullmatch(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}", value)
    if expression:
        return _matrix_values(job, expression.group(1))
    choice = _event_choice(value)
    return list(choice[1:]) if choice else [value]


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


# treesitter-chunker#502, maintainer decision (2026-11-01): 3.14 is the main
# version for every CI and release run, including the scheduled full tier. The
# 3.12 minimum (requires-python, .python-version) keeps only Linux platform-core
# and the release installed-wheel check until 7.0 drops it
# (treesitter-chunker#599).
PRIMARY_PYTHON = "3.14"

# Where the floor interpreter may appear: (workflow, job, platform family or
# None) -> reason.
FLOOR_ALLOWED = {
    ("test.yml", "test", "linux"): "focused minimum: Linux platform-core",
    ("release.yml", "verify-installed-wheel", None): "installed-wheel floor check",
    # The BAML companion is a separate package whose minimum is also 3.12. These
    # jobs check, build and smoke-test it on that minimum. Its cp312-abi3 floor
    # comes from packages/baml-grammar/setup.py and CIBW_BUILD, asserted below.
    ("baml-grammar-wheels.yml", "source", None): "BAML companion on its 3.12 minimum",
    ("baml-grammar-wheels.yml", "wheel", None): "BAML companion on its 3.12 minimum",
}


def _workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text("utf-8"))


def _interpreter_fields(workflow_env: dict, job: dict) -> list[str]:
    """Every setup-python version and UV_PYTHON value that applies to a job."""
    values = _setup_python_versions(job)
    for env in (workflow_env, job.get("env") or {}):
        if "UV_PYTHON" in env:
            values.append(str(env["UV_PYTHON"]))
    for step in job.get("steps") or []:
        if "UV_PYTHON" in (step.get("env") or {}):
            values.append(str(step["env"]["UV_PYTHON"]))
    return values


def _floor_uses(
    docs: dict[str, dict] | None = None,
) -> set[tuple[str, str, str | None]]:
    floor = _floor_text()
    uses = set()
    for workflow, name, workflow_env, job in _workflow_jobs(docs):
        for value in _interpreter_fields(workflow_env, job):
            if floor not in _resolve(job, value):
                continue
            include = ((job.get("strategy") or {}).get("matrix") or {}).get("include")
            if (
                value == "${{ matrix.python-version }}"
                and include
                and all("platform-family" in item for item in include)
            ):
                uses |= {
                    (workflow, name, item["platform-family"])
                    for item in include
                    if str(item.get("python-version")) == floor
                }
            else:
                uses.add((workflow, name, None))
    return uses


def test_no_workflow_selects_its_interpreter_by_event():
    """No event-conditional interpreter, such as 3.12-when-scheduled."""
    offenders = [
        (workflow, name, value)
        for workflow, name, workflow_env, job in _workflow_jobs()
        for value in _interpreter_fields(workflow_env, job)
        if "github.event_name" in value or _event_choice(value)
    ]
    assert offenders == []


def test_floor_interpreter_appears_only_in_floor_checks():
    """3.12 runs only Linux platform-core, the installed-wheel check and BAML."""
    assert _floor_uses() == set(FLOOR_ALLOWED)


# Plain-text interpreter scan (maintainer decision, 2026-11-01): flag broadly,
# exempt narrowly. Every line of every workflow file (.yml and .yaml) is
# scanned as text, including comments, echo output and heredoc bodies, with no
# shell parsing. Lines are attributed to jobs from the parsed YAML node
# positions. Outside a FLOOR_ALLOWED job (or, for a family-scoped entry,
# outside that family's literal matrix include entry), any mention of
# switching the Python version fails. The only exemption is a canonical 3.14
# setting at the start of a line (`python-version:` or `UV_PYTHON:` set to 3.14,
# a literal list of only 3.14, or `${{ matrix.python-version }}` over a literal
# matrix whose non-3.14 values are all allowed floor entries). The rest of
# that line, comments included, is still scanned.
_TEXT_RULES = (
    ("--python", re.compile(r"--python")),
    ("python3.N", re.compile(r"python3\.\d+")),
    ("Python3NN path", re.compile(r"[Pp]ython3\d\d\b")),
    ("python@3", re.compile(r"(?<![\w-])python@\d")),
    ("py -3.N", re.compile(r"\bpy(?:\.exe)?[ \t]+-(?:V:)?\d")),
    ("uv python pin|install|find", re.compile(r"\bpython[ \t]+(?:pin|install|find)\b")),
    ("PYENV_VERSION", re.compile(r"PYENV_VERSION")),
    ("UV_PYTHON", re.compile(r"(?i)uv_python")),
    ("python-version", re.compile(r"(?<![.\w-])python-version")),
)
# A short-option cluster containing p (-p, -qp, -p3.12, "-p"), starting after
# a line start, whitespace, a quote, '=' or '('.
_SHORT_P = re.compile(r"""(?:(?<=^)|(?<=[\s"'=(]))-([A-Za-z]*p[A-Za-z]*)""")
_CANONICAL_SETTING = re.compile(
    r"""^\s*(?:-\s+)?(?P<key>python-version|UV_PYTHON):[ \t]*"""
    r"""(?P<value>'3\.14'|"3\.14"|3\.14(?![\w.])|\[\s*['"]?3\.14['"]?\s*\]|"""
    r"""\$\{\{\s*matrix\.python-version\s*\}\})"""
)
_TEXT_FIX = (
    "Each line above mentions switching the Python version outside the 3.12 floor "
    "jobs. To fix it, either (a) reword the text (comments and echo output count) "
    "so it no longer names --python, -p, UV_PYTHON, PYENV_VERSION, python3.N, "
    "python@3, Python3NN, py -3.N, uv python pin|install|find or a non-3.14 "
    "python-version, or (b) if the job is a deliberate 3.12 floor check, add "
    "(workflow, job, platform family or None) to FLOOR_ALLOWED in "
    "tests/test_release_hygiene_policy.py with a reason."
)


def _short_p_excluded(line: str, match: re.Match) -> bool:
    """The three named exclusions: pytest -p no:, mkdir -p, tar -cpf."""
    cluster, before, after = match.group(1), line[: match.start()], line[match.end() :]
    command = re.split(r"[;&|]", before)[-1]
    if (
        cluster == "p"
        and re.match(r"[ =]?no:", after)
        and re.search(r"\bpytest\b", command)
    ):
        return True
    if cluster == "p" and re.search(r"\bmkdir\b", command):
        return True
    return cluster == "cpf" and bool(re.search(r"\btar\b", command))


def _scan_text(line: str) -> list[str]:
    hits = [name for name, pattern in _TEXT_RULES if pattern.search(line)]
    hits += [
        "-p" for match in _SHORT_P.finditer(line) if not _short_p_excluded(line, match)
    ]
    return hits


def _literal_matrix_versions(job: dict) -> list[tuple[str, str | None]] | None:
    """(python-version, platform-family) pairs from a literal matrix, else None."""
    matrix = (job.get("strategy") or {}).get("matrix")
    if not isinstance(matrix, dict):
        return None
    pairs: list[tuple[str, str | None]] = []
    top = matrix.get("python-version", [])
    if not isinstance(top, list):
        return None
    pairs += [(str(value), None) for value in top]
    include = matrix.get("include", [])
    if not isinstance(include, list) or not all(isinstance(i, dict) for i in include):
        return None
    pairs += [
        (str(item["python-version"]), item.get("platform-family"))
        for item in include
        if "python-version" in item
    ]
    if not pairs or any("${{" in value for value, _family in pairs):
        return None
    return pairs


def _job_spans(
    text: str,
) -> tuple[dict[str, tuple[int, int]], dict[str, list[tuple[int, int, str]]]]:
    """Line spans (0-based, end exclusive) of each job and its matrix include
    entries, from the composed YAML nodes."""

    def span(start, end) -> tuple[int, int]:
        return start.line, end.line + (1 if end.column else 0)

    root = yaml.compose(text)
    jobs: dict[str, tuple[int, int]] = {}
    includes: dict[str, list[tuple[int, int, str]]] = {}
    if root is None:
        return jobs, includes
    for key, value in root.value:
        if key.value != "jobs" or not isinstance(value, yaml.MappingNode):
            continue
        for job_key, job_node in value.value:
            jobs[job_key.value] = span(job_key.start_mark, job_node.end_mark)
            entries = []
            node = job_node
            for part in ("strategy", "matrix", "include"):
                found = (
                    [v for k, v in node.value if k.value == part]
                    if isinstance(node, yaml.MappingNode)
                    else []
                )
                node = found[0] if found else None
                if node is None:
                    break
            if isinstance(node, yaml.SequenceNode):
                for item in node.value:
                    if isinstance(item, yaml.MappingNode):
                        family = [
                            v.value
                            for k, v in item.value
                            if k.value == "platform-family"
                        ]
                        if family:
                            entries.append(
                                (*span(item.start_mark, item.end_mark), family[0])
                            )
            includes[job_key.value] = entries
    return jobs, includes


def _yaml_anchor_lines(text: str) -> list[int]:
    """1-based lines of YAML anchors or aliases (rejected in workflows)."""
    return sorted(
        {
            event.start_mark.line + 1
            for event in yaml.parse(text)
            if isinstance(event, yaml.AliasEvent)
            or (getattr(event, "anchor", None) is not None)
        }
    )


def _text_offenders(texts: dict[str, str] | None = None) -> list[str]:
    offenders = []
    for workflow, text in (texts if texts is not None else _workflow_texts()).items():
        lines = text.splitlines()
        try:
            yaml.compose(text)
        except yaml.YAMLError as error:
            offenders.append(f"{workflow}: unparseable workflow YAML: {error}")
            continue
        for number in _yaml_anchor_lines(text):
            offenders.append(
                f"{workflow}:{number} YAML anchor/alias: {lines[number - 1].strip()}"
            )
        parsed_jobs = (yaml.safe_load(text) or {}).get("jobs") or {}
        spans, includes = _job_spans(text)
        if set(spans) != set(parsed_jobs):
            offenders.append(
                f"{workflow}: job names from the text {sorted(spans)} differ from "
                f"the parsed jobs {sorted(parsed_jobs)}"
            )
        owner: list[str | None] = [None] * len(lines)
        exempt = [False] * len(lines)
        for job, (start, end) in spans.items():
            for index in range(start, min(end, len(lines))):
                owner[index] = job
            if (workflow, job, None) in FLOOR_ALLOWED:
                for index in range(start, min(end, len(lines))):
                    exempt[index] = True
            for entry_start, entry_end, family in includes.get(job, []):
                if (workflow, job, family) in FLOOR_ALLOWED:
                    for index in range(entry_start, min(entry_end, len(lines))):
                        exempt[index] = True
        for index, line in enumerate(lines):
            if exempt[index]:
                continue
            job = owner[index]
            rest, hits = line, []
            canonical = _CANONICAL_SETTING.match(line)
            if canonical:
                accepted = True
                if "matrix.python-version" in canonical.group("value"):
                    pairs = _literal_matrix_versions(parsed_jobs.get(job) or {})
                    accepted = pairs is not None and all(
                        version == PRIMARY_PYTHON
                        or (workflow, job, family) in FLOOR_ALLOWED
                        for version, family in pairs
                    )
                    if not accepted:
                        hits.append("computed or non-3.14 matrix python-version")
                if accepted:
                    rest = line[canonical.end() :]
            hits += _scan_text(rest)
            offenders += [
                f"{workflow}:{index + 1} [{job or '<workflow>'}] {hit}: {line.strip()}"
                for hit in hits
            ]
    return offenders


def _assert_no_text_offenders(texts: dict[str, str] | None = None) -> None:
    offenders = _text_offenders(texts)
    assert not offenders, "\n".join([*offenders, "", _TEXT_FIX])


def test_workflow_text_mentions_no_interpreter_switch_outside_floor_jobs():
    _assert_no_text_offenders()


def test_text_job_attribution_matches_parsed_jobs():
    """Every parsed job, quoted keys included, owns a non-empty span of lines."""
    for workflow, text in _workflow_texts().items():
        spans, _includes = _job_spans(text)
        parsed = (yaml.safe_load(text) or {}).get("jobs") or {}
        assert set(spans) == set(parsed), workflow
        assert all(end > start for start, end in spans.values()), workflow


def test_workflows_use_no_yaml_anchors_or_aliases():
    for workflow, text in _workflow_texts().items():
        assert _yaml_anchor_lines(text) == [], workflow


# Mutation tests. Each edits workflow text in memory and must be rejected with
# the fix message, attributed to the mutated workflow.
_CI_PYTEST = '          if [ "$GITHUB_EVENT_NAME" = "schedule" ]; then\n'


def _insert_ci(inserted: str):
    return ("ci.yml", _CI_PYTEST, inserted + _CI_PYTEST)


TEXT_MUTATIONS = {
    # reviewers' shell bypasses (#591 round 3, #605 round 1)
    "M502-text-uv-python": _insert_ci("          uv run --python 3.12 -V\n"),
    "M502-text-if-prefix": _insert_ci(
        "          if uv run --python 3.12 --locked python -V; then echo ok; fi\n"
    ),
    "M502-text-then-assignment": _insert_ci(
        "          if true; then UV_PYTHON=3.12 uv run --locked python -V; fi\n"
    ),
    "M502-text-heredoc-dash": _insert_ci(
        "          cat <<-EOF\n            log text\n          EOF\n"
        "          uv run --python 3.12 --locked python -V\n"
    ),
    "M502-text-bash-c": _insert_ci(
        "          bash -c 'uv run -p 3.12 --locked python -V'\n"
    ),
    "M502-text-eval": _insert_ci(
        '          eval "uv run --python=3.12 --locked python -V"\n'
    ),
    "M502-text-sudo-env": _insert_ci(
        "          sudo -E env UV_PYTHON=3.12 uv run --locked python -V\n"
    ),
    "M502-text-tee-github-env": _insert_ci(
        '          echo UV_PYTHON=3.12 | tee -a "$GITHUB_ENV"\n'
    ),
    "M502-text-unknown-uv-option": _insert_ci(
        "          uv run --no-extra baml -p 3.12 --locked python -V\n"
    ),
    "M502-text-combined-short-flags": _insert_ci(
        "          uv run -qp 3.12 --locked python -V\n"
    ),
    # -p in any form
    "M502-text-p-equals": _insert_ci("          uv run -p=3.12 -V\n"),
    "M502-text-p-var": _insert_ci(
        '          FLOOR=3.12\n          uv run -p "$FLOOR" -V\n'
    ),
    "M502-text-p-expression": _insert_ci("          uv run -p ${{ vars.FLOOR }} -V\n"),
    "M502-text-p-cp312": _insert_ci("          uv run -p cp312 -V\n"),
    "M502-text-p-range": _insert_ci("          uv run -p '>=3.12,<3.13' python -V\n"),
    "M502-text-p-eq": _insert_ci("          uv run -p ==3.12 -V\n"),
    "M502-text-p-quoted-flag": _insert_ci('          uv run "-p" 3.12 -V\n'),
    "M502-text-p-continuation": _insert_ci(
        "          uv run --locked -p \\\n            3.12 python -V\n"
    ),
    "M502-text-cpython-p": _insert_ci("          uvx -p cpython@3.12 ruff\n"),
    # interpreter spellings
    "M502-text-python3x": _insert_ci("          python3.12 -m pytest\n"),
    "M502-text-path-python": _insert_ci("          /usr/bin/python3.12 -m pytest\n"),
    "M502-text-py-launcher": _insert_ci("          py -3.12 -m pytest\n"),
    "M502-text-py-v": _insert_ci("          py -V:3.12 -m pytest\n"),
    "M502-text-py-exe": _insert_ci("          py.exe -3.12 -m pytest\n"),
    "M502-text-uvx-python-at": _insert_ci("          uvx python@3.12 -V\n"),
    "M502-text-uv-python-pin": _insert_ci("          uv python pin 3.12\n"),
    "M502-text-uv-python-install": _insert_ci("          uv python install 3.12\n"),
    "M502-text-uv-python-find": _insert_ci("          uv python find 3.12\n"),
    "M502-text-windows-path": _insert_ci(
        "          C:/Python312/python.exe -m pytest\n"
    ),
    "M502-text-pyenv-version": _insert_ci("          PYENV_VERSION=3.12 python -V\n"),
    "M502-text-uv-python-lowercase": _insert_ci(
        "          uv_python=3.12 uv run python -V\n"
    ),
    "M502-text-comment": _insert_ci("          # switch to python3.12 for this step\n"),
    "M502-text-echo": _insert_ci('          echo "export UV_PYTHON=3.12"\n'),
    # settings
    "M502-text-uv-python-env": (
        "ci.yml",
        "      UV_PYTHON: '3.14'\n",
        "      UV_PYTHON: '3.12'\n",
    ),
    "M502-text-setup-python": (
        "docs.yml",
        "        python-version: '3.14'\n",
        "        python-version: '3.12'\n",
    ),
    "M502-text-event-version": (
        "ci.yml",
        "      UV_PYTHON: '3.14'\n",
        "      UV_PYTHON: \"${{ github.event_name == 'schedule' && '3.12' || '3.14' }}\"\n",
    ),
    "M502-text-trailing-uv-python": (
        "ci.yml",
        "      UV_PYTHON: '3.14'\n",
        "      UV_PYTHON: '3.14' # UV_PYTHON=3.12\n",
    ),
    "M502-text-trailing-python-version": (
        "ci.yml",
        "      UV_PYTHON: '3.14'\n",
        "      UV_PYTHON: '3.14' # python-version: '3.12'\n",
    ),
    # job attribution, platform scope, matrix and anchors
    "M502-text-quoted-job-release": (
        "release.yml",
        "  create-release:\n",
        "  'extra':\n    runs-on: ubuntu-latest\n    steps:\n"
        "    - run: uv run --python 3.12 python -V\n\n  create-release:\n",
    ),
    "M502-text-quoted-job-test": (
        "test.yml",
        "    - name: Install dependencies\n",
        None,  # appended job, see _apply
    ),
    "M502-text-family-scope": (
        "test.yml",
        "    - name: Install dependencies\n",
        "    - name: floor everywhere\n"
        "      run: uv run --python 3.12 python scripts/run_platform_core.py"
        " --platform ${{ matrix.platform-family }}\n"
        "    - name: Install dependencies\n",
    ),
    "M502-text-macos-floor": (
        "test.yml",
        "          - python-version: '3.14'\n            platform: macos-latest\n",
        "          - python-version: '3.12'\n            platform: macos-latest\n",
    ),
    "M502-text-computed-include": (
        "baml-grammar-wheels.yml",
        "        python-version: ['3.14']\n",
        "        include: ${{ fromJSON(vars.BAML_TEST_INCLUDE) }}\n",
    ),
    "M502-text-yaml-anchor": (
        "baml-grammar-wheels.yml",
        "      - name: Build and smoke-test cp312-abi3 wheel on Python 3.12\n",
        None,  # anchor in wheel, alias in test-wheel, see _apply
    ),
}


def _apply(mutation: str, texts: dict[str, str]) -> str:
    workflow, anchor, new = TEXT_MUTATIONS[mutation]
    text = texts[workflow]
    assert anchor in text, (mutation, anchor)
    if mutation == "M502-text-quoted-job-test":
        texts[workflow] = text.rstrip("\n") + (
            '\n\n  "full-on-floor":\n    runs-on: windows-latest\n    steps:\n'
            "    - run: uv run --python 3.12 python scripts/run_full_suite.py\n"
        )
    elif mutation == "M502-text-yaml-anchor":
        text = text.replace(
            anchor, "      - &floor_step\n        run: echo floor\n" + anchor, 1
        )
        test_wheel_steps = "    steps:\n      - uses: actions/download-artifact"
        assert test_wheel_steps in text
        texts[workflow] = text.replace(
            test_wheel_steps,
            "    steps:\n      - *floor_step\n      - uses: actions/download-artifact",
            1,
        )
    else:
        texts[workflow] = text.replace(anchor, new, 1)
    return workflow


@pytest.mark.parametrize("mutation", sorted(TEXT_MUTATIONS))
def test_text_mutations_are_rejected(mutation):
    texts = _workflow_texts()
    workflow = _apply(mutation, texts)
    offenders = _text_offenders(texts)
    assert offenders and all(o.startswith(f"{workflow}:") for o in offenders), offenders
    with pytest.raises(AssertionError) as failure:
        _assert_no_text_offenders(texts)
    assert _TEXT_FIX in str(failure.value)
    assert f"{workflow}:" in str(failure.value)


def test_quoted_job_is_attributed_to_itself():
    texts = _workflow_texts()
    _apply("M502-text-quoted-job-release", texts)
    offenders = _text_offenders(texts)
    assert any("[extra] --python" in o for o in offenders), offenders


def test_yaml_workflow_extension_is_scanned(tmp_path, monkeypatch):
    """A .yaml workflow file is discovered by the text scan and the parsed checks."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    for path in _workflow_paths():
        (workflows / path.name).write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (workflows / "extra.yaml").write_text(
        "name: extra\non: workflow_dispatch\njobs:\n  extra:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/setup-python@v5\n        with:\n"
        "          python-version: '3.12'\n      - run: python3.12 -V\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    assert "extra.yaml" in _workflow_texts() and "extra.yaml" in _workflow_docs()
    offenders = _text_offenders()
    assert offenders and all(o.startswith("extra.yaml:") for o in offenders), offenders
    assert ("extra.yaml", "extra", None) in _floor_uses()


# Text that must not be reported: the three named -p exclusions.
TEXT_NON_SELECTORS = {
    "pytest-p-no": "          uv run --locked pytest -p no:cacheprovider -q\n",
    "mkdir-p": "          mkdir -p dist/wheelhouse\n",
    "tar-cpf": "          tar -cpf out.tar dist\n",
}


@pytest.mark.parametrize("case", sorted(TEXT_NON_SELECTORS))
def test_text_scan_ignores_named_exclusions(case):
    texts = _workflow_texts()
    assert _CI_PYTEST in texts["ci.yml"]
    texts["ci.yml"] = texts["ci.yml"].replace(
        _CI_PYTEST, TEXT_NON_SELECTORS[case] + _CI_PYTEST, 1
    )
    assert _text_offenders(texts) == []


def test_named_exclusions_do_not_hide_a_second_p():
    texts = _workflow_texts()
    texts["ci.yml"] = texts["ci.yml"].replace(
        _CI_PYTEST, "          mkdir -p d && uv run -p 3.12 -V\n" + _CI_PYTEST, 1
    )
    assert _text_offenders(texts)


def test_text_scan_allows_anything_in_named_floor_jobs():
    texts = _workflow_texts()
    anchor = "    - name: Verify complete wheel-only locked installation and CLI\n"
    assert anchor in texts["release.yml"]
    texts["release.yml"] = texts["release.yml"].replace(
        anchor,
        "    # floor check: uv run --python 3.12, python3.12, UV_PYTHON\n" + anchor,
        1,
    )
    assert _text_offenders(texts) == []


def test_baml_companion_abi_floor_comes_from_its_build_config():
    """The companion's cp312-abi3 floor is set by setup.py and CIBW_BUILD."""
    setup = (ROOT / "packages/baml-grammar/setup.py").read_text(encoding="utf-8")
    assert '("Py_LIMITED_API", "0x030C0000")' in setup
    assert '"py_limited_api": "cp312"' in setup
    wheel = _workflow("baml-grammar-wheels.yml")["jobs"]["wheel"]
    builds = [
        (step.get("env") or {}).get("CIBW_BUILD")
        for step in wheel["steps"]
        if "CIBW_BUILD" in (step.get("env") or {})
    ]
    assert builds == ["cp312-*"]


def test_primary_python_runs_ci_full_tier_and_release():
    """CI (smoke and scheduled full tier) and release run on 3.14; no new jobs."""
    floor = _floor_text()
    assert floor != PRIMARY_PYTHON

    ci = _workflow("ci.yml")["jobs"]
    assert list(ci) == ["test"]
    job = ci["test"]
    assert str(job["env"]["UV_PYTHON"]) == PRIMARY_PYTHON
    assert _setup_python_versions(job) == [PRIMARY_PYTHON]
    # The same job runs the full tier when scheduled and the smoke tier otherwise.
    pytest_step = next(s for s in job["steps"] if s.get("name") == "Pytest")
    full_branch, smoke_branch = pytest_step["run"].split("else", 1)
    assert '"$GITHUB_EVENT_NAME" = "schedule"' in full_branch
    assert "scripts/run_full_suite.py" in full_branch
    assert "scripts/run_ci_smoke.py" in smoke_branch

    release = _workflow("release.yml")["jobs"]
    assert release["release-validation"]["strategy"]["matrix"]["python-version"] == [
        PRIMARY_PYTHON
    ]
    build = release["build-distributions"]
    assert str(build["env"]["UV_PYTHON"]) == PRIMARY_PYTHON
    assert _setup_python_versions(build) == [PRIMARY_PYTHON]

    platform = _workflow("test.yml")["jobs"]
    assert list(platform) == ["test"]
    matrix = platform["test"]["strategy"]["matrix"]
    assert set(matrix) == {"include"}
    layout = sorted(
        (item["platform-family"], str(item["python-version"]))
        for item in matrix["include"]
    )
    assert layout == [
        ("linux", floor),
        ("macos", PRIMARY_PYTHON),
        ("windows", PRIMARY_PYTHON),
    ]
    assert platform["test"]["env"]["UV_PYTHON"] == "${{ matrix.python-version }}"

    # The lint and type checks run once per CI run, in the ci.yml job on 3.14.
    gate = "scripts/mypy_gate.py"
    runs = [
        (workflow, name)
        for workflow, name, _env, job in _workflow_jobs()
        for step in job.get("steps") or []
        if gate in str(step.get("run", "")) and workflow in ("ci.yml", "test.yml")
    ]
    assert runs == [("ci.yml", "test")]


def test_publication_requires_full_validation_and_verified_artifacts():
    """A release cannot bypass failed source checks or missing build artifacts."""
    jobs = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())["jobs"]
    validation = jobs["release-validation"]
    assert not validation.get("continue-on-error", False)
    assert validation["strategy"]["matrix"]["python-version"] == [PRIMARY_PYTHON]
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
    # Explicitly no token scopes (treesitter-chunker#507).
    assert job["permissions"] == {}
    assert not job.get("continue-on-error")
    assert len(job["steps"]) == 1
    step = job["steps"][0]
    assert set(step) == {"name", "run"}
    commands = step["run"].splitlines()
    assert len(commands) == 2
    assert commands[0].startswith('echo "::error::')
    assert "distribution is suspended for v5" in commands[0]
    assert commands[1] == "exit 1"

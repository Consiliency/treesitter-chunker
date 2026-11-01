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


def _workflow_docs() -> dict[str, dict]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / ".github/workflows").glob("*.yml"))
    }


def _workflow_jobs(docs: dict[str, dict] | None = None):
    for name_, workflow in (docs if docs is not None else _workflow_docs()).items():
        for name, job in (workflow.get("jobs") or {}).items():
            yield name_, name, workflow.get("env") or {}, job


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

# Shell-level interpreter selection inside a step's ``run:`` script. The scan is
# structural: each script is normalized (line continuations joined, heredoc
# bodies skipped, GitHub expressions held as placeholders), split into shell
# commands with shlex (comments dropped, quotes respected, operators split), and
# only command tokens are inspected, never echo output or prose. Every
# selector value must resolve to concrete versions; an unresolvable or
# event-dependent value is reported as UNRESOLVED.
_GH_EXPR = re.compile(r"\$\{\{(.*?)\}\}", re.S)
_SHELL_VAR = re.compile(r"\$(?:\{(\w+)\}|(\w+))")
_ASSIGNMENT = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.S)
_PYTHON_COMMAND = re.compile(r"(?:^|[/\\])python(\d+\.\d+)(?:\.exe)?$")
_PY_LAUNCHER = re.compile(r"^-(?:V:)?(\d+\.\d+)$")
_OPERATORS = {";", "&&", "||", "|", "&", "(", ")", ";;", "|&"}
_COMMAND_PREFIXES = {"sudo", "exec", "time", "command", "nohup", "then", "do", "else"}
# uv options that consume the next token as their value.
_UV_VALUE_OPTIONS = {
    "--python",
    "-p",
    "--python-version",
    "--with",
    "-w",
    "--with-requirements",
    "--with-editable",
    "--directory",
    "--project",
    "--config-file",
    "--cache-dir",
    "--index",
    "--default-index",
    "--index-url",
    "-i",
    "--extra-index-url",
    "--find-links",
    "-f",
    "--extra",
    "--group",
    "--only-group",
    "--no-group",
    "--package",
    "--env-file",
    "--from",
    "--python-platform",
    "--exclude-newer",
    "--prerelease",
    "--resolution",
    "--link-mode",
    "--keyring-provider",
    "--allow-insecure-host",
    "-C",
    "--config-setting",
    "--refresh-package",
    "-P",
    "--upgrade-package",
    "--reinstall-package",
    "--no-binary-package",
    "--no-build-package",
    "--format",
    "-o",
    "--output-file",
    "-r",
    "--requirement",
    "--constraint",
    "-c",
    "--overrides",
    "--target",
    "--prefix",
}
# After these, the remaining tokens belong to the wrapped program.
_UV_PROGRAM_SUBCOMMANDS = {"run", "tool"}
_KNOWN_MINORS = [f"3.{minor}" for minor in range(8, 17)]


def _expand(
    text: str, job: dict, env: dict[str, str], depth: int = 0
) -> list[str] | None:
    """Expand GitHub matrix expressions and shell variables, or None if unknown."""
    if depth > 5 or "$(" in text or "`" in text:
        return None
    gh = _GH_EXPR.search(text)
    if gh:
        expression = gh.group(1).strip()
        match = re.fullmatch(r"matrix\.([\w-]+)", expression)
        if not match or "github.event" in expression:
            return None
        values = _matrix_values(job, match.group(1))
        if not values:
            return None
        out: list[str] = []
        for value in values:
            sub = _expand(
                text[: gh.start()] + value + text[gh.end() :], job, env, depth + 1
            )
            if sub is None:
                return None
            out += sub
        return out
    var = _SHELL_VAR.search(text)
    if var:
        name = var.group(1) or var.group(2)
        if name not in env:
            return None
        sub = _expand(str(env[name]), job, env, depth + 1)
        if sub is None:
            return None
        return [
            out
            for value in sub
            for out in (
                _expand(
                    text[: var.start()] + value + text[var.end() :], job, env, depth + 1
                )
                or [None]
            )
            if out is not None
        ] or None
    return [text]


def _versions_of(value: str) -> list[str] | None:
    """Versions an interpreter request selects: 3.12, cpython-3.12, cpython@3.12,
    a specifier such as >=3.12,<3.13 (every admitted minor), or None."""
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    value = value.strip().strip("'\"")
    if value[:1] in "<>=!~":
        try:
            spec = SpecifierSet(value)
        except InvalidSpecifier:
            return None
        admitted = [
            v for v in _KNOWN_MINORS if spec.contains(f"{v}.0", prereleases=True)
        ]
        return admitted or None
    match = re.search(r"(\d+)\.(\d+)", value)
    return [f"{match.group(1)}.{match.group(2)}"] if match else None


def _split_commands(script: str) -> list[list[str]]:
    """Normalize a run: script and split it into shell commands (token lists)."""
    import shlex

    placeholders: dict[str, str] = {}

    def hold(match: re.Match) -> str:
        key = f"__GHE{len(placeholders)}__"
        placeholders[key] = match.group(0)
        return key

    script = _GH_EXPR.sub(hold, re.sub(r"\\\r?\n", " ", script))
    commands: list[list[str]] = []
    heredoc: tuple[str, bool] | None = None
    for line in script.splitlines():
        if heredoc:
            tag, strip_tabs = heredoc
            if (line.lstrip("\t") if strip_tabs else line).strip() == tag:
                heredoc = None
            continue
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        try:
            tokens = list(lexer)
        except ValueError:
            tokens = line.split()
        current: list[str] = []
        for index, token in enumerate(tokens):
            if token in ("<<", "<<-") and index + 1 < len(tokens):
                heredoc = (tokens[index + 1], token == "<<-")
            if token in _OPERATORS:
                if current:
                    commands.append(current)
                current = []
            else:
                for key, original in placeholders.items():
                    token = token.replace(key, original)
                current.append(token)
        if current:
            commands.append(current)
    return commands


def _command_selectors(tokens: list[str], local: dict[str, str]) -> list[str]:
    """Raw interpreter-selector values named by one shell command."""
    selected: list[str] = []
    index = 0
    # Leading assignments (VAR=value cmd, or a bare assignment line).
    while index < len(tokens) and _ASSIGNMENT.match(tokens[index]):
        name, value = _ASSIGNMENT.match(tokens[index]).groups()
        local[name] = value
        if name == "UV_PYTHON":
            selected.append(value)
        index += 1
    while index < len(tokens) and tokens[index] in _COMMAND_PREFIXES:
        index += 1
    if index >= len(tokens):
        return selected
    command, args = tokens[index], tokens[index + 1 :]
    base = command.replace("\\", "/").rsplit("/", 1)[-1]
    if base in ("export", "env", "declare", "typeset", "local", "readonly"):
        for arg in args:
            match = _ASSIGNMENT.match(arg)
            if match:
                local[match.group(1)] = match.group(2)
                if match.group(1) == "UV_PYTHON":
                    selected.append(match.group(2))
            elif base == "env" and not arg.startswith("-"):
                rest = args[args.index(arg) :]
                return selected + _command_selectors(rest, local)
        return selected
    if command.startswith("$env:UV_PYTHON"):  # PowerShell
        value = command.partition("=")[2] or (args[1] if args[:1] == ["="] else "")
        return selected + [value or "$env:UV_PYTHON"]
    if base in ("echo", "printf"):
        writes_env = any(
            op in (">", ">>")
            and target.strip("'\"") in ("$GITHUB_ENV", "${GITHUB_ENV}")
            for op, target in zip(args, args[1:])
        )
        if writes_env:
            selected += [
                m.group(2)
                for arg in args
                if (m := _ASSIGNMENT.match(arg)) and m.group(1) == "UV_PYTHON"
            ]
        return selected
    if _PYTHON_COMMAND.search(command):
        return selected + [_PYTHON_COMMAND.search(command).group(1)]
    if base in ("py", "py.exe"):
        if args and _PY_LAUNCHER.match(args[0]):
            selected.append(_PY_LAUNCHER.match(args[0]).group(1))
        return selected
    if base not in ("uv", "uvx", "uv.exe", "uvx.exe"):
        return selected
    subcommand = "tool" if base.startswith("uvx") else None
    position = 0
    while position < len(args):
        token = args[position]
        if token == "--":
            break
        if subcommand is None and not token.startswith("-"):
            subcommand = token
            if token == "python" and position + 1 < len(args):
                if args[position + 1] in ("install", "pin", "find"):
                    selected += [
                        a for a in args[position + 2 :] if not a.startswith("-")
                    ]
                    return selected
            position += 1
            continue
        for option in ("--python", "--python-version", "-p"):
            if token == option and position + 1 < len(args):
                selected.append(args[position + 1])
            elif token.startswith(option + "="):
                selected.append(token.split("=", 1)[1])
            elif (
                option == "-p"
                and token.startswith("-p")
                and len(token) > 2
                and token[2] != "-"
            ):
                selected.append(token[2:].lstrip("="))
        if token.startswith("-"):
            name = token.split("=", 1)[0]
            if name in ("-m", "--module", "--script", "-s"):
                break
            position += 2 if name in _UV_VALUE_OPTIONS and "=" not in token else 1
            continue
        if subcommand in _UV_PROGRAM_SUBCOMMANDS:
            if subcommand == "tool" and token == "run":
                position += 1
                continue
            break  # the wrapped program's own arguments follow
        position += 1
    return selected


def _run_selectors(workflow_env: dict, job: dict) -> list[str]:
    """Versions selected inside a job's run: scripts; UNRESOLVED:<value> if unknown."""
    versions: list[str] = []
    for step in job.get("steps") or []:
        if "run" not in step:
            continue
        env = {
            **{k: str(v) for k, v in (workflow_env or {}).items()},
            **{k: str(v) for k, v in (job.get("env") or {}).items()},
            **{k: str(v) for k, v in (step.get("env") or {}).items()},
        }
        local: dict[str, str] = {}
        for tokens in _split_commands(str(step["run"])):
            for raw in _command_selectors(tokens, local):
                expanded = _expand(raw, job, {**env, **local})
                found = (
                    [v for value in expanded for v in (_versions_of(value) or [None])]
                    if expanded
                    else [None]
                )
                versions += [v if v else f"UNRESOLVED:{raw}" for v in found]
    return versions


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
        if floor in _run_selectors(workflow_env, job):
            uses.add((workflow, name, None))
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


def _run_offenders(docs: dict[str, dict] | None = None) -> list[tuple[str, str, str]]:
    floor = _floor_text()
    allowed = {(w, j) for w, j, _family in FLOOR_ALLOWED}
    return [
        (workflow, name, version)
        for workflow, name, workflow_env, job in _workflow_jobs(docs)
        for version in _run_selectors(workflow_env, job)
        if version != PRIMARY_PYTHON
        and not (version == floor and (workflow, name) in allowed)
    ]


def test_run_scripts_select_only_the_primary_or_allowed_floor():
    """``run:`` selectors resolve to 3.14, or 3.12 only in an allowed floor job."""
    assert _run_offenders() == []


def _pytest_step(docs: dict[str, dict]) -> dict:
    return next(
        s for s in docs["ci.yml"]["jobs"]["test"]["steps"] if s.get("name") == "Pytest"
    )


_FULL = "uv run --locked --all-extras python scripts/run_full_suite.py"


def _replace_full(new: str):
    def mutate(docs: dict[str, dict]) -> None:
        step = _pytest_step(docs)
        assert _FULL in step["run"]
        step["run"] = step["run"].replace(_FULL, new, 1)

    return mutate


def _with_job(key: str, value: dict, new: str):
    def mutate(docs: dict[str, dict]) -> None:
        docs["ci.yml"]["jobs"]["test"].setdefault(key, {}).update(value)
        _replace_full(new)(docs)

    return mutate


_EVENT = "${{ github.event_name == 'schedule' && '3.12' || '3.14' }}"

# Named mutations of the scheduled full-tier command in the ci.yml Pytest step.
# Each selects 3.12 (or an event-chosen interpreter) and must be rejected.
RUN_OVERRIDE_MUTATIONS = {
    "M502-run-uv-python": _replace_full(
        _FULL.replace("uv run", "uv run --python 3.12")
    ),
    "M502-run-double-space": _replace_full(
        _FULL.replace("uv run", "uv run --python  3.12")
    ),
    "M502-run-python-equals": _replace_full(
        _FULL.replace("uv run", "uv run --python=3.12")
    ),
    "M502-run-uv-p": _replace_full(_FULL.replace("uv run", "uv run -p 3.12")),
    "M502-run-p-equals": _replace_full(_FULL.replace("uv run", "uv run -p=3.12")),
    "M502-run-continued-p": _replace_full(
        _FULL.replace("uv run", "uv run \\\n  -p 3.12")
    ),
    "M502-run-continued-python": _replace_full(
        _FULL.replace("uv run", "uv run --python \\\n  3.12")
    ),
    "M502-run-cpython-dash": _replace_full(
        _FULL.replace("uv run", "uv run --python cpython-3.12")
    ),
    "M502-run-cpython-at": _replace_full(
        _FULL.replace("uv run", "uv run --python cpython@3.12")
    ),
    "M502-run-specifier": _replace_full(
        _FULL.replace("uv run", "uv run --python '>=3.12,<3.13'")
    ),
    "M502-run-export": _replace_full("export UV_PYTHON=3.12; " + _FULL),
    "M502-run-export-quoted": _replace_full('export "UV_PYTHON=3.12"; ' + _FULL),
    "M502-run-github-env": _replace_full(
        'echo UV_PYTHON=3.12 >> "$GITHUB_ENV"; ' + _FULL
    ),
    "M502-run-python3x": _replace_full("python3.12 -m " + _FULL),
    "M502-run-path-python": _replace_full("/usr/bin/python3.12 -m " + _FULL),
    "M502-run-py-launcher": _replace_full("py -3.12 -m " + _FULL),
    "M502-run-py-v": _replace_full("py -V:3.12 -m " + _FULL),
    "M502-run-uv-python-install": _replace_full("uv python install 3.12; " + _FULL),
    "M502-run-matrix-expr": _with_job(
        "strategy",
        {"matrix": {"legacy": ["3.12"]}},
        _FULL.replace("uv run", "uv run --python ${{ matrix.legacy }}"),
    ),
    "M502-run-env-var": _with_job(
        "env", {"PY": "3.12"}, _FULL.replace("uv run", "uv run --python $PY")
    ),
    "M502-run-env-braces": _with_job(
        "env", {"PY": "3.12"}, _FULL.replace("uv run", 'uv run --python "${PY}"')
    ),
    "M502-run-event": _replace_full(
        _FULL.replace("uv run", f"uv run --python {_EVENT}")
    ),
    "M502-run-event-local-var": _replace_full(
        f"PY={_EVENT}; " + _FULL.replace("uv run", 'uv run --python "$PY"')
    ),
    "M502-run-unknown-var": _replace_full(
        _FULL.replace("uv run", "uv run --python $UNDECLARED")
    ),
}


@pytest.mark.parametrize("mutation", sorted(RUN_OVERRIDE_MUTATIONS))
def test_run_override_mutations_are_rejected(mutation):
    docs = _workflow_docs()
    assert _run_offenders(docs) == []
    RUN_OVERRIDE_MUTATIONS[mutation](docs)
    offenders = _run_offenders(docs)
    assert offenders and all(o[:2] == ("ci.yml", "test") for o in offenders)


# Lines that mention 3.12 without selecting an interpreter: comments, output,
# a wrapped program's own -p option, heredoc script content and quoted strings.
RUN_NON_SELECTORS = {
    "comment": "# Never use uv run --python 3.12 here",
    "trailing-comment": "true  # uv run -p 3.12",
    "echo-prose": "echo 'see the docs for python3.12 notes'",
    "echo-floor": 'echo "Python floor: python3.12"',
    "echo-uv-python": 'echo "uv run --python 3.12 is not used"',
    "printf-assignment": "printf 'UV_PYTHON=3.12\\n'",
    "tool-own-p": "uv run --locked python -m sometool -p 3.12",
    "uvx-tool-p": "uvx ruff check -p 3.12",
    "pytest-plugin-p": "uv run --locked pytest -p no:cacheprovider",
    "heredoc-body": "python - <<'PY'\nimport subprocess\nsubprocess.run(['python3.12', '-V'])\nPY",
    "site-packages-path": "ls .venv/lib/python3.12/site-packages",
    "quoted-arg": "grep -n 'uv run --python 3.12' README.md",
}


@pytest.mark.parametrize("case", sorted(RUN_NON_SELECTORS))
def test_run_scan_ignores_non_selectors(case):
    docs = _workflow_docs()
    _replace_full(RUN_NON_SELECTORS[case] + "\n" + _FULL)(docs)
    assert _run_offenders(docs) == []


def test_run_scan_accepts_primary_selectors():
    docs = _workflow_docs()
    _replace_full(
        "uv python install 3.14; export UV_PYTHON=3.14; "
        + _FULL.replace("uv run", "uv run --python cpython@3.14")
    )(docs)
    assert _run_offenders(docs) == []
    assert "3.14" in _run_selectors({}, docs["ci.yml"]["jobs"]["test"])


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

"""Central validator, CLI load sites and admitted health (treesitter-chunker#362).

ADMIT SL-core-2: ``GrammarValidator`` admits candidates through
``probe_native_grammar`` under its own pins (N2, N3), keeps pin holders off
``chunker.parser``, reuses verdicts only inside the producing process under the
frozen key, ``GrammarInstaller``/``GrammarRegistry``/``GrammarManager`` and
``ComprehensiveGrammarCLI`` forward pins, the click group resolves the pin
source, the CLI load sites (N4, N5, N6) admit, and
``GrammarManager.get_admitted_health`` is IF-0-ADMIT-1.

Native checks use real grammars compiled from ``packages/baml-grammar/src`` with
the exported symbol renamed so the registry, not the BAML companion, resolves
them.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from hashlib import sha256
from pathlib import Path

import pytest
from click.testing import CliRunner

from chunker._internal import native_admission
from chunker._internal.trusted_artifacts import (
    TRUSTED_ARTIFACTS_SCHEMA,
    user_config_pin_path,
)
from chunker.grammar import integrity
from chunker.grammar_management import core as core_module
from chunker.grammar_management.cli import ComprehensiveGrammarCLI, grammar_cli
from chunker.grammar_management.core import (
    GrammarInstaller,
    GrammarManager,
    GrammarRegistry,
    GrammarValidator,
    ValidationLevel,
)
from tests.test_compiled_grammar_analysis_contract import FIXTURE
from tests.test_registry_admission_contract import _build

LANGUAGE = "admitfixture"
SUFFIX = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
SAMPLE = FIXTURE.read_text(encoding="utf-8")


def require(condition: object, name: str) -> None:
    if not condition:
        raise AssertionError(name)


def _pin(data: bytes) -> dict[str, str]:
    return {"sha256": sha256(data).hexdigest()}


@pytest.fixture(scope="module")
def fixture_bytes(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return _build(
        tmp_path_factory.mktemp("validator"), [LANGUAGE], LANGUAGE
    ).read_bytes()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Private pin-file locations; HOME/USERPROFILE stay intact in-process."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.delenv("CHUNKER_GRAMMAR_BUILD_DIR", raising=False)
    return home


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []
    real = integrity.probe_native_grammar

    def counting(path, language, **kwargs):
        calls.append(Path(path))
        return real(path, language, **kwargs)

    monkeypatch.setattr(integrity, "probe_native_grammar", counting)
    return calls


@pytest.fixture
def loads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record in-process native loads by ``load_compiled_grammar``."""
    calls: list[Path] = []
    real = core_module.ctypes.CDLL

    def recording(name, *args, **kwargs):
        calls.append(Path(name))
        return real(name, *args, **kwargs)

    monkeypatch.setattr(core_module.ctypes, "CDLL", recording)
    return calls


def _candidate(tmp_path: Path, data: bytes, name: str = LANGUAGE) -> Path:
    path = tmp_path / "candidates" / f"lib{name}{SUFFIX}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _document(artifacts: dict[str, object]) -> str:
    return json.dumps({"schema": TRUSTED_ARTIFACTS_SCHEMA, "artifacts": artifacts})


# --- N2 and N3 ----------------------------------------------------------------------


def test_abi_check_admits_through_probe_without_loading(
    isolated, tmp_path, fixture_bytes, probes, loads
):
    candidate = _candidate(tmp_path, fixture_bytes)
    unpinned = GrammarValidator(tmp_path / "cache", trusted_artifacts={})
    require(
        unpinned.check_abi_compatibility(candidate, LANGUAGE)
        == (False, "Native admission failed: untrusted"),
        "unpinned is untrusted",
    )
    require(probes == [], "no probe without a pin")
    wrong = GrammarValidator(
        tmp_path / "cache", trusted_artifacts={LANGUAGE: {"sha256": "0" * 64}}
    )
    require(
        wrong.check_abi_compatibility(candidate, LANGUAGE)
        == (False, "Native admission failed: integrity_mismatch"),
        "mismatched pin",
    )
    pinned = GrammarValidator(
        tmp_path / "cache", trusted_artifacts={LANGUAGE: _pin(fixture_bytes)}
    )
    require(pinned.check_abi_compatibility(candidate, LANGUAGE) == (True, None), "ok")
    require(len(probes) == 1, f"one probe {probes}")
    require(loads == [], f"N2 loads nothing in-process {loads}")


def test_parse_samples_with_path_loads_only_admitted_copy(
    isolated, tmp_path, fixture_bytes, loads
):
    candidate = _candidate(tmp_path, fixture_bytes)
    unpinned = GrammarValidator(tmp_path / "cache", trusted_artifacts={})
    ok, errors = unpinned.test_parse_samples(LANGUAGE, [SAMPLE], candidate)
    require(
        not ok and errors == ["Parser setup failed: native admission untrusted"],
        f"{errors}",
    )
    require(loads == [], "no load without a pin")
    pinned = GrammarValidator(
        tmp_path / "cache", trusted_artifacts={LANGUAGE: _pin(fixture_bytes)}
    )
    ok, errors = pinned.test_parse_samples(LANGUAGE, [SAMPLE], candidate)
    require(ok and errors == [], f"pinned parses {errors}")
    require(loads and candidate not in loads, f"candidate never mapped {loads}")
    require(
        all(path.parent.name.startswith("chunker-admitted-") for path in loads),
        f"admitted copies only {loads}",
    )


def test_parse_samples_without_path_stays_off_the_parse_path(
    isolated, tmp_path, fixture_bytes, monkeypatch
):
    """EC-ADMIT-6: a config pin never reaches a validator with its own (empty) pins."""
    from chunker import parser as parser_module

    build = tmp_path / "build"
    build.mkdir()
    (build / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_bytes)
    monkeypatch.setenv("CHUNKER_GRAMMAR_BUILD_DIR", str(build))
    config = user_config_pin_path()
    assert config is not None
    config.parent.mkdir(parents=True)
    config.write_text(_document({LANGUAGE: _pin(fixture_bytes)}), encoding="utf-8")
    fresh = parser_module._ParserState()
    fresh.default_library_path = tmp_path / f"missing{SUFFIX}"
    monkeypatch.setattr(parser_module, "_state", fresh)

    empty = GrammarValidator(tmp_path / "cache", trusted_artifacts={})
    ok, errors = empty.test_parse_samples(LANGUAGE, [SAMPLE])
    require(not ok, f"config pin not used by a pin holder {errors}")
    require(any("untrusted" in error for error in errors), f"cause named {errors}")

    own = GrammarValidator(
        tmp_path / "cache", trusted_artifacts={LANGUAGE: _pin(fixture_bytes)}
    )
    ok, errors = own.test_parse_samples(LANGUAGE, [SAMPLE])
    require(ok and errors == [], f"own registry and pins resolve it {errors}")


def test_parse_samples_without_path_keeps_package_supplied_grammars(isolated, tmp_path):
    """Carry-over 2: the validator's own registry still serves P1/P2 grammars."""
    validator = GrammarValidator(tmp_path / "cache", trusted_artifacts={})
    ok, errors = validator.test_parse_samples("python", ["def f():\n    return 1\n"])
    require(ok and errors == [], f"official python wheel {errors}")
    ok, errors = validator.test_parse_samples("typescript", ["const x: number = 1;\n"])
    require(ok and errors == [], f"language-pack grammar {errors}")


# --- verdict reuse in the validator cache (EC-ADMIT-3) -------------------------------


def test_persisted_ok_never_admits_in_a_new_process(
    isolated, tmp_path, fixture_bytes, probes
):
    candidate = _candidate(tmp_path, fixture_bytes)
    pins = {LANGUAGE: _pin(fixture_bytes)}
    cache = tmp_path / "cache"
    first = GrammarValidator(cache, trusted_artifacts=pins).validate_grammar(
        candidate, LANGUAGE, ValidationLevel.BASIC
    )
    require(first.is_valid, f"admitted {first.errors}")
    require((cache / "validation_cache.json").is_file(), "ok result persisted")
    again = GrammarValidator(cache, trusted_artifacts=pins).validate_grammar(
        candidate, LANGUAGE, ValidationLevel.BASIC
    )
    require(again.is_valid and len(probes) == 1, f"same process reuses {probes}")

    native_admission._reset_for_tests()  # a new process holds no admissions
    fresh = GrammarValidator(cache, trusted_artifacts=pins).validate_grammar(
        candidate, LANGUAGE, ValidationLevel.BASIC
    )
    require(fresh.is_valid, "still valid")
    require(len(probes) == 2, f"a new process probes again {probes}")


def test_validator_cache_rejects_same_stat_replacement_and_pin_change(
    isolated, tmp_path, fixture_bytes
):
    candidate = _candidate(tmp_path, fixture_bytes)
    pins = {LANGUAGE: _pin(fixture_bytes)}
    validator = GrammarValidator(tmp_path / "cache", trusted_artifacts=pins)
    require(
        validator.validate_grammar(candidate, LANGUAGE, ValidationLevel.BASIC).is_valid,
        "admitted",
    )
    status = candidate.stat()
    replaced = bytearray(fixture_bytes)
    replaced[len(replaced) // 2] ^= 0xFF
    candidate.write_bytes(bytes(replaced))
    os.utime(candidate, ns=(status.st_atime_ns, status.st_mtime_ns))
    after = validator.validate_grammar(candidate, LANGUAGE, ValidationLevel.BASIC)
    require(not after.is_valid, "same-stat replacement misses")
    require(
        any("integrity_mismatch" in error for error in after.errors), f"{after.errors}"
    )
    candidate.write_bytes(fixture_bytes)
    other = GrammarValidator(
        tmp_path / "cache", trusted_artifacts={LANGUAGE: {"sha256": "1" * 64}}
    )
    require(
        not other.validate_grammar(candidate, LANGUAGE, ValidationLevel.BASIC).is_valid,
        "a changed pin misses",
    )


def test_failed_validation_is_never_stored(isolated, tmp_path, fixture_bytes):
    candidate = _candidate(tmp_path, fixture_bytes)
    cache = tmp_path / "cache"
    result = GrammarValidator(cache, trusted_artifacts={}).validate_grammar(
        candidate, LANGUAGE, ValidationLevel.BASIC
    )
    require(not result.is_valid, "untrusted")
    require(not (cache / "validation_cache.json").exists(), "nothing stored")


# --- pin forwarding (TXN depends on GrammarInstaller) ---------------------------------


def test_constructors_copy_and_forward_pins(isolated, tmp_path):
    pins = {LANGUAGE: {"sha256": "a" * 64}}
    installer = GrammarInstaller(tmp_path / "installer", trusted_artifacts=pins)
    registry = GrammarRegistry(
        tmp_path / "user",
        tmp_path / "package",
        tmp_path / "registry",
        trusted_artifacts=pins,
    )
    manager = GrammarManager(
        tmp_path / "user",
        tmp_path / "package",
        tmp_path / "manager",
        trusted_artifacts=pins,
    )
    cli = ComprehensiveGrammarCLI(tmp_path / "cli", trusted_artifacts=pins)
    pins[LANGUAGE]["sha256"] = "b" * 64
    expected = {LANGUAGE: {"sha256": "a" * 64}}
    holders = {
        "installer validator": installer._validator._trusted_artifacts,
        "registry installer": registry._installer._trusted_artifacts,
        "registry installer validator": registry._installer._validator._trusted_artifacts,
        "manager validator": manager._validator._trusted_artifacts,
        "manager installer": manager._installer._trusted_artifacts,
        "manager registry installer": manager._registry._installer._trusted_artifacts,
        "manager property": manager.trusted_artifacts,
        "cli manager": cli.grammar_manager._trusted_artifacts,
    }
    for name, value in holders.items():
        require(value == expected, f"{name}: {value!r}")
    require(GrammarManager(cache_dir=tmp_path / "none").trusted_artifacts == {}, "none")


def test_compatibility_helpers_use_the_managers_pins(isolated, tmp_path):
    from chunker.grammar_management.compatibility import (
        CompatibilityChecker,
        GrammarTester,
    )

    pins = {LANGUAGE: {"sha256": "a" * 64}}
    manager = GrammarManager(
        tmp_path / "user",
        tmp_path / "package",
        tmp_path / "cache",
        trusted_artifacts=pins,
    )
    for helper in (CompatibilityChecker(manager), GrammarTester(manager)):
        require(helper.validator._trusted_artifacts == pins, type(helper).__name__)


# --- IF-0-ADMIT-1 ---------------------------------------------------------------------


def test_admitted_health_accessor(isolated, tmp_path, fixture_bytes, probes):
    user = tmp_path / "user"
    user.mkdir()
    (user / f"lib{LANGUAGE}.so").write_bytes(fixture_bytes)
    (user / "libempty.so").write_bytes(b"")
    pins = {LANGUAGE: _pin(fixture_bytes), "empty": {"sha256": "0" * 64}}
    manager = GrammarManager(
        user, tmp_path / "package", tmp_path / "cache", trusted_artifacts=pins
    )
    healthy = manager.get_admitted_health(LANGUAGE)
    require(healthy["status"] == "healthy", f"{healthy}")
    require(healthy["validation_reason"] == "ok", f"{healthy}")
    require(healthy["artifact_sha256"] == pins[LANGUAGE]["sha256"], f"{healthy}")
    require(
        healthy["path"] == str((user / f"lib{LANGUAGE}.so").absolute()), f"{healthy}"
    )
    require(
        set(healthy)
        == {
            "language",
            "status",
            "validation_reason",
            "artifact_sha256",
            "path",
            "issues",
        },
        f"{healthy}",
    )
    empty = manager.get_admitted_health("empty")
    require(
        (empty["status"], empty["validation_reason"]) == ("corrupted", "empty"),
        f"{empty}",
    )
    missing = manager.get_admitted_health("absent")
    require(
        (missing["status"], missing["validation_reason"]) == ("missing", "missing"),
        f"{missing}",
    )
    unpinned = GrammarManager(user, tmp_path / "package", tmp_path / "cache2")
    untrusted = unpinned.get_admitted_health(LANGUAGE)
    require(
        (untrusted["status"], untrusted["validation_reason"])
        == ("incompatible", "untrusted"),
        f"{untrusted}",
    )
    require(untrusted["artifact_sha256"] is None, "no digest without admission")


# --- click group and CLI sites (N4, N5, N6) --------------------------------------------


def _click(cache: Path, *argv: str, pins: Path | None = None):
    command = ["--cache-dir", str(cache)]
    if pins is not None:
        command += ["--trusted-artifacts", str(pins)]
    return CliRunner().invoke(grammar_cli, [*command, *argv])


def _installed(cache: Path, data: bytes) -> Path:
    user = cache / "grammars" / "user"
    user.mkdir(parents=True, exist_ok=True)
    library = user / f"lib{LANGUAGE}.so"
    library.write_bytes(data)
    return library


def test_click_group_option_and_config_fallback(
    isolated, tmp_path, fixture_bytes, loads
):
    cache = tmp_path / "cache"
    installed = _installed(cache, fixture_bytes)
    pins = tmp_path / "pins.json"
    pins.write_text(_document({LANGUAGE: _pin(fixture_bytes)}), encoding="utf-8")
    sample = tmp_path / "sample.baml"
    sample.write_text(SAMPLE, encoding="utf-8")

    unpinned = _click(cache, "test", LANGUAGE, str(sample))
    require(unpinned.exit_code == 1, unpinned.output)
    require("Native admission failed: untrusted" in unpinned.output, unpinned.output)

    with_option = _click(cache, "test", LANGUAGE, str(sample), pins=pins)
    require(with_option.exit_code == 0, with_option.output)
    # N6: the test command loads only the admitted private copy.
    require(loads and installed not in loads, f"installed path never mapped {loads}")
    require(
        all(path.parent.name.startswith("chunker-admitted-") for path in loads),
        f"admitted copies only {loads}",
    )
    require("Grammar test successful" in with_option.output, with_option.output)

    config = user_config_pin_path()
    assert config is not None
    config.parent.mkdir(parents=True)
    shutil.copyfile(pins, config)
    from_config = _click(cache, "test", LANGUAGE, str(sample))
    require(from_config.exit_code == 0, from_config.output)

    empty = tmp_path / "empty.json"
    empty.write_text(_document({}), encoding="utf-8")
    never_merged = _click(cache, "test", LANGUAGE, str(sample), pins=empty)
    require(never_merged.exit_code == 1, "option replaces config, never merged")


@pytest.mark.parametrize("subcommand", ["list", "info", "validate", "cleanup"])
def test_click_defective_pin_file_exits_two_for_every_subcommand(
    isolated, tmp_path, subcommand
):
    config = user_config_pin_path()
    assert config is not None
    config.parent.mkdir(parents=True)
    config.write_text("{broken", encoding="utf-8")
    args = (
        [subcommand]
        if subcommand in {"list", "validate", "cleanup"}
        else [subcommand, LANGUAGE]
    )
    result = _click(tmp_path / "cache", *args)
    require(result.exit_code == 2, f"{subcommand}: {result.exit_code} {result.output}")
    require(
        str(config) in result.output and "not valid JSON" in result.output,
        result.output,
    )
    missing = _click(tmp_path / "cache", *args, pins=tmp_path / "absent.json")
    require(
        missing.exit_code == 2 and "file not found" in missing.output, missing.output
    )


def test_validate_compiled_grammar_admits_and_keeps_output_shape(
    isolated, tmp_path, fixture_bytes, loads
):
    cache = tmp_path / "cache"
    library = _installed(cache, fixture_bytes)
    unpinned = ComprehensiveGrammarCLI(cache)._validate_compiled_grammar(
        LANGUAGE, library, fix=False
    )
    require(unpinned["status"] == "corrupted" and not unpinned["valid"], f"{unpinned}")
    require(
        unpinned["issues"] == ["Grammar is not loadable: native admission untrusted"],
        f"{unpinned}",
    )
    pinned = ComprehensiveGrammarCLI(
        cache, trusted_artifacts={LANGUAGE: _pin(fixture_bytes)}
    )._validate_compiled_grammar(LANGUAGE, library, fix=False)
    require(pinned["status"] == "healthy" and pinned["valid"], f"{pinned}")
    require(
        set(pinned)
        == {"valid", "status", "issues", "recommendations", "fixes_applied"},
        f"{pinned}",
    )
    require(loads == [], f"N5 loads nothing in-process {loads}")


def test_build_without_pin_is_not_admitted_and_with_pin_is_probed(
    isolated, tmp_path, fixture_bytes, monkeypatch, probes, loads, capsys
):
    """N4: fresh build output is never loaded unpinned; with a pin it is probed.

    The external build tools (node, npx, the compile script) are replaced by a
    step that writes reviewed fixture output; the post-build check is real.
    """
    cache = tmp_path / "cache"
    source = cache / "grammars" / "user" / LANGUAGE
    source.mkdir(parents=True)

    def build(pins):
        tool = ComprehensiveGrammarCLI(cache, trusted_artifacts=pins)
        target = tool.build_dir / f"tree_sitter_{LANGUAGE}.so"

        def run_command(command, cwd=None, timeout=30):
            if command[0] == "python":
                target.write_bytes(fixture_bytes)
            return 0, "", ""

        monkeypatch.setattr(tool, "_run_command", run_command)
        code = tool.build_grammar(LANGUAGE, force=True)
        return code, capsys.readouterr().out

    code, out = build({})
    require(code == 0, f"unpinned build exits 0 {out}")
    require("built, not admitted: add a pin via --trusted-artifacts" in out, out)
    require(probes == [] and loads == [], f"nothing probed or loaded {probes} {loads}")

    code, out = build({LANGUAGE: _pin(fixture_bytes)})
    require(code == 0 and "Successfully built" in out, f"pinned build admitted {out}")
    require(len(probes) == 1 and loads == [], f"probed, never mapped {probes} {loads}")

    code, out = build({LANGUAGE: {"sha256": "0" * 64}})
    require(code == 1, f"failed admission exits 1 {out}")
    require("failed native admission: integrity_mismatch" in out, out)


# --- testing.py (T1, T2) ------------------------------------------------------------


def test_self_test_workflow_never_reloads_the_original_path(
    isolated, tmp_path, fixture_bytes, loads
):
    """T1 retired: parse errors come from test_parse_samples on admitted bytes."""
    from chunker.grammar_management.testing import IntegrationTester

    candidate = _candidate(tmp_path, fixture_bytes)
    sample = tmp_path / "sample.baml"
    sample.write_text(SAMPLE, encoding="utf-8")
    tester = IntegrationTester(
        tmp_path / "self-test", trusted_artifacts={LANGUAGE: _pin(fixture_bytes)}
    )
    try:
        result = tester._test_complete_workflow_local(sample, LANGUAGE, candidate)
        require(result["status"] == "pass", f"{result}")
        broken = tmp_path / "broken.baml"
        broken.write_text("class Broken {\n", encoding="utf-8")
        failed = tester._test_complete_workflow_local(broken, LANGUAGE, candidate)
        require(
            failed["errors"] == ["Sample 1: Syntax error in parse tree"], f"{failed}"
        )
    finally:
        tester.cleanup()
    require(candidate not in loads, f"original never mapped {loads}")


def test_corrupt_grammar_self_test_compares_the_admission_reason(
    isolated, tmp_path, loads
):
    """T2 retired: no in-process load of the self-written corrupt file."""
    from chunker.grammar_management.testing import IntegrationTester

    tester = IntegrationTester(tmp_path / "scenarios")
    try:
        require(tester._test_corrupt_grammar_error() is True, "admission rejects it")
    finally:
        tester.cleanup()
    require(loads == [], f"nothing loaded in-process {loads}")


# --- one trust rule (maintainer decision, 2026-11-01) --------------------------------


def test_admitted_health_honours_record_verified_package_grammars(
    isolated, tmp_path, fixture_bytes, monkeypatch
):
    """The click/validator path uses the same RECORD check as parsing."""
    import base64
    from importlib.metadata import PathDistribution

    from chunker._internal import package_supplier

    site = tmp_path / "site"
    package = site / "chunker"
    build = package / "data" / "grammars" / "build"
    build.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    name = f"lib{LANGUAGE}.so"
    shipped = build / name
    dist_info = site / "treesitter_chunker-6.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: treesitter-chunker\nVersion: 6.0.0\n",
        encoding="utf-8",
    )
    encoded = base64.urlsafe_b64encode(sha256(fixture_bytes).digest()).rstrip(b"=")
    (dist_info / "RECORD").write_text(
        f"chunker/__init__.py,,\nchunker/data/grammars/build/{name},"
        f"sha256={encoded.decode()},{len(fixture_bytes)}\n",
        encoding="utf-8",
    )
    distribution = PathDistribution(dist_info)
    monkeypatch.setattr(package_supplier, "_package_distribution", lambda: distribution)
    monkeypatch.setattr(
        package_supplier, "_package_init_file", lambda: package / "__init__.py"
    )
    package_supplier._package_grammar_records.cache_clear()
    try:
        shipped.write_bytes(fixture_bytes)
        manager = GrammarManager(
            tmp_path / "user", build, tmp_path / "cache", trusted_artifacts={}
        )
        healthy = manager.get_admitted_health(LANGUAGE)
        require(
            (healthy["status"], healthy["validation_reason"]) == ("healthy", "ok"),
            f"package-supplied without a pin {healthy}",
        )
        shipped.write_bytes(fixture_bytes + b"tampered")
        pinned = GrammarManager(
            tmp_path / "user",
            build,
            tmp_path / "cache2",
            trusted_artifacts={LANGUAGE: _pin(fixture_bytes + b"tampered")},
        )
        mismatch = pinned.get_admitted_health(LANGUAGE)
        require(
            mismatch["validation_reason"] == "integrity_mismatch",
            f"no pin rescues a RECORD mismatch {mismatch}",
        )
        advice = " ".join(mismatch["issues"])
        require("reinstall the package" in advice, f"reinstall advice {advice}")
        require("--trusted-artifacts" not in advice, f"no pin advice {advice}")
    finally:
        package_supplier._package_grammar_records.cache_clear()


# --- round-1 review of SL-core-2 ----------------------------------------------------


def _fake_package_grammar(
    tmp_path: Path, monkeypatch, name: str, data: bytes, record_bytes: bytes
) -> Path:
    import base64
    from importlib.metadata import PathDistribution

    from chunker._internal import package_supplier

    site = tmp_path / "site"
    package = site / "chunker"
    build = package / "data" / "grammars" / "build"
    build.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (build / name).write_bytes(data)
    dist_info = site / "treesitter_chunker-6.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: treesitter-chunker\nVersion: 6.0.0\n",
        encoding="utf-8",
    )
    encoded = base64.urlsafe_b64encode(sha256(record_bytes).digest()).rstrip(b"=")
    (dist_info / "RECORD").write_text(
        f"chunker/__init__.py,,\nchunker/data/grammars/build/{name},"
        f"sha256={encoded.decode()},{len(record_bytes)}\n",
        encoding="utf-8",
    )
    distribution = PathDistribution(dist_info)
    monkeypatch.setattr(package_supplier, "_package_distribution", lambda: distribution)
    monkeypatch.setattr(
        package_supplier, "_package_init_file", lambda: package / "__init__.py"
    )
    package_supplier._package_grammar_records.cache_clear()
    return build / name


def test_cached_validation_never_rescues_a_record_mismatch(
    isolated, tmp_path, fixture_bytes, monkeypatch
):
    """The trust rule runs before cache reuse (cross-path, identical bytes)."""
    from chunker._internal import package_supplier

    pins = {LANGUAGE: _pin(fixture_bytes)}
    validator = GrammarValidator(tmp_path / "cache", trusted_artifacts=pins)
    local = _candidate(tmp_path, fixture_bytes)
    require(
        validator.validate_grammar(local, LANGUAGE, ValidationLevel.BASIC).is_valid,
        "primed through an ordinary pinned local file",
    )
    try:
        shipped = _fake_package_grammar(
            tmp_path,
            monkeypatch,
            f"lib{LANGUAGE}.so",
            fixture_bytes,
            record_bytes=fixture_bytes + b"what RECORD expects",
        )
        result = validator.validate_grammar(shipped, LANGUAGE, ValidationLevel.BASIC)
        require(not result.is_valid, f"RECORD mismatch rejected {result}")
        require(
            any("integrity_mismatch" in error for error in result.errors),
            f"{result.errors}",
        )
    finally:
        package_supplier._package_grammar_records.cache_clear()


def test_pinned_failing_artifact_is_never_cached(isolated, tmp_path, probes):
    data = b"corrupt data"
    candidate = _candidate(tmp_path, data)
    cache = tmp_path / "cache"
    validator = GrammarValidator(cache, trusted_artifacts={LANGUAGE: _pin(data)})
    key, digest = validator._verdict_cache_key(
        candidate, LANGUAGE, ValidationLevel.BASIC
    )
    require(key is not None and digest == _pin(data)["sha256"], "a key exists")
    for _ in range(2):
        result = validator.validate_grammar(candidate, LANGUAGE, ValidationLevel.BASIC)
        require(not result.is_valid, f"{result.errors}")
        require(
            any("load_failed" in error for error in result.errors), f"{result.errors}"
        )
    require(not native_admission.has_verdict(key), "no admission recorded")
    require(not (cache / "validation_cache.json").exists(), "nothing stored")
    require(len(probes) == 2, f"the second call probes again {probes}")
    # GrammarRegistry discovers lib*.so on every platform today
    # (treesitter-chunker#117 belongs to ADMITFIX), so use that name here.
    user = tmp_path / "manager-user"
    user.mkdir()
    (user / f"lib{LANGUAGE}.so").write_bytes(data)
    manager = GrammarManager(
        user,
        tmp_path / "package",
        tmp_path / "cache2",
        trusted_artifacts={LANGUAGE: _pin(data)},
    )
    health = manager.get_admitted_health(LANGUAGE)
    require(
        (health["status"], health["validation_reason"]) == ("corrupted", "load_failed"),
        f"{health}",
    )


@pytest.mark.parametrize(
    ("reason", "status"),
    [
        ("ok", "healthy"),
        ("missing", "missing"),
        ("empty", "corrupted"),
        ("load_failed", "corrupted"),
        ("parse_failed", "corrupted"),
        ("untrusted", "incompatible"),
        ("integrity_mismatch", "incompatible"),
        ("timeout", "incompatible"),
        ("child_failed", "incompatible"),
        ("ack_missing", "incompatible"),
        ("ack_invalid", "incompatible"),
        ("inspect_failed", "incompatible"),
    ],
)
def test_legacy_health_status_maps_every_reason(reason, status):
    from chunker.grammar_management.core import legacy_health_status

    require(legacy_health_status(reason) == status, f"{reason} -> {status}")


def test_validate_fix_never_reports_an_unadmitted_rebuild_valid(
    isolated, tmp_path, fixture_bytes, monkeypatch, probes, capsys
):
    cache = tmp_path / "cache"
    library = _installed(cache, fixture_bytes)
    (cache / "grammars" / "user" / LANGUAGE).mkdir(parents=True)
    tool = ComprehensiveGrammarCLI(cache)
    target = tool.build_dir / f"tree_sitter_{LANGUAGE}.so"

    def run_command(command, cwd=None, timeout=30):
        if command[0] == "python":
            target.write_bytes(fixture_bytes)
        return 0, "", ""

    monkeypatch.setattr(tool, "_run_command", run_command)
    result = tool._validate_compiled_grammar(LANGUAGE, library, fix=True)
    capsys.readouterr()
    require(result["valid"] is False, f"not valid {result}")
    require(result["status"] != "fixed", f"not fixed {result}")
    require(
        result["fixes_applied"] == ["Grammar rebuilt, not admitted: untrusted"],
        f"{result}",
    )
    require(probes == [], "nothing probed without a pin")

"""Registry discovery, package supplier and parse-path pins (treesitter-chunker#362).

ADMIT SL-reg: R1-R4 load a local grammar only under its own pin (through an
admitted private copy) or when it is a RECORD-verified file of our own wheel;
``chunker.parser`` reads the user-config pin file once; a defective file grants
no local trust; and the on-demand fetch-and-build is retired (F1).

Native checks use real grammars compiled from ``packages/baml-grammar/src``
with the exported symbol renamed, so the registry (not the BAML companion)
resolves them. Pin-file locations are isolated: subprocess tests set ``HOME``,
``USERPROFILE``, ``APPDATA`` and ``XDG_CONFIG_HOME``; in-process tests redirect
``Path.home()`` and set ``APPDATA`` and ``XDG_CONFIG_HOME``.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import subprocess
import sys
import textwrap
from hashlib import sha256
from importlib.metadata import PathDistribution
from pathlib import Path

import pytest
from tree_sitter import Parser

from chunker._internal import package_supplier
from chunker._internal import registry as registry_module
from chunker._internal.registry import LanguageRegistry, default_library_path
from chunker._internal.trusted_artifacts import (
    TRUSTED_ARTIFACTS_SCHEMA,
    user_config_pin_path,
)
from chunker.exceptions import LanguageNotFoundError
from tests.test_compiled_grammar_analysis_contract import (
    FIXTURE,
    _compile_probe_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
LANGUAGE = "admitfixture"
SAMPLE = FIXTURE.read_bytes()


def require(condition: object, name: str) -> None:
    if not condition:
        raise AssertionError(name)


def _renamed_source(directory: Path, language: str) -> Path:
    unit = directory / f"{language}.c"
    unit.write_text(
        f'#define tree_sitter_baml tree_sitter_{language}\n#include "parser.c"\n',
        encoding="utf-8",
    )
    return unit


def _build(directory: Path, languages: list[str], name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    sources = [_renamed_source(directory, language) for language in languages]
    library = _compile_probe_fixture(directory, sources)
    target = directory / f"{name}{SUFFIX}"
    library.replace(target)
    return target


@pytest.fixture(scope="module")
def fixture_library(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return _build(tmp_path_factory.mktemp("single"), [LANGUAGE], LANGUAGE).read_bytes()


@pytest.fixture(scope="module")
def combined_library(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return _build(
        tmp_path_factory.mktemp("combined"), ["alpha", "beta"], "languages"
    ).read_bytes()


def _pin(data: bytes) -> dict[str, str]:
    return {"sha256": sha256(data).hexdigest()}


def _document(artifacts: dict[str, object]) -> str:
    return json.dumps({"schema": TRUSTED_ARTIFACTS_SCHEMA, "artifacts": artifacts})


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    env = {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "XDG_CONFIG_HOME": str(home / "xdg"),
    }
    # In-process: redirect Path.home() and set APPDATA/XDG_CONFIG_HOME, but
    # leave the process HOME/USERPROFILE alone (on Windows the language-pack's
    # native cache lookup breaks for the rest of the process otherwise).
    # Subprocess tests receive all four in ``env``.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("APPDATA", env["APPDATA"])
    monkeypatch.setenv("XDG_CONFIG_HOME", env["XDG_CONFIG_HOME"])
    monkeypatch.delenv("CHUNKER_GRAMMAR_BUILD_DIR", raising=False)
    package_supplier._package_grammar_records.cache_clear()
    return env


def _write_config(text: str) -> Path:
    path = user_config_pin_path()
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _record_loads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    loads: list[Path] = []
    real = registry_module.ctypes.CDLL

    def recording(name, *args, **kwargs):
        loads.append(Path(name))
        return real(name, *args, **kwargs)

    monkeypatch.setattr(registry_module.ctypes, "CDLL", recording)
    return loads


def _parses(language) -> bool:
    tree = Parser(language).parse(SAMPLE)
    return tree.root_node is not None and not tree.root_node.has_error


# --- parse path (chunker.parser) in a fresh process ---------------------------------

PARSE_SCRIPT = textwrap.dedent(
    """
    import json, sys
    from chunker.parser import get_parser, acquire_parser
    out = {}
    for name in sys.argv[2:]:
        try:
            parser = get_parser(name)
            tree = parser.parse(open(sys.argv[1], "rb").read() if name != "python" else b"x = 1\\n")
            out[name] = {"ok": not tree.root_node.has_error}
        except Exception as error:
            out[name] = {"error": type(error).__name__, "message": str(error)}
    print(json.dumps(out))
    """
)


def _parse_in_process(isolated, build_dir: Path, cwd: Path, *languages: str):
    env = {**os.environ, **isolated, "CHUNKER_GRAMMAR_BUILD_DIR": str(build_dir)}
    # The child imports this checkout, not whichever one an editable install
    # points at.
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", PARSE_SCRIPT, str(FIXTURE), *languages],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    require(completed.returncode == 0, f"child failed {completed.stderr}")
    return json.loads(completed.stdout.strip().splitlines()[-1]), completed.stderr


def test_pinned_local_grammar_parses_through_get_parser(
    isolated, tmp_path, fixture_library
):
    build = tmp_path / "build"
    build.mkdir()
    (build / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_library)
    _write_config(_document({LANGUAGE: _pin(fixture_library)}))
    result, _ = _parse_in_process(isolated, build, tmp_path, LANGUAGE, "python")
    require(result[LANGUAGE] == {"ok": True}, f"pinned fixture parses {result}")
    require(result["python"] == {"ok": True}, f"official python {result}")


def test_unpinned_local_grammar_is_ignored_by_get_parser(
    isolated, tmp_path, fixture_library
):
    build = tmp_path / "build"
    build.mkdir()
    candidate = build / f"{LANGUAGE}{SUFFIX}"
    candidate.write_bytes(fixture_library)
    result, _ = _parse_in_process(isolated, build, tmp_path, LANGUAGE)
    outcome = result[LANGUAGE]
    require(outcome.get("error") == "LanguageNotFoundError", f"ignored {outcome}")
    require(str(candidate) in outcome["message"], "names the candidate")
    require("untrusted" in outcome["message"], f"names the cause {outcome}")


def test_defective_config_keeps_package_grammars_and_names_the_defect(
    isolated, tmp_path, fixture_library
):
    build = tmp_path / "build"
    build.mkdir()
    (build / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_library)
    config = _write_config("{broken")
    result, stderr = _parse_in_process(isolated, build, tmp_path, "python", LANGUAGE)
    require(result["python"] == {"ok": True}, f"package-supplied grammar {result}")
    outcome = result[LANGUAGE]
    require(outcome.get("error") == "LanguageNotFoundError", f"untrusted {outcome}")
    require(
        str(config) in outcome["message"] and "not valid JSON" in outcome["message"],
        f"error names file and defect {outcome}",
    )
    require(stderr.count("grants no local trust") == 1, f"one warning {stderr!r}")


def test_on_demand_fetch_and_build_is_retired(isolated, tmp_path, monkeypatch):
    """F1: a miss raises without cloning or compiling (wasm has a source URL)."""
    sources = json.loads((ROOT / "config" / "grammar_sources.json").read_text("utf-8"))
    require("wasm" in sources, "the probe language has a configured source")
    from chunker import parser as parser_module
    from chunker.grammar import manager as manager_module

    constructed = []
    monkeypatch.setattr(
        manager_module,
        "TreeSitterGrammarManager",
        lambda *args, **kwargs: constructed.append(args) or pytest.fail("built"),
    )
    state = parser_module._ParserState()
    state.default_library_path = tmp_path / f"missing{SUFFIX}"
    monkeypatch.setattr(parser_module, "_state", state)
    monkeypatch.chdir(tmp_path)
    for call in (parser_module.get_parser, parser_module.acquire_parser):
        with pytest.raises(LanguageNotFoundError):
            call("wasm")
    require(constructed == [], "no grammar manager")
    require(not (tmp_path / "grammars").exists(), "nothing cloned into cwd")
    require(not (tmp_path / "build").exists(), "nothing built into cwd")


# --- registry discovery under pins ------------------------------------------------


def test_registry_constructor_never_reads_config(
    isolated, tmp_path, fixture_library, monkeypatch
):
    build = tmp_path / "build"
    build.mkdir()
    candidate = build / f"{LANGUAGE}{SUFFIX}"
    candidate.write_bytes(fixture_library)
    _write_config(_document({LANGUAGE: _pin(fixture_library)}))
    loads = _record_loads(monkeypatch)
    for pins in (None, {}):
        registry = LanguageRegistry(build / f"missing{SUFFIX}", trusted_artifacts=pins)
        with pytest.raises(LanguageNotFoundError) as caught:
            registry.get_language(LANGUAGE)
        require("untrusted" in str(caught.value), f"{pins!r}: {caught.value}")
    require(loads == [], f"nothing loaded {loads}")


def test_pinned_individual_library_loads_only_its_admitted_copy(
    isolated, tmp_path, fixture_library, monkeypatch
):
    build = tmp_path / "build"
    build.mkdir()
    candidate = build / f"{LANGUAGE}{SUFFIX}"
    candidate.write_bytes(fixture_library)
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(
        build / f"missing{SUFFIX}",
        trusted_artifacts={LANGUAGE: _pin(fixture_library)},
    )
    require(_parses(registry.get_language(LANGUAGE)), "pinned fixture parses")
    require(loads, "a library was loaded")
    require(candidate not in loads, f"candidate never mapped {loads}")
    require(
        all(path.parent.name.startswith("chunker-admitted-") for path in loads),
        f"only admitted copies {loads}",
    )
    require(
        all(path.read_bytes() == fixture_library for path in loads), "approved bytes"
    )


def test_wrong_pin_rejects_local_library(
    isolated, tmp_path, fixture_library, monkeypatch
):
    build = tmp_path / "build"
    build.mkdir()
    (build / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_library)
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(
        build / f"missing{SUFFIX}",
        trusted_artifacts={LANGUAGE: {"sha256": "0" * 64}},
    )
    with pytest.raises(LanguageNotFoundError, match="integrity_mismatch"):
        registry.get_language(LANGUAGE)
    require(loads == [], "no load")


def test_combined_library_admits_each_language_on_its_own_pin(
    isolated, tmp_path, combined_library, monkeypatch
):
    """Rule 5: mapping a combined library for one language admits no other."""
    directory = tmp_path / "combined"
    directory.mkdir()
    combined = directory / f"languages{SUFFIX}"
    combined.write_bytes(combined_library)
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(
        combined, trusted_artifacts={"alpha": _pin(combined_library)}
    )
    require(_parses(registry.get_language("alpha")), "alpha parses")
    with pytest.raises(LanguageNotFoundError):
        registry.get_language("beta")
    require(combined not in loads, f"combined library never mapped whole {loads}")

    both = LanguageRegistry(
        combined,
        trusted_artifacts={
            "alpha": _pin(combined_library),
            "beta": _pin(combined_library),
        },
    )
    require(_parses(both.get_language("beta")), "beta with its own pin")


def test_individual_libraries_are_admitted_per_requested_language(
    isolated, tmp_path, combined_library, monkeypatch
):
    """Rule 5 for per-language files: a pin admits only its own language.

    ``alpha`` and ``beta`` are identical bytes exporting both symbols, so the
    ``alpha`` pin's digest matches ``beta`` too; ``beta`` still has no pin.
    """
    build = tmp_path / "build"
    build.mkdir()
    (build / f"alpha{SUFFIX}").write_bytes(combined_library)
    (build / f"beta{SUFFIX}").write_bytes(combined_library)
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(
        build / f"missing{SUFFIX}",
        trusted_artifacts={"alpha": _pin(combined_library)},
    )
    require(_parses(registry.get_language("alpha")), "alpha parses")
    before = list(loads)
    with pytest.raises(LanguageNotFoundError) as caught:
        registry.get_language("beta")
    require("untrusted" in str(caught.value), f"beta has no pin: {caught.value}")
    require(loads == before, f"nothing loaded for beta {loads[len(before) :]}")


def test_individual_library_pin_is_keyed_by_requested_language(
    isolated, tmp_path, monkeypatch
):
    """R4: a filename variant (``my-lang``) is found for ``my_lang``, but the
    pin consulted is the requested language's, never the variant's."""
    build = tmp_path / "build"
    library = _build(build, ["my_lang"], "my-lang")
    data = library.read_bytes()
    variant = LanguageRegistry(
        build / f"missing{SUFFIX}", trusted_artifacts={"my-lang": _pin(data)}
    )
    with pytest.raises(LanguageNotFoundError) as caught:
        variant.get_language("my_lang")
    require("untrusted" in str(caught.value), f"variant pin ignored {caught.value}")
    # The directory scan may admit the file under its own stem's pin, but that
    # registers no ``my_lang``.
    require(not variant.has_language("my_lang"), "my_lang stays unavailable")
    requested = LanguageRegistry(
        build / f"missing{SUFFIX}", trusted_artifacts={"my_lang": _pin(data)}
    )
    require(_parses(requested.get_language("my_lang")), "requested-language pin")


def test_relative_library_path_is_made_absolute(
    isolated, tmp_path, fixture_library, monkeypatch
):
    """A relative library path still finds and admits its sibling grammar."""
    from chunker import parser as parser_module

    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_library)
    _write_config(_document({LANGUAGE: _pin(fixture_library)}))
    monkeypatch.chdir(tmp_path)
    state = parser_module._ParserState()
    monkeypatch.setattr(parser_module, "_state", state)
    parser_module._initialize(Path("lib") / f"missing{SUFFIX}")
    require(state.registry is not None, "initialized")
    require(state.registry._library_path.is_absolute(), "absolute library path")
    tree = parser_module.get_parser(LANGUAGE).parse(SAMPLE)
    require(not tree.root_node.has_error, "relative library path parses")


def test_relative_build_dir_override_is_made_absolute(
    isolated, tmp_path, fixture_library
):
    """A relative ``CHUNKER_GRAMMAR_BUILD_DIR`` is resolved against the cwd."""
    work = tmp_path / "work"
    (work / "grammars").mkdir(parents=True)
    (work / "grammars" / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_library)
    _write_config(_document({LANGUAGE: _pin(fixture_library)}))
    result, _ = _parse_in_process(isolated, Path("grammars"), work, LANGUAGE)
    require(result[LANGUAGE] == {"ok": True}, f"relative override parses {result}")


def test_pin_file_beside_a_custom_library_is_refused(
    isolated, tmp_path, fixture_library, monkeypatch
):
    """The parse path passes its library path to the pin reader, so a pin file
    in the custom library's (tool-written) directory grants nothing."""
    from chunker import parser as parser_module
    from chunker._internal import trusted_artifacts

    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_library)
    planted = lib / "trusted-artifacts.json"
    planted.write_text(_document({LANGUAGE: _pin(fixture_library)}), "utf-8")
    monkeypatch.setattr(trusted_artifacts, "user_config_pin_path", lambda: planted)
    loads = _record_loads(monkeypatch)
    state = parser_module._ParserState()
    monkeypatch.setattr(parser_module, "_state", state)
    parser_module._initialize(lib / f"languages{SUFFIX}")
    with pytest.raises(LanguageNotFoundError) as caught:
        parser_module.get_parser(LANGUAGE)
    message = str(caught.value)
    require(str(planted) in message, f"names the refused pin file {message}")
    require("grants no local trust" in message, f"no trust {message}")
    require(loads == [], f"nothing loaded {loads}")


# --- package-supplied grammars of our own wheel (EC-ADMIT-7) --------------------------


def _fake_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, bytes],
    *,
    record: dict[str, bytes | None] | None = None,
) -> Path:
    """Install-like tree: site/chunker/... plus a dist-info with a RECORD."""
    site = tmp_path / "site"
    package = site / "chunker"
    build = package / "data" / "grammars" / "build"
    build.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name, data in files.items():
        (build / name).write_bytes(data)
    dist_info = site / "treesitter_chunker-6.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: treesitter-chunker\nVersion: 6.0.0\n",
        encoding="utf-8",
    )
    rows = ["chunker/__init__.py,,"]
    for entry, data in (record if record is not None else dict(files.items())).items():
        name = entry if "/" in entry else f"chunker/data/grammars/build/{entry}"
        if data is None:
            rows.append(f"{name},,")
        else:
            digest = base64.urlsafe_b64encode(sha256(data).digest()).rstrip(b"=")
            rows.append(f"{name},sha256={digest.decode()},{len(data)}")
    (dist_info / "RECORD").write_text("\n".join(rows) + "\n", encoding="utf-8")
    distribution = PathDistribution(dist_info)
    monkeypatch.setattr(package_supplier, "_package_distribution", lambda: distribution)
    monkeypatch.setattr(
        package_supplier, "_package_init_file", lambda: package / "__init__.py"
    )
    monkeypatch.setattr(registry_module, "package_grammar_build_dir", lambda: build)
    package_supplier._package_grammar_records.cache_clear()
    return build


def test_record_verified_package_grammar_loads_without_pin(
    isolated, tmp_path, fixture_library, monkeypatch
):
    build = _fake_distribution(
        tmp_path, monkeypatch, {f"{LANGUAGE}{SUFFIX}": fixture_library}
    )
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(tmp_path / f"missing{SUFFIX}", trusted_artifacts={})
    require(_parses(registry.get_language(LANGUAGE)), "package grammar parses")
    require(set(loads) == {build / f"{LANGUAGE}{SUFFIX}"}, f"loaded in place {loads}")


def test_package_grammar_mismatching_record_fails_closed_even_with_pin(
    isolated, tmp_path, fixture_library, monkeypatch
):
    tampered = fixture_library + b"appended after install"
    build = _fake_distribution(
        tmp_path,
        monkeypatch,
        {f"{LANGUAGE}{SUFFIX}": tampered},
        record={f"{LANGUAGE}{SUFFIX}": fixture_library},
    )
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(
        tmp_path / f"missing{SUFFIX}", trusted_artifacts={LANGUAGE: _pin(tampered)}
    )
    with pytest.raises(LanguageNotFoundError, match="integrity_mismatch"):
        registry.get_language(LANGUAGE)
    require(loads == [], f"never loaded {loads}")
    require(build.joinpath(f"{LANGUAGE}{SUFFIX}").read_bytes() == tampered, "untouched")


@pytest.mark.parametrize("case", ["no_entry", "no_hash", "other_algorithm"])
def test_package_dir_file_without_record_hash_is_an_ordinary_candidate(
    isolated, tmp_path, fixture_library, monkeypatch, case
):
    name = f"{LANGUAGE}{SUFFIX}"
    if case == "no_entry":
        record: dict[str, bytes | None] = {}
    elif case == "no_hash":
        record = {name: None}
    else:
        record = {name: fixture_library}
    build = _fake_distribution(
        tmp_path, monkeypatch, {name: fixture_library}, record=record
    )
    if case == "other_algorithm":
        record_file = next(tmp_path.joinpath("site").glob("*.dist-info")) / "RECORD"
        record_file.write_text(
            record_file.read_text("utf-8").replace("sha256=", "md5="), encoding="utf-8"
        )
        package_supplier._package_grammar_records.cache_clear()
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(tmp_path / f"missing{SUFFIX}", trusted_artifacts={})
    with pytest.raises(LanguageNotFoundError, match="untrusted"):
        registry.get_language(LANGUAGE)
    require(loads == [], f"{case}: never loaded without a pin {loads}")
    pinned = LanguageRegistry(
        tmp_path / f"missing{SUFFIX}",
        trusted_artifacts={LANGUAGE: _pin(fixture_library)},
    )
    require(_parses(pinned.get_language(LANGUAGE)), f"{case}: pinned copy parses")
    require(build / name not in loads, f"{case}: the file itself is never mapped")


def test_record_entries_outside_the_exact_directory_are_ignored(
    isolated, tmp_path, fixture_library, monkeypatch
):
    name = f"{LANGUAGE}{SUFFIX}"
    _fake_distribution(
        tmp_path,
        monkeypatch,
        {name: fixture_library},
        record={
            f"chunker/data/grammars/build/../build/{name}": fixture_library,
            f"chunker/data/grammars/{name}": fixture_library,
        },
    )
    registry = LanguageRegistry(tmp_path / f"missing{SUFFIX}", trusted_artifacts={})
    with pytest.raises(LanguageNotFoundError, match="untrusted"):
        registry.get_language(LANGUAGE)


def test_shadowing_distribution_supplies_nothing(
    isolated, tmp_path, fixture_library, monkeypatch
):
    _fake_distribution(tmp_path, monkeypatch, {f"{LANGUAGE}{SUFFIX}": fixture_library})
    other = tmp_path / "other" / "chunker" / "__init__.py"
    other.parent.mkdir(parents=True)
    other.write_text("", encoding="utf-8")
    monkeypatch.setattr(package_supplier, "_package_init_file", lambda: other)
    package_supplier._package_grammar_records.cache_clear()
    registry = LanguageRegistry(tmp_path / f"missing{SUFFIX}", trusted_artifacts={})
    with pytest.raises(LanguageNotFoundError, match="untrusted"):
        registry.get_language(LANGUAGE)


@pytest.mark.skipif(os.name == "nt", reason="directory symlinks need privileges")
def test_package_identity_survives_symlinked_site_path(
    isolated, tmp_path, fixture_library, monkeypatch
):
    build = _fake_distribution(
        tmp_path, monkeypatch, {f"{LANGUAGE}{SUFFIX}": fixture_library}
    )
    alias = tmp_path / "site-alias"
    alias.symlink_to(tmp_path / "site", target_is_directory=True)
    aliased_build = alias / build.relative_to(tmp_path / "site")
    monkeypatch.setattr(
        registry_module, "package_grammar_build_dir", lambda: aliased_build
    )
    registry = LanguageRegistry(tmp_path / f"missing{SUFFIX}", trusted_artifacts={})
    require(_parses(registry.get_language(LANGUAGE)), "symlinked path still supplied")


def test_package_supplied_symlink_candidate_is_not_supplied(
    isolated, tmp_path, fixture_library, monkeypatch
):
    if os.name == "nt":
        pytest.skip("file symlinks need privileges on Windows")
    build = _fake_distribution(
        tmp_path, monkeypatch, {f"{LANGUAGE}{SUFFIX}": fixture_library}
    )
    link = tmp_path / f"link{SUFFIX}"
    link.symlink_to(build / f"{LANGUAGE}{SUFFIX}")
    require(
        registry_module.package_supplied_digest(link) == ("local", None),
        "a symlink never counts",
    )


# --- small interfaces ---------------------------------------------------------------


def test_universal_registry_forwards_pins(tmp_path, monkeypatch):
    from chunker.grammar.registry import UniversalLanguageRegistry

    pins = {LANGUAGE: {"sha256": "a" * 64}}
    universal = UniversalLanguageRegistry(
        tmp_path / f"missing{SUFFIX}",
        discovery_service=object(),
        download_service=object(),
        cache_dir=tmp_path / "cache",
        trusted_artifacts=pins,
    )
    pins[LANGUAGE]["sha256"] = "b" * 64
    require(
        universal._base_registry._trusted_artifacts == {LANGUAGE: {"sha256": "a" * 64}},
        "forwarded and copied",
    )


def test_default_library_path_matches_parse_path():
    from chunker import parser as parser_module

    require(
        parser_module._ParserState().default_library_path == default_library_path(),
        "one definition of the default combined library",
    )
    require(default_library_path().suffix == SUFFIX, "platform suffix")


def test_ctypes_is_only_reached_through_admission(monkeypatch, tmp_path, isolated):
    """A library outside every source is neither hashed into trust nor loaded."""
    stray = tmp_path / f"stray{SUFFIX}"
    stray.write_bytes(b"not approved")
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(stray, trusted_artifacts={})
    registry.list_languages()
    require(loads == [], f"no load of an unpinned combined library {loads}")
    require(ctypes is registry_module.ctypes, "same module")


def test_discovery_scan_never_loads_unpinned_library(
    monkeypatch, tmp_path, isolated, fixture_library
):
    """R2: scan directories confer no trust; discovery maps nothing unpinned."""
    build = tmp_path / "build"
    build.mkdir()
    (build / f"{LANGUAGE}{SUFFIX}").write_bytes(fixture_library)
    loads = _record_loads(monkeypatch)
    registry = LanguageRegistry(build / f"missing{SUFFIX}", trusted_artifacts={})
    require(LANGUAGE not in registry.list_languages(), "not discovered")
    require(loads == [], f"discovery loaded nothing {loads}")
    require(
        any("untrusted" in note for note in registry._local_rejections[LANGUAGE]),
        "rejection recorded",
    )

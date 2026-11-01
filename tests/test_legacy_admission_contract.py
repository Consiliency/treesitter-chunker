"""Legacy native-load sites under the admission contract (treesitter-chunker#362).

ADMIT SL-legacy: the legacy ``TreeSitterGrammarValidator`` is retired
(treesitter-chunker#400, inventory V1), ``GrammarDownloadManager.validate_grammar``
is retired (D1), and the legacy combined-library
``chunker.grammar_manager.GrammarManager.get_available_languages`` admits each
pinned language through ``probe_native_grammar`` without mapping the library in
this process (M1). Native checks use real grammars compiled from
``packages/baml-grammar/src`` with renamed symbols.
"""

from __future__ import annotations

import ctypes
from hashlib import sha256
from pathlib import Path

import pytest

from tests.test_compiled_grammar_analysis_contract import _compile_probe_fixture


def _build(directory: Path, languages: list[str], name: str) -> Path:
    """Compile the BAML parser once per language, with renamed exported symbols."""
    sources = []
    for language in languages:
        unit = directory / f"{language}.c"
        unit.write_text(
            f'#define tree_sitter_baml tree_sitter_{language}\n#include "parser.c"\n',
            encoding="utf-8",
        )
        sources.append(unit)
    library = _compile_probe_fixture(directory, sources)
    return library.replace(directory / f"{name}{library.suffix}")


def require(condition: object, name: str) -> None:
    if not condition:
        raise AssertionError(name)


@pytest.fixture(scope="module")
def combined(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return _build(
        tmp_path_factory.mktemp("legacy"), ["alpha", "beta"], "languages"
    ).read_bytes()


@pytest.fixture
def no_parent_loads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fail on any in-process ``ctypes`` library load."""
    loads: list[str] = []

    def refuse(name, *args, **kwargs):
        loads.append(str(name))
        raise AssertionError(f"in-process native load of {name}")

    monkeypatch.setattr(ctypes, "CDLL", refuse)
    monkeypatch.setattr(ctypes.cdll, "LoadLibrary", refuse)
    return loads


def test_legacy_validator_is_retired_and_names_its_replacement(
    tmp_path, combined, no_parent_loads
):
    from chunker.grammar import TreeSitterGrammarValidator as ExportedValidator
    from chunker.grammar.validator import (
        RETIREMENT_MESSAGE,
        TreeSitterGrammarValidator,
        ValidationError,
    )

    require(
        ExportedValidator is TreeSitterGrammarValidator,
        "still importable from chunker.grammar",
    )
    with pytest.raises(ValidationError) as caught:
        TreeSitterGrammarValidator()
    message = str(caught.value)
    require("chunker.grammar_management.core.GrammarValidator" in message, message)
    require("probe_native_grammar" in message, message)
    # The instance methods are reachable without the constructor (for example
    # through a subclass); each raises the same retirement error.
    unconstructed = object.__new__(TreeSitterGrammarValidator)
    for call in (
        lambda: unconstructed.validate_node_types("python", {"module"}),
        lambda: unconstructed.test_parse("python", "x = 1\n"),
        lambda: unconstructed.validate_grammar_features("python"),
    ):
        with pytest.raises(
            ValidationError, match="TreeSitterGrammarValidator is retired"
        ):
            call()
    library = tmp_path / "libalpha.so"
    library.write_bytes(combined)
    require(
        TreeSitterGrammarValidator.check_abi_compatibility(library)
        == (False, RETIREMENT_MESSAGE),
        "static check is retired",
    )
    require(no_parent_loads == [], "no native load")


def test_download_validate_grammar_is_retired(tmp_path, combined, no_parent_loads):
    from chunker.grammar.download import (
        VALIDATE_GRAMMAR_RETIRED,
        GrammarDownloadManager,
    )

    library = tmp_path / "alpha.so"
    library.write_bytes(combined)
    require(
        GrammarDownloadManager.validate_grammar(library)
        == (False, VALIDATE_GRAMMAR_RETIRED),
        "retired",
    )
    require(
        GrammarDownloadManager.validate_grammar(tmp_path / "absent.so")
        == (False, "Grammar file does not exist"),
        "non-native checks kept",
    )
    require("probe_native_grammar" in VALIDATE_GRAMMAR_RETIRED, "names the replacement")
    require(no_parent_loads == [], "no native load")


def _legacy_manager(tmp_path: Path, data: bytes, pins):
    from chunker.grammar_manager import GrammarManager

    config = tmp_path / "config" / "grammar_sources.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        '{"alpha": "https://github.com/example/tree-sitter-alpha"}', encoding="utf-8"
    )
    manager = GrammarManager(
        root_dir=tmp_path, config_file=config, trusted_artifacts=pins
    )
    manager._lib_path.write_bytes(data)
    (tmp_path / "grammars" / "tree-sitter-beta").mkdir(parents=True, exist_ok=True)
    return manager


def test_legacy_combined_library_admits_each_pinned_language(
    tmp_path, combined, no_parent_loads
):
    digest = {"sha256": sha256(combined).hexdigest()}
    require(
        _legacy_manager(tmp_path / "none", combined, None).get_available_languages()
        == set(),
        "no pins: nothing, not even configured or directory names",
    )
    require(
        _legacy_manager(
            tmp_path / "alpha", combined, {"alpha": digest}
        ).get_available_languages()
        == {"alpha"},
        "rule 5: pinning alpha admits no other language",
    )
    require(
        _legacy_manager(
            tmp_path / "both", combined, {"alpha": digest, "beta": digest}
        ).get_available_languages()
        == {"alpha", "beta"},
        "each language on its own pin",
    )
    require(
        _legacy_manager(
            tmp_path / "wrong", combined, {"alpha": {"sha256": "0" * 64}}
        ).get_available_languages()
        == set(),
        "a mismatched pin admits nothing",
    )
    require(
        _legacy_manager(
            tmp_path / "gamma", combined, {"gamma": digest}
        ).get_available_languages()
        == set(),
        "a pinned language without its own symbol is not admitted",
    )
    require(no_parent_loads == [], "the library is never mapped in this process")

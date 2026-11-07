"""Unsupported global selection constraints are rejected (treesitter-chunker#344).

``SmartSelector.select_multiple_grammars`` accepted ``global_constraints`` and
returned the unconstrained selections unchanged. No cross-language constraint
has defined semantics, so a nonempty mapping is now rejected before any
selection runs. Named mutation ``M344-ignore`` (accept and ignore the mapping,
the old behavior) fails the rejection cases.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    SmartSelector,
)
from chunker.grammar_management.core import (
    GrammarManager,
    GrammarPriority,
    load_compiled_grammar,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
GRAMMAR_SRC = ROOT / "packages/baml-grammar/src"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="The checked-in BAML grammar builds as a Linux shared library",
)


@pytest.fixture
def selector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A selector over real USER and PACKAGE BAML artifacts."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    libraries = []
    for name in ("user", "package"):
        directory = tmp_path / name
        directory.mkdir()
        library = directory / "libbaml.so"
        subprocess.run(
            [
                "cc",
                "-shared",
                "-fPIC",
                "-O2",
                "-I",
                str(GRAMMAR_SRC),
                str(GRAMMAR_SRC / "parser.c"),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        tree = load_compiled_grammar(library, "baml").parse(FIXTURE.read_bytes())
        assert not tree.root_node.has_error
        libraries.append(library)
    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    return SmartSelector(manager, CompatibilityChecker(manager)), set(libraries)


@pytest.mark.parametrize(
    "constraints",
    [
        {"max_total_parse_time": 0.0},
        {"same_priority": True, "max_parse_time": 0.0},
        {"prefer": GrammarPriority.USER},
    ],
)
def test_nonempty_global_constraints_are_rejected_before_selection(
    selector, constraints
) -> None:
    smart, _libraries = selector
    registry = smart.grammar_manager._registry
    with pytest.raises(ValueError, match="does not support global constraints") as e:
        smart.select_multiple_grammars(["baml"], global_constraints=constraints)
    for key in constraints:
        assert str(key) in str(e.value)
    # Rejected before any selection: discovery never ran.
    assert registry._registry_cache == {}
    assert registry._cache_timestamp == 0


@pytest.mark.parametrize("constraints", [None, {}])
def test_absent_global_constraints_select_real_artifacts(selector, constraints) -> None:
    smart, libraries = selector
    selections = smart.select_multiple_grammars(
        ["baml", "not-installed"], global_constraints=constraints
    )
    assert set(selections) == {"baml", "not-installed"}
    assert selections["not-installed"] is None
    assert selections["baml"] is not None
    assert selections["baml"].grammar_path in libraries

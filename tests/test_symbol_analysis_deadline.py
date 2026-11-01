"""Symbol analysis reports why its symbol lists are empty (treesitter-chunker#207).

Under CPU load the five-second ``nm`` deadline could expire, and the analyzer
returned the same empty lists as a grammar with no symbols. Every outcome now
carries an ``analysis`` status. The real ``nm`` runs against a real compiled
BAML grammar; the deadline case kills it with a deadline it cannot meet.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from chunker.languages.compatibility.grammar_analyzer import GrammarAnalyzer

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"
SYMBOL_LISTS = ("functions", "constants", "data", "undefined")

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Analyzer inspects ELF .so symbols with nm"
)


@pytest.fixture(scope="module")
def baml_library(tmp_path_factory: pytest.TempPathFactory) -> Path:
    library = tmp_path_factory.mktemp("baml") / "baml.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(SOURCE),
            str(SOURCE / "parser.c"),
            "-o",
            str(library),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    return library


def _analyzer(directory: Path) -> GrammarAnalyzer:
    return GrammarAnalyzer(directory)


def _counts(symbols: dict) -> int:
    return sum(len(symbols[name]) for name in SYMBOL_LISTS)


def test_completed_analysis_reports_symbols(baml_library: Path) -> None:
    symbols = _analyzer(baml_library.parent).analyze_grammar_symbols(baml_library)

    assert symbols["analysis"] == {
        "status": "complete",
        "deadline_seconds": 5.0,
        "detail": "nm completed",
    }
    assert "tree_sitter_baml" in symbols["functions"]
    assert _counts(symbols) > 0


def test_deadline_expiry_is_reported_not_counted_as_no_symbols(
    baml_library: Path,
) -> None:
    symbols = _analyzer(baml_library.parent).analyze_grammar_symbols(
        baml_library, timeout=1e-6
    )

    assert symbols["analysis"]["status"] == "deadline_expired"
    assert symbols["analysis"]["deadline_seconds"] == 1e-6
    assert "deadline" in symbols["analysis"]["detail"]
    assert _counts(symbols) == 0


def test_missing_nm_is_unavailable(
    baml_library: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    symbols = _analyzer(baml_library.parent).analyze_grammar_symbols(baml_library)

    assert symbols["analysis"]["status"] == "unavailable"
    assert symbols["analysis"]["detail"] == "nm command not found"
    assert _counts(symbols) == 0


def test_unreadable_artifact_is_failed(tmp_path: Path) -> None:
    artifact = tmp_path / "not-elf.so"
    artifact.write_bytes(b"not an ELF object\n")
    symbols = _analyzer(tmp_path).analyze_grammar_symbols(artifact)

    assert symbols["analysis"]["status"] == "failed"
    assert symbols["analysis"]["detail"]
    assert _counts(symbols) == 0

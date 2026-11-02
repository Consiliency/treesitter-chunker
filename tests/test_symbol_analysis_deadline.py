"""Symbol analysis reports why its symbol lists are empty (treesitter-chunker#207).

Under CPU load the five-second ``nm`` deadline could expire, and the analyzer
returned the same empty lists as a grammar with no symbols. Every outcome now
carries an ``analysis`` status. The real ``nm`` runs against a real compiled
BAML grammar; the deadline case kills it with a deadline it cannot meet.

The default five-second run can itself expire on a loaded CI runner
(treesitter-chunker#592). That expiry is a reported outcome, not a failure, so
the completion check confirms it once under the load-tolerant bound, as the
other #207/#143 tests do. Only ``deadline_expired`` is re-checked; ``failed``
and ``unavailable`` never are.
"""

from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from chunker.languages.compatibility.grammar_analyzer import GrammarAnalyzer
from tests.language_smoke import LOAD_TOLERANT_DEADLINE_SECONDS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"
SYMBOL_LISTS = ("functions", "constants", "data", "undefined")
DEFAULT_DEADLINE_SECONDS = 5.0
# The CI smoke runs under ``--timeout=60``. A confirmed expiry costs up to 50 s
# (the 5 s default run plus the 45 s confirmation), and the module-scoped
# ``cc`` build of the BAML grammar counts toward whichever test requests it
# first, so the confirming tests get a larger budget. A real hang still trips
# it (treesitter-chunker#592).
RECHECK_TIMEOUT = pytest.mark.timeout(150)

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


def _analyze_with_confirmation(
    analyzer: GrammarAnalyzer, library: Path, *, first_timeout: float | None = None
) -> tuple[dict, dict | None]:
    """Analyze ``library``; confirm a deadline expiry once under load tolerance.

    Returns the first result and, only when it reported ``deadline_expired``,
    the confirmation run. ``first_timeout=None`` uses the analyzer's default.
    """
    if first_timeout is None:
        first = analyzer.analyze_grammar_symbols(library)
    else:
        first = analyzer.analyze_grammar_symbols(library, timeout=first_timeout)
    if first["analysis"]["status"] != "deadline_expired":
        return first, None
    warnings.warn(
        f"{first['analysis']['detail']}; confirming under the "
        f"{LOAD_TOLERANT_DEADLINE_SECONDS:g}-second bound (treesitter-chunker#592)",
        stacklevel=2,
    )
    confirmed = analyzer.analyze_grammar_symbols(
        library, timeout=LOAD_TOLERANT_DEADLINE_SECONDS
    )
    return first, confirmed


def _assert_complete(symbols: dict, deadline: float) -> None:
    assert symbols["analysis"] == {
        "status": "complete",
        "deadline_seconds": deadline,
        "detail": "nm completed",
    }
    assert "tree_sitter_baml" in symbols["functions"]
    assert _counts(symbols) > 0


def _assert_expired(symbols: dict, deadline: float) -> None:
    assert symbols["analysis"] == {
        "status": "deadline_expired",
        "deadline_seconds": deadline,
        "detail": f"nm exceeded the {deadline:g}-second deadline",
    }
    assert _counts(symbols) == 0


def _check_completed(analyzer: GrammarAnalyzer, library: Path) -> None:
    first, confirmed = _analyze_with_confirmation(analyzer, library)

    if confirmed is None:
        _assert_complete(first, DEFAULT_DEADLINE_SECONDS)
    else:
        # The default deadline expired under host load: reported as such, with
        # no symbols counted, and the confirmation must then find them.
        _assert_expired(first, DEFAULT_DEADLINE_SECONDS)
        _assert_complete(confirmed, LOAD_TOLERANT_DEADLINE_SECONDS)


@RECHECK_TIMEOUT
def test_completed_analysis_reports_symbols(baml_library: Path) -> None:
    _check_completed(_analyzer(baml_library.parent), baml_library)


@RECHECK_TIMEOUT
def test_completed_check_accepts_a_confirmed_default_expiry(
    baml_library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run the loaded-host branch on every CI run.

    The first analysis reports exactly what the analyzer reports when its
    default five-second run expires; the confirmation is the real ``nm``.
    """
    analyzer = _analyzer(baml_library.parent)
    real = analyzer.analyze_grammar_symbols
    calls: list[dict] = []

    def first_call_expires(path: Path, **kwargs) -> dict:
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                **{name: [] for name in SYMBOL_LISTS},
                "analysis": {
                    "status": "deadline_expired",
                    "deadline_seconds": DEFAULT_DEADLINE_SECONDS,
                    "detail": "nm exceeded the 5-second deadline",
                },
            }
        return real(path, **kwargs)

    monkeypatch.setattr(analyzer, "analyze_grammar_symbols", first_call_expires)
    with pytest.warns(UserWarning, match="treesitter-chunker#592"):
        _check_completed(analyzer, baml_library)
    assert calls == [{}, {"timeout": LOAD_TOLERANT_DEADLINE_SECONDS}]


@RECHECK_TIMEOUT
def test_expired_analysis_is_confirmed_under_the_tolerant_bound(
    baml_library: Path,
) -> None:
    analyzer = _analyzer(baml_library.parent)
    with pytest.warns(UserWarning, match="treesitter-chunker#592"):
        first, confirmed = _analyze_with_confirmation(
            analyzer, baml_library, first_timeout=1e-6
        )

    _assert_expired(first, 1e-6)
    assert confirmed is not None
    _assert_complete(confirmed, LOAD_TOLERANT_DEADLINE_SECONDS)


def test_failure_is_never_rechecked(tmp_path: Path) -> None:
    artifact = tmp_path / "not-elf.so"
    artifact.write_bytes(b"not an ELF object\n")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        first, confirmed = _analyze_with_confirmation(_analyzer(tmp_path), artifact)

    assert first["analysis"]["status"] == "failed"
    assert confirmed is None


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

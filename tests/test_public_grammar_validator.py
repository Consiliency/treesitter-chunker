"""Contract tests for the exported grammar validator using real parsers."""

import shutil
import sys
from pathlib import Path

from chunker import get_parser
from chunker.grammar_management import GrammarValidator, ValidationLevel
from chunker.grammar_management.core import load_compiled_grammar
from tree_sitter_language_pack import cache_dir


FIXTURE_DIR = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app"


def test_parse_samples_accepts_python_fixtures(tmp_path: Path) -> None:
    sources = [
        (FIXTURE_DIR / name).read_text(encoding="utf-8")
        for name in ("alpha.py", "service.py")
    ]
    parser = get_parser("python")
    for source in sources:
        tree = parser.parse(source.encode("utf-8"))
        assert tree.root_node.type == "module"
        assert not tree.root_node.has_error

    validator = GrammarValidator(cache_dir=tmp_path / "grammar-cache")
    assert (tmp_path / "grammar-cache").is_dir()
    success, errors = validator.test_parse_samples("python", sources)

    assert success
    assert errors == []


def test_parse_samples_reports_unavailable_language(tmp_path: Path) -> None:
    source = (FIXTURE_DIR / "alpha.py").read_text(encoding="utf-8")
    validator = GrammarValidator(cache_dir=tmp_path / "grammar-cache")

    success, errors = validator.test_parse_samples("nonexistent", [source])

    assert not success
    assert len(errors) == 1
    assert errors[0].startswith("Parser setup failed:")


def test_parse_samples_reports_syntax_error_with_sample_index(tmp_path: Path) -> None:
    valid = (FIXTURE_DIR / "alpha.py").read_text(encoding="utf-8")
    malformed = "def broken(:\n    pass\n"
    assert get_parser("python").parse(malformed.encode("utf-8")).root_node.has_error

    validator = GrammarValidator(cache_dir=tmp_path / "grammar-cache")
    success, errors = validator.test_parse_samples("python", [valid, malformed, valid])

    assert not success
    assert len(errors) == 1
    assert errors[0].startswith("Sample 2:")
    assert "syntax error" in errors[0].lower()


def test_validation_cache_rechecks_replaced_local_grammar(tmp_path: Path) -> None:
    suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    native = Path(cache_dir()) / f"libtree_sitter_python{suffix}"
    source = (FIXTURE_DIR / "service.py").read_bytes()
    assert native.exists()
    assert not load_compiled_grammar(native, "python").parse(source).root_node.has_error

    candidate = tmp_path / f"libpython{suffix}"
    candidate.write_bytes(b"")
    cache = tmp_path / "validator-cache"
    validator = GrammarValidator(cache_dir=cache)
    broken = validator.validate_grammar(candidate, "python", ValidationLevel.STANDARD)
    assert not broken.is_valid
    assert any("empty" in error.lower() for error in broken.errors)

    candidate.unlink()
    shutil.copyfile(native, candidate)
    assert (
        not load_compiled_grammar(candidate, "python").parse(source).root_node.has_error
    )

    repaired = validator.validate_grammar(candidate, "python", ValidationLevel.STANDARD)
    assert repaired.is_valid
    assert repaired.errors == []
    assert repaired.performance_metrics["samples_tested"] > 0
    assert (
        GrammarValidator(cache_dir=cache)
        .validate_grammar(candidate, "python", ValidationLevel.STANDARD)
        .is_valid
    )
    assert (cache / "validation_cache.json").exists()

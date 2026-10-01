"""Contract tests for the exported grammar validator using real parsers."""

from pathlib import Path

from chunker import get_parser
from chunker.grammar_management import GrammarValidator


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

import json
from pathlib import Path

from tests.boundary_ir_conformance import P0_BOUNDARY_LANGUAGES, fixture_path

MANIFEST_PATH = Path("tests/fixtures/boundary_ir/manifest.json")


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_each_p0_language_has_fixture_repo_and_utf8_sources():
    for language in P0_BOUNDARY_LANGUAGES:
        root = fixture_path(language)
        assert root.is_dir()
        sources = [path for path in root.rglob("*") if path.is_file()]
        assert sources, f"{language} fixture repo has no source files"
        for source in sources:
            source.read_text(encoding="utf-8")


def test_manifest_has_p0_language_expectations():
    manifest = _manifest()

    assert tuple(manifest) == ("go", "javascript", "python", "typescript")
    assert set(manifest) == set(P0_BOUNDARY_LANGUAGES)
    for language in P0_BOUNDARY_LANGUAGES:
        entry = manifest[language]
        assert entry["expected_qualified_names"]
        assert entry["expected_kinds"]
        assert entry["expected_signatures"]
        assert entry["expected_dependencies"]
        assert entry["expected_calls"]
        assert "resolved" in entry["expected_resolution_statuses"]
        assert "ambiguous" in entry["expected_resolution_statuses"]
        assert "unresolved" in entry["expected_resolution_statuses"]
        assert entry["strict_reference_targets"]


def test_fixture_corpus_contains_nested_import_call_duplicate_and_unresolved_cases():
    corpus_text = {
        language: "\n".join(
            path.read_text(encoding="utf-8")
            for path in fixture_path(language).rglob("*")
            if path.is_file()
        )
        for language in P0_BOUNDARY_LANGUAGES
    }

    assert "class Renderer" in corpus_text["python"]
    assert "from app.formatting import format_name" in corpus_text["python"]
    assert corpus_text["python"].count("def helper") == 2
    assert "missing_call" in corpus_text["python"]

    assert "class Renderer" in corpus_text["javascript"]
    assert "import { formatName }" in corpus_text["javascript"]
    assert corpus_text["javascript"].count("function helper") == 2
    assert "missingCall" in corpus_text["javascript"]

    assert "interface Formatter" in corpus_text["typescript"]
    assert "import type { Formatter }" in corpus_text["typescript"]
    assert corpus_text["typescript"].count("function helper") == 2
    assert "missingCall" in corpus_text["typescript"]

    assert "type Widget struct" in corpus_text["go"]
    assert 'import "strings"' in corpus_text["go"]
    assert corpus_text["go"].count("func helper") == 2
    assert "Ghost" in corpus_text["go"]

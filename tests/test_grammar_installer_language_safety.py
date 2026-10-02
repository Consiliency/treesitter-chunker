"""Installer language identifiers cannot escape their cache directory."""

from pathlib import Path

from chunker.grammar_management.core import GrammarInstaller


def test_installer_rejects_traversal_before_cache_cleanup(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    installer = GrammarInstaller(cache_dir=cache)
    (cache / "downloads/tree-sitter-x").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    malicious = "x/../../../outside"
    assert (installer._downloads_dir / f"tree-sitter-{malicious}").resolve() == outside

    for unsafe in (malicious, r"x\..\..\outside", "C:outside", "..", ""):
        assert installer._download_grammar(
            unsafe, "https://github.com/tree-sitter/tree-sitter-python"
        ) == (False, None, "Invalid grammar language")
        assert installer.install_grammar(
            unsafe, "https://github.com/tree-sitter/tree-sitter-python"
        ) == (False, "Invalid grammar language", None)
        assert installer.remove_grammar(unsafe) == (False, "Invalid grammar language")
        installer._cleanup_cache(unsafe)
    assert sentinel.read_text(encoding="utf-8") == "keep"

    for language in ("python", "c_sharp", "c++", "baml-grammar"):
        assert installer._download_grammar(language, "invalid-url")[2] != (
            "Invalid grammar language"
        )
    ordinary = cache / "downloads/tree-sitter-python"
    ordinary.mkdir()
    (ordinary / "stale.txt").write_text("stale", encoding="utf-8")
    installer._cleanup_cache("python")
    assert not ordinary.exists()

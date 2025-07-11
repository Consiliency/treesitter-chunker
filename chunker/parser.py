from __future__ import annotations
import os
from pathlib import Path
from tree_sitter import Language, Parser

_LIB_PATH = Path("build/my-languages.so")

_LANG_REPOS = {
    "python": "grammars/tree-sitter-python",
    "rust": "grammars/tree-sitter-rust",
    "javascript": "grammars/tree-sitter-javascript",
    "c": "grammars/tree-sitter-c",
    "cpp": "grammars/tree-sitter-cpp",
}

def _ensure_lib() -> None:
    if _LIB_PATH.exists():
        return
    _LIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Language.build_library(str(_LIB_PATH), list(_LANG_REPOS.values()))

# Build the library once when the module is imported
_ensure_lib()

_LANGUAGES = {lang: Language(str(_LIB_PATH), lang) for lang in _LANG_REPOS}

def get_parser(lang: str) -> Parser:
    """Return a Tree‑sitter `Parser` for the requested language."""
    if lang not in _LANGUAGES:
        raise ValueError(f"Unsupported language: {lang}")
    parser = Parser()
    parser.set_language(_LANGUAGES[lang])
    return parser

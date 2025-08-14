#!/usr/bin/env python3
import os
from pathlib import Path
from chunker.grammar.manager import TreeSitterGrammarManager

langs = os.getenv("CHUNKER_WHEEL_LANGS", "python,javascript,rust").split(",")
repo_map = {
	"python": "https://github.com/tree-sitter/tree-sitter-python",
	"javascript": "https://github.com/tree-sitter/tree-sitter-javascript",
	"rust": "https://github.com/tree-sitter/tree-sitter-rust",
}

root = Path(__file__).resolve().parents[1]
build = root / "build"
source = root / "grammars"

mgr = TreeSitterGrammarManager(grammars_dir=source, build_dir=build)
for lang in langs:
	url = repo_map.get(lang)
	if not url:
		continue
	mgr.add_grammar(lang, url)
	if mgr.fetch_grammar(lang):
		mgr.build_grammar(lang)
print("Built grammars:", langs, "to", build)

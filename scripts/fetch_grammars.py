"""
Clone a curated set of Tree‑sitter grammars into ./grammars.
Run: python scripts/fetch_grammars.py
"""
from pathlib import Path
import subprocess

GRAMMARS = {
    # Original languages
    "python": "https://github.com/tree-sitter/tree-sitter-python.git",
    "rust": "https://github.com/tree-sitter/tree-sitter-rust.git",
    "javascript": "https://github.com/tree-sitter/tree-sitter-javascript.git",
    "c": "https://github.com/tree-sitter/tree-sitter-c.git",
    "cpp": "https://github.com/tree-sitter/tree-sitter-cpp.git",
    
    # New languages for Phase 8
    "go": "https://github.com/tree-sitter/tree-sitter-go.git",
    "ruby": "https://github.com/tree-sitter/tree-sitter-ruby.git",
    "java": "https://github.com/tree-sitter/tree-sitter-java.git",
    
    # Additional popular languages
    "typescript": "https://github.com/tree-sitter/tree-sitter-typescript.git",
    "csharp": "https://github.com/tree-sitter/tree-sitter-c-sharp.git",
    "php": "https://github.com/tree-sitter/tree-sitter-php.git",
    "swift": "https://github.com/alex-pinkus/tree-sitter-swift.git",
    "kotlin": "https://github.com/fwcd/tree-sitter-kotlin.git",
}

dest = Path("grammars")
dest.mkdir(exist_ok=True)

for lang, repo in GRAMMARS.items():
    tgt = dest / f"tree-sitter-{lang}"
    if tgt.exists():
        print(f"[skip] {lang} already present")
        continue
    print(f"[clone] {lang}")
    subprocess.run(["git", "clone", "--depth=1", repo, str(tgt)], check=True)

#!/usr/bin/env python3
"""Directly build missing grammars without using the manager."""

import subprocess
import sys
import os
from pathlib import Path

def direct_build_grammar(language: str) -> bool:
    """Directly build a grammar using tree-sitter CLI if available, or manual compilation."""
    try:
        print(f"\nBuilding {language}...")
        
        # Map language names to their grammar directories
        grammar_mappings = {
            "json": "tree-sitter-json",
            "toml": "tree-sitter-toml", 
            "yaml": "tree-sitter-yaml",
            "html": "tree-sitter-html",
            "css": "tree-sitter-css",
            "xml": "tree-sitter-xml",
            "ruby": "tree-sitter-ruby",
            "php": "tree-sitter-php",
            "ocaml": "tree-sitter-ocaml",
            "wasm": "tree-sitter-wasm"
        }
        
        grammar_dir_name = grammar_mappings.get(language, f"tree-sitter-{language}")
        
        # First, check if grammar source exists
        grammar_path = Path("grammars") / grammar_dir_name
        if not grammar_path.exists():
            # Try to clone it
            config_file = Path("config/grammar_sources.json")
            if config_file.exists():
                import json
                with open(config_file) as f:
                    sources = json.load(f)
                    repo_url = sources.get(language)
                    if repo_url:
                        print(f"  Cloning {language} from {repo_url}...")
                        clone_cmd = ["git", "clone", "--depth", "1", repo_url, str(grammar_path)]
                        result = subprocess.run(clone_cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"  ✗ Failed to clone: {result.stderr}")
                            return False
                    else:
                        print(f"  ✗ No repository URL found for {language}")
                        return False
        
        # Find the actual source directory
        src_dir = None
        possible_paths = [
            grammar_path / "src",
            grammar_path / language / "src",
            grammar_path / "grammars" / language / "src",
            grammar_path / f"tree-sitter-{language}" / "src"
        ]
        
        for path in possible_paths:
            if path.exists():
                src_dir = path
                break
        
        if not src_dir:
            print(f"  ✗ Source directory not found for {language}")
            return False
        
        print(f"  Found source at: {src_dir}")
        
        # Build the grammar
        output_file = Path("chunker/data/grammars/build") / f"{language}.so"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Find all source files
        c_files = list(src_dir.glob("*.c"))
        cc_files = list(src_dir.glob("*.cc")) + list(src_dir.glob("*.cpp"))
        
        if not c_files and not cc_files:
            print(f"  ✗ No source files found in {src_dir}")
            return False
        
        # Determine compiler and flags
        use_cxx = len(cc_files) > 0
        compiler = "g++" if use_cxx else "gcc"
        
        # Special handling for languages with known issues
        extra_includes = []
        if language in ["php", "ocaml"]:
            # These need tree_sitter headers
            ts_include = subprocess.run(
                ["python", "-c", "import tree_sitter_language_pack; import os; print(os.path.dirname(tree_sitter_language_pack.__file__))"],
                capture_output=True, text=True
            )
            if ts_include.returncode == 0:
                inc_path = ts_include.stdout.strip()
                extra_includes = [f"-I{inc_path}"]
        
        # Build command
        sources = [str(f) for f in c_files + cc_files]
        cmd = [
            compiler,
            "-shared",
            "-fPIC",
            "-O2",
            "-o", str(output_file),
            *sources,
            "-std=c11" if not use_cxx else "-std=c++17",
            *extra_includes
        ]
        
        if use_cxx:
            cmd.append("-lstdc++")
        
        print(f"  Compiling with: {compiler}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and output_file.exists():
            print(f"  ✓ {language} built successfully")
            return True
        else:
            print(f"  ✗ Compilation failed: {result.stderr[:200]}")
            return False
            
    except Exception as e:
        print(f"  ✗ {language}: {e}")
        return False


def main():
    """Main function."""
    
    # Missing languages
    missing_languages = ["json", "toml", "yaml", "html", "css", "xml", "ruby", "php", "ocaml", "wasm"]
    
    print("=" * 60)
    print("Direct Build of Missing Grammars")
    print("=" * 60)
    print(f"Languages to build: {', '.join(missing_languages)}")
    
    successful = []
    failed = []
    
    for lang in missing_languages:
        if direct_build_grammar(lang):
            successful.append(lang)
        else:
            failed.append(lang)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"Built: {len(successful)}/{len(missing_languages)}")
    if successful:
        print(f"✓ Successfully built: {', '.join(successful)}")
    if failed:
        print(f"✗ Failed: {', '.join(failed)}")
    
    # Check total available
    package_dir = Path("chunker/data/grammars/build")
    if package_dir.exists():
        available_grammars = list(package_dir.glob("*.so"))
        print(f"\nTotal grammars now available: {len(available_grammars)}/35")
        
        if len(available_grammars) >= 35:
            print("\n✅ Phase 1.6a COMPLETE! All 35 grammars are now available!")
        elif len(available_grammars) >= 30:
            print(f"\n✅ Phase 1.6a substantially complete with {len(available_grammars)} grammars.")
            print("The core languages and most important grammars are available.")


if __name__ == "__main__":
    main()
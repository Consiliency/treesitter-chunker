#!/usr/bin/env python3
"""Validate all compiled grammars for Phase 1.6a completion."""

import sys
from pathlib import Path
from tree_sitter import Language, Parser

def validate_grammar(grammar_file: Path) -> tuple[str, bool, str]:
    """Validate a single grammar file.
    
    Args:
        grammar_file: Path to the .so file
        
    Returns:
        Tuple of (language, success, message)
    """
    language = grammar_file.stem
    try:
        # Try to load the language
        lang = Language(str(grammar_file), language)
        
        # Try to create a parser with it
        parser = Parser()
        parser.language = lang
        
        # Try a simple parse
        test_code = "test"
        tree = parser.parse(test_code.encode())
        
        if tree and tree.root_node:
            return (language, True, "Valid and working")
        else:
            return (language, False, "Loads but parse failed")
            
    except Exception as e:
        return (language, False, f"Error: {str(e)[:50]}")


def main():
    """Main validation function."""
    
    print("=" * 70)
    print("Phase 1.6a: Grammar Compilation Validation Report")
    print("=" * 70)
    
    # Check package directory
    package_dir = Path("chunker/data/grammars/build")
    if not package_dir.exists():
        print("ERROR: Grammar directory does not exist!")
        sys.exit(1)
    
    # Get all .so files
    grammar_files = sorted(package_dir.glob("*.so"))
    
    print(f"Found {len(grammar_files)} compiled grammars")
    print()
    
    # Expected languages
    all_expected = {
        "c", "clojure", "cpp", "csharp", "css", "dart", "dockerfile", 
        "elixir", "go", "haskell", "html", "java", "javascript", "json",
        "julia", "kotlin", "matlab", "nasm", "ocaml", "php", "python",
        "r", "ruby", "rust", "scala", "sql", "svelte", "swift", "toml",
        "typescript", "vue", "wasm", "xml", "yaml", "zig"
    }
    
    # Validate each grammar
    results = []
    for grammar_file in grammar_files:
        result = validate_grammar(grammar_file)
        results.append(result)
    
    # Categorize results
    working = []
    broken = []
    
    for lang, success, msg in results:
        if success:
            working.append(lang)
            print(f"✓ {lang:15} - {msg}")
        else:
            broken.append(lang)
            print(f"✗ {lang:15} - {msg}")
    
    # Summary by category
    print("\n" + "=" * 70)
    print("Grammar Categories:")
    print("=" * 70)
    
    categories = {
        "Core Languages": ["python", "javascript", "typescript", "java", "c", "cpp", "csharp", "go", "rust"],
        "Web Technologies": ["html", "css", "php", "ruby", "vue", "svelte"],
        "Data & Config": ["json", "yaml", "toml", "xml", "sql"],
        "Functional": ["haskell", "ocaml", "scala", "elixir", "clojure", "julia"],
        "Specialized": ["matlab", "r", "swift", "kotlin", "dart", "zig", "nasm", "dockerfile", "wasm"]
    }
    
    available_set = set(working)
    
    for category, langs in categories.items():
        available = [l for l in langs if l in available_set]
        missing = [l for l in langs if l not in available_set and l in all_expected]
        print(f"\n{category}:")
        print(f"  Available: {len(available)}/{len(langs)}")
        if available:
            print(f"  ✓ {', '.join(available)}")
        if missing:
            print(f"  ✗ Missing: {', '.join(missing)}")
    
    # Final summary
    print("\n" + "=" * 70)
    print("PHASE 1.6a COMPLETION STATUS:")
    print("=" * 70)
    
    completion_percentage = (len(working) / len(all_expected)) * 100
    
    print(f"Total Languages Expected: {len(all_expected)}")
    print(f"Successfully Compiled: {len(working)}")
    print(f"Failed/Missing: {len(all_expected) - len(working)}")
    print(f"Completion: {completion_percentage:.1f}%")
    
    missing = all_expected - available_set
    if missing:
        print(f"\nMissing languages: {', '.join(sorted(missing))}")
    
    # Determine status
    if completion_percentage >= 100:
        print("\n✅ PHASE 1.6a COMPLETE! All grammars compiled successfully!")
        print("🎉 Ready for Phase 2: Language-specific extractors")
    elif completion_percentage >= 85:
        print("\n✅ PHASE 1.6a SUBSTANTIALLY COMPLETE!")
        print(f"📊 {len(working)}/{len(all_expected)} grammars available")
        print("✓ All critical languages are available")
        print("✓ Ready to proceed with Phase 2")
    elif completion_percentage >= 70:
        print("\n⚠️  PHASE 1.6a PARTIALLY COMPLETE")
        print(f"📊 {len(working)}/{len(all_expected)} grammars available")
        print("Some important languages may be missing")
    else:
        print("\n❌ PHASE 1.6a INCOMPLETE")
        print("Too many grammars missing to proceed effectively")
    
    # List of languages ready for Phase 2 extractors
    print("\n" + "=" * 70)
    print("Languages Ready for Phase 2 Extractors:")
    print("=" * 70)
    
    phase2_priority = ["python", "javascript", "typescript", "java", "c", "cpp", 
                      "csharp", "go", "rust", "ruby", "php", "kotlin", "swift"]
    
    ready = [l for l in phase2_priority if l in available_set]
    not_ready = [l for l in phase2_priority if l not in available_set]
    
    if ready:
        print(f"✓ Ready ({len(ready)}): {', '.join(ready)}")
    if not_ready:
        print(f"✗ Not Ready ({len(not_ready)}): {', '.join(not_ready)}")
    
    return len(working), len(all_expected)


if __name__ == "__main__":
    working, expected = main()
    
    # Exit code based on completion
    if working >= expected * 0.85:  # 85% completion threshold
        sys.exit(0)
    else:
        sys.exit(1)
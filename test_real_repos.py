#!/usr/bin/env python3
"""Test treesitter-chunker with real repositories."""

from pathlib import Path

from chunker import chunk_file, list_languages
from chunker.repo.processor import RepoProcessor

# Available languages
print("Available languages:", sorted(list_languages()))
print()

# Test repositories
repos = {
    "lodash": {
        "path": "lodash",
        "language": "javascript",
        "files": ["lodash.js", "chunk.js", "compact.js"],
    },
    "flask": {
        "path": "flask",
        "language": "python",
        "files": ["src/flask/app.py", "src/flask/blueprints.py"],
    },
    "gin": {
        "path": "gin",
        "language": "go",
        "files": ["gin.go", "context.go", "tree.go"],
    },
    "serde": {
        "path": "serde",
        "language": "rust",
        "files": ["serde/src/lib.rs", "serde/src/de/mod.rs"],
    },
    "ruby": {
        "path": "ruby",
        "language": "ruby",
        "files": ["array.c", "string.c"],
    },  # C files in Ruby
    "guava": {
        "path": "guava",
        "language": "java",
        "files": ["guava/src/com/google/common/base/Strings.java"],
    },
    "googletest": {
        "path": "googletest",
        "language": "cpp",
        "files": ["googletest/src/gtest.cc"],
    },
}

print("Testing individual files from repositories:")
print("=" * 50)

for repo_name, info in repos.items():
    repo_path = Path(repo_name)
    if not repo_path.exists():
        print(f"\n❌ {repo_name} not found at {repo_path}")
        continue

    print(f"\n📁 Testing {repo_name} ({info['language']}):")

    # Test individual files
    for file_name in info["files"]:
        file_path = repo_path / file_name
        if not file_path.exists():
            # Try to find similar files
            similar = list(repo_path.rglob(f"*{Path(file_name).name}"))[:3]
            if similar:
                file_path = similar[0]
                print(f"  Using {file_path} instead of {file_name}")
            else:
                print(f"  ❌ {file_name} not found")
                continue

        try:
            # For C files, use C language
            language = info["language"]
            if file_path.suffix == ".c":
                language = "c"
            elif file_path.suffix == ".cc":
                language = "cpp"

            chunks = chunk_file(str(file_path), language=language)
            print(f"  ✅ {file_path.name}: {len(chunks)} chunks")

            # Show first few chunks
            for chunk in chunks[:2]:
                print(f"     - {chunk.node_type} at line {chunk.start_line}")

        except Exception as e:
            print(f"  ❌ Error with {file_path.name}: {e}")

# Test repository processing
print("\n\nTesting repository-wide processing:")
print("=" * 50)

processor = RepoProcessor()

for repo_name, info in repos.items():
    repo_path = Path(repo_name)
    if not repo_path.exists():
        continue

    print(f"\n📁 Processing entire {repo_name} repository:")

    try:
        # Process with limits
        # Limit processing to save time
        result = processor.process_repository(
            str(repo_path),
            file_pattern="**/*.{py,js,go,rs,java,c,cc,cpp,rb}",
            exclude_patterns=["**/test/**", "**/tests/**", "**/vendor/**"],
        )

        print(f"  ✅ Processed {result.files_processed} files")
        print(f"  📊 Total chunks: {result.total_chunks}")
        print(f"  ⏱️  Time: {result.processing_time:.2f}s")

        # Show language breakdown
        lang_counts = {}
        for file_result in result.file_results[:10]:  # First 10 files
            lang = file_result.language
            lang_counts[lang] = lang_counts.get(lang, 0) + len(file_result.chunks)

        if lang_counts:
            print(f"  📈 Languages: {dict(sorted(lang_counts.items()))}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n✅ Repository testing complete!")

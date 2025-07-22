#!/usr/bin/env python3
"""Demo script for advanced query functionality."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker import (
    chunk_file,
    NaturalLanguageQueryEngine,
    AdvancedQueryIndex,
    SmartQueryOptimizer,
    QueryType
)


def main():
    """Demonstrate advanced query capabilities."""
    print("Advanced Query Demo")
    print("=" * 50)
    
    # Chunk some example files
    print("\n1. Chunking example files...")
    chunks = []
    
    # Get chunks from example Python files
    chunker_dir = Path(__file__).parent.parent / "chunker"
    if chunker_dir.exists():
        # Get a few Python files to demonstrate
        py_files = list(chunker_dir.glob("*.py"))[:10]  # First 10 files
        for py_file in py_files:
            try:
                file_chunks = chunk_file(str(py_file), "python")
                chunks.extend(file_chunks)
            except Exception as e:
                print(f"   Warning: Could not chunk {py_file.name}: {e}")
    
    print(f"   Found {len(chunks)} chunks")
    
    # Create query components
    engine = NaturalLanguageQueryEngine()
    index = AdvancedQueryIndex()
    optimizer = SmartQueryOptimizer()
    
    # Build index
    print("\n2. Building search index...")
    index.build_index(chunks[:100])  # Use first 100 chunks for demo
    stats = index.get_statistics()
    print(f"   Index stats: {stats['total_chunks']} chunks, {stats['unique_terms']} unique terms")
    
    # Demo natural language queries
    print("\n3. Natural Language Queries:")
    queries = [
        "find error handling code",
        "show me authentication functions",
        "database query methods",
        "test functions",
        "configuration classes"
    ]
    
    for query in queries:
        print(f"\n   Query: '{query}'")
        
        # Optimize query
        optimized = optimizer.optimize_query(query, QueryType.NATURAL_LANGUAGE)
        if optimized != query:
            print(f"   Optimized: '{optimized}'")
        
        # Search
        results = engine.search(optimized, chunks[:100], QueryType.NATURAL_LANGUAGE, limit=3)
        
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result.chunk.file_path}:{result.chunk.start_line}")
            print(f"      Type: {result.chunk.node_type}, Score: {result.score:.2f}")
            if result.metadata.get("matched_intents"):
                print(f"      Intents: {', '.join(result.metadata['matched_intents'])}")
    
    # Demo structured queries
    print("\n\n4. Structured Queries:")
    structured_queries = [
        "type:class_definition language:python",
        "type:function_definition error",
        "language:python test"
    ]
    
    for query in structured_queries:
        print(f"\n   Query: '{query}'")
        results = engine.search(query, chunks[:100], QueryType.STRUCTURED, limit=3)
        
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result.chunk.file_path}:{result.chunk.start_line}")
            print(f"      Type: {result.chunk.node_type}, Score: {result.score:.2f}")
    
    # Demo filtering
    print("\n\n5. Filtering Examples:")
    
    # Filter by language
    python_chunks = engine.filter(chunks[:100], languages=["python"])
    print(f"   Python chunks: {len(python_chunks)}")
    
    # Filter by node type
    class_chunks = engine.filter(chunks[:100], node_types=["class_definition"])
    print(f"   Class definitions: {len(class_chunks)}")
    
    # Filter by size
    small_chunks = engine.filter(chunks[:100], max_lines=10)
    print(f"   Small chunks (≤10 lines): {len(small_chunks)}")
    
    # Demo similarity search
    print("\n\n6. Similarity Search:")
    if chunks:
        reference = chunks[0]
        print(f"   Reference chunk: {reference.file_path}:{reference.start_line}")
        print(f"   Type: {reference.node_type}")
        
        similar = engine.find_similar(reference, chunks[:100], threshold=0.3, limit=5)
        print(f"\n   Found {len(similar)} similar chunks:")
        
        for i, result in enumerate(similar, 1):
            print(f"   {i}. {result.chunk.file_path}:{result.chunk.start_line}")
            print(f"      Score: {result.score:.2f}")
            if "similarity_factors" in result.metadata:
                factors = result.metadata["similarity_factors"]
                print(f"      Factors: {', '.join(k for k, v in factors.items() if v)}")
    
    # Demo query suggestions
    print("\n\n7. Query Suggestions:")
    partial_queries = ["find", "test", "type:func"]
    
    for partial in partial_queries:
        suggestions = optimizer.suggest_queries(partial, chunks[:100])
        print(f"\n   Partial: '{partial}'")
        print(f"   Suggestions: {suggestions[:5]}")
    
    # Demo regex search
    print("\n\n8. Regex Search:")
    regex_pattern = r"def\s+\w+_test\s*\("
    print(f"   Pattern: {regex_pattern}")
    
    results = engine.search(regex_pattern, chunks[:100], QueryType.REGEX, limit=5)
    print(f"   Found {len(results)} matches")
    
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result.chunk.file_path}:{result.chunk.start_line}")
        print(f"      Matches: {result.metadata.get('match_count', 0)}")


if __name__ == "__main__":
    main()
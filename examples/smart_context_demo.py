#!/usr/bin/env python3
"""Demonstrate smart context functionality."""

from chunker import (
    HybridContextStrategy,
    RelevanceContextStrategy,
    TreeSitterSmartContextProvider,
    chunk_file,
)


def main():
    """Run smart context demo."""
    # Get chunks from a Python file
    chunks = chunk_file("examples/example.py", "python")

    if not chunks:
        print("No chunks found!")
        return

    # Create smart context provider
    provider = TreeSitterSmartContextProvider()

    # Create context strategies
    relevance_strategy = RelevanceContextStrategy()
    hybrid_strategy = HybridContextStrategy()

    # Demo 1: Get semantic context for a chunk
    print("=== SEMANTIC CONTEXT DEMO ===")
    target_chunk = chunks[0]
    print(f"\nTarget chunk: {target_chunk.node_type} at line {target_chunk.start_line}")
    print(f"Content preview: {target_chunk.content[:100]}...")

    context_str, metadata = provider.get_semantic_context(target_chunk, max_tokens=500)
    print(f"\nSemantic context (relevance: {metadata.relevance_score:.2f}):")
    print(context_str[:300] + "..." if len(context_str) > 300 else context_str)

    # Demo 2: Get dependencies
    print("\n\n=== DEPENDENCY CONTEXT DEMO ===")
    dependencies = provider.get_dependency_context(target_chunk, chunks)
    print(f"\nFound {len(dependencies)} dependencies:")
    for dep_chunk, dep_meta in dependencies[:3]:  # Show top 3
        print(
            f"  - {dep_chunk.node_type} at line {dep_chunk.start_line} "
            f"(relevance: {dep_meta.relevance_score:.2f})",
        )

    # Demo 3: Get usages
    print("\n\n=== USAGE CONTEXT DEMO ===")
    usages = provider.get_usage_context(target_chunk, chunks)
    print(f"\nFound {len(usages)} usages:")
    for usage_chunk, usage_meta in usages[:3]:  # Show top 3
        print(
            f"  - {usage_chunk.node_type} at line {usage_chunk.start_line} "
            f"(relevance: {usage_meta.relevance_score:.2f})",
        )

    # Demo 4: Get structural context
    print("\n\n=== STRUCTURAL CONTEXT DEMO ===")
    structural = provider.get_structural_context(target_chunk, chunks)
    print(f"\nFound {len(structural)} structural relations:")
    for struct_chunk, struct_meta in structural[:3]:  # Show top 3
        print(
            f"  - {struct_chunk.node_type} at line {struct_chunk.start_line} "
            f"(distance: {struct_meta.distance} lines)",
        )

    # Demo 5: Use context strategy to select most relevant chunks
    print("\n\n=== CONTEXT SELECTION DEMO ===")
    all_candidates = dependencies + usages + structural

    # Use relevance strategy
    selected_by_relevance = relevance_strategy.select_context(
        target_chunk,
        all_candidates,
        max_tokens=1000,
    )
    print(f"\nRelevance strategy selected {len(selected_by_relevance)} chunks")

    # Use hybrid strategy
    selected_by_hybrid = hybrid_strategy.select_context(
        target_chunk,
        all_candidates,
        max_tokens=1000,
    )
    print(f"Hybrid strategy selected {len(selected_by_hybrid)} chunks")

    # Show ranking
    ranked = relevance_strategy.rank_candidates(target_chunk, all_candidates)
    print("\nTop 5 ranked chunks by relevance:")
    for chunk, score in ranked[:5]:
        print(f"  - {chunk.node_type} at line {chunk.start_line} (score: {score:.3f})")


if __name__ == "__main__":
    main()

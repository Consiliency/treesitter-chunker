#!/usr/bin/env python3
"""Enhanced demonstration of semantic merging functionality."""

import os
import sys
from pathlib import Path

sys.path.append(Path(os.path.dirname(Path(__file__).resolve().parent)))

from chunker.chunker import chunk_file
from chunker.semantic import (
    MergeConfig,
    TreeSitterRelationshipAnalyzer,
    TreeSitterSemanticMerger,
)


def create_example_chunks():
    """Create example chunks for demonstration."""
    # Example Python code with getters/setters and small methods
    example_code = '''
class Person:
    def __init__(self, name, age):
        self._name = name
        self._age = age

    def get_name(self):
        """Get person's name."""
        return self._name

    def set_name(self, name):
        """Set person's name."""
        self._name = name

    def get_age(self):
        """Get person's age."""
        return self._age

    def set_age(self, age):
        """Set person's age."""
        if age < 0:
            raise ValueError("Age cannot be negative")
        self._age = age

    @property
    def email(self):
        """Get email address."""
        return self._email

    @email.setter
    def email(self, value):
        """Set email address."""
        if '@' not in value:
            raise ValueError("Invalid email")
        self._email = value

    def greet(self):
        """Greet the person."""
        print(f"Hello, {self._name}!")

    def is_adult(self):
        """Check if person is adult."""
        return self._age >= 18

    def is_senior(self):
        """Check if person is senior."""
        return self._age >= 65

class Calculator:
    # Overloaded-style methods
    def add_two(self, a, b):
        """Add two numbers."""
        return a + b

    def add_three(self, a, b, c):
        """Add three numbers."""
        return a + b + c

    def add_many(self, *args):
        """Add many numbers."""
        return sum(args)
'''

    # Write to temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(example_code)
        temp_file = f.name

    # Chunk the file
    chunks = chunk_file(temp_file, "python")

    # Clean up
    import os

    os.unlink(temp_file)

    return chunks


def demonstrate_relationship_analysis(chunks):
    """Demonstrate relationship analysis."""
    print("=== Relationship Analysis ===\n")

    analyzer = TreeSitterRelationshipAnalyzer()

    # Find getter/setter pairs
    pairs = analyzer.find_getter_setter_pairs(chunks)
    print(f"Found {len(pairs)} getter/setter pairs:")
    for getter, setter in pairs:
        getter_name = getter.content.split("(")[0].split()[-1]
        setter_name = setter.content.split("(")[0].split()[-1]
        print(f"  - {getter_name} <-> {setter_name}")

    # Find related chunks
    print("\nRelated chunks:")
    relationships = analyzer.find_related_chunks(chunks)
    for chunk_id, related_ids in relationships.items():
        if related_ids:
            chunk = next(c for c in chunks if c.chunk_id == chunk_id)
            chunk_name = chunk.content.split("\n")[0].strip()
            print(f"  - {chunk_name}: {len(related_ids)} related chunks")

    # Calculate cohesion scores
    print("\nCohesion scores for method pairs:")
    methods = [
        c for c in chunks if c.node_type in ["function_definition", "method_definition"]
    ]
    for i in range(min(3, len(methods) - 1)):
        score = analyzer.calculate_cohesion_score(methods[i], methods[i + 1])
        name1 = methods[i].content.split("(")[0].split()[-1]
        name2 = methods[i + 1].content.split("(")[0].split()[-1]
        print(f"  - {name1} <-> {name2}: {score:.2f}")


def demonstrate_semantic_merging(chunks):
    """Demonstrate semantic chunk merging."""
    print("\n=== Semantic Merging ===\n")

    # Configure merger
    config = MergeConfig(
        merge_getters_setters=True,
        merge_small_methods=True,
        small_method_threshold=5,
        cohesion_threshold=0.6,
    )
    merger = TreeSitterSemanticMerger(config)

    print(f"Original chunks: {len(chunks)}")
    for chunk in chunks:
        if chunk.node_type in ["function_definition", "method_definition"]:
            name = chunk.content.split("(")[0].split()[-1]
            lines = chunk.end_line - chunk.start_line + 1
            print(f"  - {name} ({lines} lines)")

    # Merge chunks
    merged_chunks = merger.merge_chunks(chunks)

    print(f"\nMerged chunks: {len(merged_chunks)}")
    for chunk in merged_chunks:
        if chunk.node_type in [
            "function_definition",
            "method_definition",
            "merged_chunk",
        ]:
            # Extract names from content
            lines = chunk.content.split("\n")
            names = []
            for line in lines:
                if "def " in line and "(" in line:
                    name = line.split("(")[0].split()[-1]
                    names.append(name)

            if names:
                total_lines = chunk.end_line - chunk.start_line + 1
                if len(names) > 1:
                    print(f"  - Merged: {', '.join(names)} ({total_lines} lines)")
                else:
                    print(f"  - {names[0]} ({total_lines} lines)")

    # Show merge reasons for some pairs
    print("\nSample merge reasons:")
    pairs_to_check = [
        ("get_name", "set_name"),
        ("get_age", "set_age"),
        ("email", "email"),  # Property methods
        ("is_adult", "is_senior"),  # Small related methods
    ]

    for name1, name2 in pairs_to_check:
        chunk1 = next((c for c in chunks if name1 in c.content), None)
        chunk2 = next((c for c in chunks if name2 in c.content and c != chunk1), None)
        if chunk1 and chunk2:
            reason = merger.get_merge_reason(chunk1, chunk2)
            if reason:
                print(f"  - {name1} + {name2}: {reason}")


def demonstrate_configuration_impact():
    """Show how different configurations affect merging."""
    print("\n=== Configuration Impact ===\n")

    chunks = create_example_chunks()
    method_chunks = [
        c for c in chunks if c.node_type in ["function_definition", "method_definition"]
    ]

    configs = {
        "Conservative": MergeConfig(
            merge_getters_setters=True,
            merge_overloaded_functions=False,
            merge_small_methods=False,
            cohesion_threshold=0.8,
        ),
        "Moderate": MergeConfig(
            merge_getters_setters=True,
            merge_overloaded_functions=True,
            merge_small_methods=True,
            small_method_threshold=5,
            cohesion_threshold=0.6,
        ),
        "Aggressive": MergeConfig(
            merge_getters_setters=True,
            merge_overloaded_functions=True,
            merge_small_methods=True,
            small_method_threshold=10,
            cohesion_threshold=0.4,
            max_merged_size=200,
        ),
    }

    for config_name, config in configs.items():
        merger = TreeSitterSemanticMerger(config)
        merged = merger.merge_chunks(method_chunks)
        print(f"{config_name}: {len(method_chunks)} chunks -> {len(merged)} chunks")


def main():
    """Run the demonstration."""
    print("Enhanced Tree-sitter Semantic Merging Demonstration")
    print("=" * 60)

    # Create example chunks
    chunks = create_example_chunks()

    # Filter to just method/function chunks for clearer demo
    method_chunks = [
        c for c in chunks if c.node_type in ["function_definition", "method_definition"]
    ]

    # Demonstrate relationship analysis
    demonstrate_relationship_analysis(method_chunks)

    # Demonstrate semantic merging
    demonstrate_semantic_merging(method_chunks)

    # Show configuration impact
    demonstrate_configuration_impact()

    print("\n" + "=" * 60)
    print("Demonstration complete!")
    print("\nKey Benefits:")
    print("- Reduces fragmentation by merging related code")
    print("- Preserves semantic boundaries")
    print("- Highly configurable for different use cases")
    print("- Language-aware patterns for multiple languages")


if __name__ == "__main__":
    main()

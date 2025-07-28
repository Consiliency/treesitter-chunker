#!/usr/bin/env python3
"""Improved demonstration of semantic merging functionality."""

from chunker import CodeChunk
from chunker.semantic import (
    MergeConfig,
    TreeSitterRelationshipAnalyzer,
    TreeSitterSemanticMerger,
)


def create_realistic_chunks():
    """Create more realistic example chunks."""
    chunks = []

    # Person class methods
    chunks.extend(
        [
            CodeChunk(
                language="python",
                file_path="/example.py",
                node_type="method_definition",
                start_line=10,
                end_line=12,
                byte_start=100,
                byte_end=150,
                parent_context="class_definition:Person",
                content='def get_name(self):\n    """Get person\'s name."""\n    return self._name',
            ),
            CodeChunk(
                language="python",
                file_path="/example.py",
                node_type="method_definition",
                start_line=14,
                end_line=16,
                byte_start=160,
                byte_end=210,
                parent_context="class_definition:Person",
                content='def set_name(self, name):\n    """Set person\'s name."""\n    self._name = name',
            ),
            CodeChunk(
                language="python",
                file_path="/example.py",
                node_type="method_definition",
                start_line=18,
                end_line=20,
                byte_start=220,
                byte_end=270,
                parent_context="class_definition:Person",
                content='def get_age(self):\n    """Get person\'s age."""\n    return self._age',
            ),
            CodeChunk(
                language="python",
                file_path="/example.py",
                node_type="method_definition",
                start_line=22,
                end_line=26,
                byte_start=280,
                byte_end=380,
                parent_context="class_definition:Person",
                content='def set_age(self, age):\n    """Set person\'s age."""\n    if age < 0:\n        raise ValueError("Age cannot be negative")\n    self._age = age',
            ),
            CodeChunk(
                language="python",
                file_path="/example.py",
                node_type="method_definition",
                start_line=28,
                end_line=35,
                byte_start=390,
                byte_end=550,
                parent_context="class_definition:Person",
                content='def validate(self):\n    """Validate person data."""\n    if not self._name:\n        raise ValueError("Name is required")\n    if self._age < 0:\n        raise ValueError("Age cannot be negative")\n    if self._age > 150:\n        raise ValueError("Age seems unrealistic")',
            ),
            # Property methods with decorators
            CodeChunk(
                language="python",
                file_path="/example.py",
                node_type="method_definition",
                start_line=40,
                end_line=43,
                byte_start=600,
                byte_end=680,
                parent_context="class_definition:Person",
                content='@property\ndef full_name(self):\n    """Get full name."""\n    return f"{self._first_name} {self._last_name}"',
            ),
            CodeChunk(
                language="python",
                file_path="/example.py",
                node_type="method_definition",
                start_line=45,
                end_line=48,
                byte_start=690,
                byte_end=770,
                parent_context="class_definition:Person",
                content='@full_name.setter\ndef full_name(self, value):\n    """Set full name."""\n    self._first_name, self._last_name = value.split(\' \', 1)',
            ),
        ],
    )

    # Calculator class with overloaded-style methods
    chunks.extend(
        [
            CodeChunk(
                language="java",
                file_path="/Calculator.java",
                node_type="method_definition",
                start_line=10,
                end_line=12,
                byte_start=100,
                byte_end=150,
                parent_context="class_definition:Calculator",
                content="public int add(int a, int b) {\n    return a + b;\n}",
            ),
            CodeChunk(
                language="java",
                file_path="/Calculator.java",
                node_type="method_definition",
                start_line=14,
                end_line=16,
                byte_start=160,
                byte_end=210,
                parent_context="class_definition:Calculator",
                content="public double add(double a, double b) {\n    return a + b;\n}",
            ),
            CodeChunk(
                language="java",
                file_path="/Calculator.java",
                node_type="method_definition",
                start_line=18,
                end_line=20,
                byte_start=220,
                byte_end=270,
                parent_context="class_definition:Calculator",
                content="public int add(int a, int b, int c) {\n    return a + b + c;\n}",
            ),
            # Separate method that shouldn't merge
            CodeChunk(
                language="java",
                file_path="/Calculator.java",
                node_type="method_definition",
                start_line=25,
                end_line=40,
                byte_start=300,
                byte_end=600,
                parent_context="class_definition:Calculator",
                content='public double calculateAverage(int[] numbers) {\n    // Long method that shouldn\'t merge\n    if (numbers == null || numbers.length == 0) {\n        throw new IllegalArgumentException("Array cannot be null or empty");\n    }\n    double sum = 0;\n    for (int num : numbers) {\n        sum += num;\n    }\n    return sum / numbers.length;\n}',
            ),
        ],
    )

    # Some unrelated functions
    chunks.extend(
        [
            CodeChunk(
                language="python",
                file_path="/utils.py",
                node_type="function_definition",
                start_line=5,
                end_line=15,
                byte_start=50,
                byte_end=250,
                parent_context="",
                content='def format_date(date):\n    """Format date for display."""\n    # Implementation details...\n    return date.strftime("%Y-%m-%d")',
            ),
        ],
    )

    return chunks


def demonstrate_targeted_merging():
    """Demonstrate more targeted semantic merging."""
    chunks = create_realistic_chunks()

    # Separate chunks by language and file
    python_person_chunks = [
        c for c in chunks if c.language == "python" and "Person" in c.parent_context
    ]
    java_calc_chunks = [c for c in chunks if c.language == "java"]
    [c for c in chunks if c not in python_person_chunks and c not in java_calc_chunks]

    print("=== Targeted Semantic Merging Demo ===\n")

    # Configure merger with reasonable settings
    config = MergeConfig(
        merge_getters_setters=True,
        merge_overloaded_functions=True,
        merge_small_methods=False,  # Don't merge all small methods
        cohesion_threshold=0.8,  # Higher threshold
        max_merged_size=20,  # Reasonable size limit
    )
    merger = TreeSitterSemanticMerger(config)
    analyzer = TreeSitterRelationshipAnalyzer()

    # Process Python getter/setter pairs
    print("Python Getter/Setter Merging:")
    print(f"  Original chunks: {len(python_person_chunks)}")

    pairs = analyzer.find_getter_setter_pairs(python_person_chunks)
    print(f"  Found {len(pairs)} getter/setter pairs")

    merged_python = merger.merge_chunks(python_person_chunks)
    print(f"  After merging: {len(merged_python)} chunks")

    for chunk in merged_python:
        methods = [
            line.strip()
            for line in chunk.content.split("\n")
            if line.strip().startswith("def ")
        ]
        if len(methods) > 1:
            print(
                f"    - Merged: {', '.join(m.split('(')[0].replace('def ', '') for m in methods)}",
            )
        else:
            method_name = chunk.content.split("(")[0].split()[-1]
            print(f"    - Kept separate: {method_name}")

    # Process Java overloaded methods
    print("\nJava Overloaded Method Merging:")
    print(f"  Original chunks: {len(java_calc_chunks)}")

    overloaded = analyzer.find_overloaded_functions(java_calc_chunks)
    print(f"  Found {len(overloaded)} groups of overloaded methods")

    merged_java = merger.merge_chunks(java_calc_chunks)
    print(f"  After merging: {len(merged_java)} chunks")

    for chunk in merged_java:
        if "add" in chunk.content and chunk.content.count("add") > 1:
            print("    - Merged: all add() overloads")
        else:
            method_match = chunk.content.split("(")[0].split()[-1]
            print(f"    - Kept separate: {method_match}")

    # Show cohesion analysis
    print("\nCohesion Analysis:")
    print("  High cohesion pairs (score >= 0.8):")
    for i, chunk1 in enumerate(chunks[:5]):
        for chunk2 in chunks[i + 1 : i + 3]:
            score = analyzer.calculate_cohesion_score(chunk1, chunk2)
            if score >= 0.8:
                name1 = chunk1.content.split("(")[0].split()[-1]
                name2 = chunk2.content.split("(")[0].split()[-1]
                print(f"    - {name1} <-> {name2}: {score:.2f}")


def demonstrate_configuration_impact():
    """Show how different configurations affect merging."""
    chunks = create_realistic_chunks()[:7]  # Just Person class methods

    print("\n=== Configuration Impact Demo ===\n")

    configs = [
        (
            "Conservative",
            MergeConfig(
                merge_getters_setters=True,
                merge_overloaded_functions=False,
                merge_small_methods=False,
                cohesion_threshold=0.9,
                max_merged_size=10,
            ),
        ),
        (
            "Moderate",
            MergeConfig(
                merge_getters_setters=True,
                merge_overloaded_functions=True,
                merge_small_methods=True,
                small_method_threshold=5,
                cohesion_threshold=0.7,
                max_merged_size=30,
            ),
        ),
        (
            "Aggressive",
            MergeConfig(
                merge_getters_setters=True,
                merge_overloaded_functions=True,
                merge_small_methods=True,
                small_method_threshold=10,
                cohesion_threshold=0.5,
                max_merged_size=100,
            ),
        ),
    ]

    for name, config in configs:
        merger = TreeSitterSemanticMerger(config)
        merged = merger.merge_chunks(chunks)
        print(f"{name} Configuration:")
        print(f"  {len(chunks)} chunks -> {len(merged)} chunks")

        # Count merged vs unmerged
        merged_count = sum(
            1 for c in merged if "def " in c.content and c.content.count("def ") > 1
        )
        print(f"  Merged chunks: {merged_count}")
        print(f"  Unmerged chunks: {len(merged) - merged_count}")
        print()


def main():
    """Run the improved demonstration."""
    print("Tree-sitter Semantic Merging - Improved Demo")
    print("=" * 50)

    demonstrate_targeted_merging()
    demonstrate_configuration_impact()

    print("=" * 50)
    print("Demonstration complete!")


if __name__ == "__main__":
    main()

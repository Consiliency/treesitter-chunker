"""Demo of enhanced chunking strategies."""

import json
from pathlib import Path

from chunker.chunker_config import (
    StrategyConfig,
    get_profile,
    load_strategy_config,
    save_strategy_config,
)
from chunker.parser import get_parser
from chunker.strategies import (
    AdaptiveChunker,
    CompositeChunker,
    HierarchicalChunker,
    SemanticChunker,
)


def demo_semantic_chunking():
    """Demonstrate semantic chunking based on code meaning."""
    print("=== Semantic Chunking Demo ===\n")

    sample_code = '''
import requests
import json

class APIClient:
    """Client for interacting with external API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.example.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}"
        })

    def get_user(self, user_id: str):
        """Fetch user details."""
        response = self.session.get(f"{self.base_url}/users/{user_id}")
        response.raise_for_status()
        return response.json()

    def update_user(self, user_id: str, data: dict):
        """Update user information."""
        response = self.session.put(
            f"{self.base_url}/users/{user_id}",
            json=data
        )
        response.raise_for_status()
        return response.json()

    def validate_response(self, response: dict) -> bool:
        """Validate API response format."""
        required_fields = ['id', 'status', 'data']
        return all(field in response for field in required_fields)

    def handle_error(self, error: Exception):
        """Handle API errors gracefully."""
        if isinstance(error, requests.HTTPError):
            print(f"HTTP Error: {error}")
        else:
            print(f"Unexpected error: {error}")
'''

    # Parse the code
    parser = get_parser("python")
    tree = parser.parse(sample_code.encode())

    # Create semantic chunker
    chunker = SemanticChunker()
    chunker.configure(
        {
            "merge_related": True,  # Merge semantically related methods
            "cohesion_threshold": 0.7,
            "split_complex": True,
        },
    )

    # Perform chunking
    chunks = chunker.chunk(
        tree.root_node,
        sample_code.encode(),
        "api_client.py",
        "python",
    )

    print(f"Found {len(chunks)} semantic chunks:\n")

    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i}: {chunk.node_type}")
        if hasattr(chunk, "metadata") and chunk.metadata:
            semantic = chunk.metadata.get("semantic", {})
            if semantic:
                print(f"  Semantic role: {semantic.get('role', 'unknown')}")
                print(f"  Patterns: {semantic.get('patterns', [])}")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
        print(f"  Dependencies: {chunk.dependencies[:3]}...")
        print()


def demo_hierarchical_chunking():
    """Demonstrate hierarchical chunking preserving structure."""
    print("\n=== Hierarchical Chunking Demo ===\n")

    sample_code = """
class Application:
    def __init__(self):
        self.modules = {}

    class DatabaseModule:
        def connect(self):
            pass

        class QueryBuilder:
            def select(self, table):
                return f"SELECT * FROM {table}"

    class CacheModule:
        def get(self, key):
            pass

        def set(self, key, value):
            pass
"""

    parser = get_parser("python")
    tree = parser.parse(sample_code.encode())

    # Create hierarchical chunker
    chunker = HierarchicalChunker()
    chunker.configure(
        {
            "granularity": "balanced",
            "max_depth": 4,
            "preserve_leaf_nodes": True,
        },
    )

    chunks = chunker.chunk(tree.root_node, sample_code.encode(), "app.py", "python")

    print(f"Found {len(chunks)} hierarchical chunks:\n")

    # Build hierarchy tree for display
    root_chunks = [c for c in chunks if c.parent_chunk_id is None]

    def print_hierarchy(chunk, chunks_list, indent=0):
        prefix = "  " * indent + "└─ " if indent > 0 else ""
        print(f"{prefix}{chunk.node_type}: {chunk.metadata.get('name', 'unnamed')}")

        # Find children
        children = [c for c in chunks_list if c.parent_chunk_id == chunk.chunk_id]
        for child in children:
            print_hierarchy(child, chunks_list, indent + 1)

    for root in root_chunks:
        print_hierarchy(root, chunks)


def demo_adaptive_chunking():
    """Demonstrate adaptive chunking based on complexity."""
    print("\n=== Adaptive Chunking Demo ===\n")

    sample_code = """
# Simple function - should be in larger chunk
def add(a, b):
    return a + b

# Complex function - should be in smaller chunk
def complex_algorithm(data, options):
    cache = {}
    results = []

    for item in data:
        if item['id'] in cache:
            results.append(cache[item['id']])
            continue

        if item['type'] == 'A':
            if item['priority'] > 5:
                if options.get('fast_mode'):
                    processed = quick_process(item)
                else:
                    processed = thorough_process(item)
            else:
                processed = standard_process(item)
        elif item['type'] == 'B':
            try:
                processed = special_process(item)
            except (AttributeError, IndexError, KeyError):
                processed = fallback_process(item)
        else:
            processed = default_process(item)

        cache[item['id']] = processed
        results.append(processed)

    return results

# Medium complexity
def validate_data(data):
    if not data:
        return False

    for item in data:
        if not isinstance(item, dict):
            return False

    return True
"""

    parser = get_parser("python")
    tree = parser.parse(sample_code.encode())

    # Create adaptive chunker
    chunker = AdaptiveChunker()
    chunker.configure(
        {
            "base_chunk_size": 30,
            "complexity_factor": 0.7,  # Strong adaptation to complexity
            "adaptive_aggressiveness": 0.8,
        },
    )

    chunks = chunker.chunk(
        tree.root_node,
        sample_code.encode(),
        "adaptive.py",
        "python",
    )

    print(f"Found {len(chunks)} adaptive chunks:\n")

    for chunk in chunks:
        lines = chunk.end_line - chunk.start_line + 1
        if hasattr(chunk, "metadata") and chunk.metadata:
            metrics = chunk.metadata.get("adaptive_metrics", {})
            print(f"Chunk: {chunk.node_type}")
            print(f"  Size: {lines} lines")
            print(f"  Complexity: {metrics.get('complexity', 0):.1f}")
            print(f"  Ideal size: {metrics.get('ideal_size', 0)} lines")
            print()


def demo_composite_strategy():
    """Demonstrate composite strategy combining multiple approaches."""
    print("\n=== Composite Strategy Demo ===\n")

    # Load a predefined profile
    profile = get_profile("code_review")
    print(f"Using profile: {profile.name}")
    print(f"Description: {profile.description}\n")

    sample_code = '''
class DataProcessor:
    def __init__(self):
        self.data = []

    def process(self, items):
        """Complex processing logic."""
        results = []
        for item in items:
            if self.validate(item):
                result = self.transform(item)
                results.append(result)
        return results

    def validate(self, item):
        return item is not None

    def transform(self, item):
        return str(item).upper()
'''

    parser = get_parser("python")
    tree = parser.parse(sample_code.encode())

    # Create composite chunker with profile
    chunker = CompositeChunker()
    chunker.configure(profile.config.to_dict()["composite"])

    chunks = chunker.chunk(
        tree.root_node,
        sample_code.encode(),
        "processor.py",
        "python",
    )

    print(f"Found {len(chunks)} chunks using composite strategy:\n")

    for chunk in chunks:
        print(f"Chunk: {chunk.node_type}")
        if hasattr(chunk, "metadata") and chunk.metadata:
            print(f"  Quality score: {chunk.metadata.get('quality_score', 0):.2f}")
            print(f"  Strategies: {chunk.metadata.get('strategies', [])}")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
        print()


def demo_configuration():
    """Demonstrate configuration management."""
    print("\n=== Configuration Management Demo ===\n")

    # Create custom configuration
    config = StrategyConfig(
        min_chunk_size=15,
        max_chunk_size=150,
        semantic={
            "complexity_threshold": 12.0,
            "merge_related": True,
        },
        adaptive={
            "base_chunk_size": 40,
            "adaptive_aggressiveness": 0.75,
        },
    )

    # Save configuration
    config_path = Path("custom_chunking_config.json")
    save_strategy_config(config, config_path)
    print(f"Saved configuration to {config_path}")

    # Load and display
    loaded_config = load_strategy_config(config_path)
    print("\nLoaded configuration:")
    print(json.dumps(loaded_config.to_dict(), indent=2))

    # Clean up
    config_path.unlink()


def main():
    """Run all demos."""
    print("Tree-sitter Enhanced Chunking Strategies Demo")
    print("=" * 50)

    demo_semantic_chunking()
    demo_hierarchical_chunking()
    demo_adaptive_chunking()
    demo_composite_strategy()
    demo_configuration()

    print("\n" + "=" * 50)
    print("Demo completed!")


if __name__ == "__main__":
    main()

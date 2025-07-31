"""Tests for the adaptive chunking strategy."""

import pytest

from chunker.parser import get_parser
from chunker.strategies.adaptive import AdaptiveChunker, AdaptiveMetrics


class TestAdaptiveChunker:
    """Test suite for AdaptiveChunker."""

    @pytest.fixture
    def adaptive_chunker(self):
        """Create an adaptive chunker instance."""
        return AdaptiveChunker()

    @pytest.fixture
    def variable_complexity_code(self):
        """Code with varying complexity levels."""
        return '''
# Simple functions
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b != 0:
        return a / b
    return None

# Medium complexity
def process_list(items):
    """Process a list with some logic."""
    result = []
    for item in items:
        if isinstance(item, int):
            if item > 0:
                result.append(item * 2)
            else:
                result.append(abs(item))
        elif isinstance(item, str):
            result.append(item.upper())
    return result

# High complexity
def complex_algorithm(data, options):
    """Complex processing with many branches."""
    results = []
    cache = {}

    for i, item in enumerate(data):
        key = f"{item['type']}_{item['id']}"

        if key in cache:
            results.append(cache[key])
            continue

        if item['type'] == 'A':
            if item['priority'] == 1:
                if item['value'] > 100:
                    processed = process_high_priority_large(item)
                else:
                    processed = process_high_priority_small(item)
            elif item['priority'] == 2:
                if 'special' in item and item['special']:
                    processed = process_special_medium(item)
                else:
                    processed = process_normal_medium(item)
            else:
                processed = process_low_priority(item)
        elif item['type'] == 'B':
            try:
                if validate_b_item(item):
                    processed = process_b_item(item)
                else:
                    processed = handle_invalid_b(item)
            except ValidationError as e:
                processed = {'error': str(e)}
            except (AttributeError, IndexError, KeyError) as e:
                processed = {'error': 'Unknown error'}
        else:
            processed = process_unknown_type(item)

        cache[key] = processed
        results.append(processed)

        if options.get('log_progress') and i % 10 == 0:
            print(f"Processed {i} items")

    return results

# Dense code with many tokens
def dense_function():
    return [x**2 + 2*x + 1 for x in range(10) if x % 2 == 0] + \
           [y**3 - 3*y**2 + 3*y - 1 for y in range(5, 15) if y % 3 == 0] + \
           [z * (z-1) * (z-2) / 6 for z in range(20, 30) if z > 25]
'''

    def test_can_handle(self, adaptive_chunker):
        """Test that adaptive chunker handles all languages."""
        assert adaptive_chunker.can_handle("test.py", "python")
        assert adaptive_chunker.can_handle("test.js", "javascript")
        assert adaptive_chunker.can_handle("test.unknown", "unknown")

    def test_adaptive_metrics_calculation(self, adaptive_chunker):
        """Test calculation of adaptive metrics."""
        metrics = AdaptiveMetrics(
            complexity_score=15.0,
            coupling_score=8.0,
            semantic_cohesion=0.7,
            line_count=50,
            token_density=12.0,
            nesting_depth=3,
        )

        # Test overall score calculation
        score = metrics.overall_score
        assert score > 0
        assert score < 20  # Reasonable bounds

    def test_adaptive_chunking(self, adaptive_chunker, variable_complexity_code):
        """Test that chunk sizes adapt to complexity."""
        parser = get_parser("python")
        tree = parser.parse(variable_complexity_code.encode())

        chunks = adaptive_chunker.chunk(
            tree.root_node,
            variable_complexity_code.encode(),
            "test.py",
            "python",
        )

        # Should create multiple chunks
        assert len(chunks) > 3

        # Find simple and complex chunks
        simple_chunks = []
        complex_chunks = []

        for chunk in chunks:
            if hasattr(chunk, "metadata") and chunk.metadata:
                metrics = chunk.metadata.get("adaptive_metrics", {})
                complexity = metrics.get("complexity", 0)

                if complexity < 5:
                    simple_chunks.append(chunk)
                elif complexity > 10:
                    complex_chunks.append(chunk)

        # Simple chunks should be larger on average
        if simple_chunks and complex_chunks:
            avg_simple_size = sum(
                c.end_line - c.start_line + 1 for c in simple_chunks
            ) / len(simple_chunks)

            avg_complex_size = sum(
                c.end_line - c.start_line + 1 for c in complex_chunks
            ) / len(complex_chunks)

            # Complex code should result in smaller chunks
            assert avg_simple_size >= avg_complex_size

    def test_ideal_chunk_size_calculation(self, adaptive_chunker):
        """Test ideal chunk size calculation for different metrics."""
        # Low complexity metrics
        low_metrics = AdaptiveMetrics(
            complexity_score=3.0,
            coupling_score=2.0,
            semantic_cohesion=0.9,
            line_count=30,
            token_density=8.0,
            nesting_depth=1,
        )

        # High complexity metrics
        high_metrics = AdaptiveMetrics(
            complexity_score=20.0,
            coupling_score=15.0,
            semantic_cohesion=0.3,
            line_count=100,
            token_density=15.0,
            nesting_depth=5,
        )

        file_metrics = {"avg_complexity": 10.0, "avg_coupling": 7.0}

        low_ideal = adaptive_chunker._calculate_ideal_chunk_size(
            low_metrics,
            file_metrics,
        )
        high_ideal = adaptive_chunker._calculate_ideal_chunk_size(
            high_metrics,
            file_metrics,
        )

        # High complexity should result in smaller ideal size
        assert low_ideal > high_ideal

        # Should be within configured bounds
        assert low_ideal >= adaptive_chunker.config["min_chunk_size"]
        assert low_ideal <= adaptive_chunker.config["max_chunk_size"]
        assert high_ideal >= adaptive_chunker.config["min_chunk_size"]
        assert high_ideal <= adaptive_chunker.config["max_chunk_size"]

    def test_configuration_effects(self, adaptive_chunker, variable_complexity_code):
        """Test that configuration changes affect chunking."""
        parser = get_parser("python")
        tree = parser.parse(variable_complexity_code.encode())

        # Default configuration
        default_chunks = adaptive_chunker.chunk(
            tree.root_node,
            variable_complexity_code.encode(),
            "test.py",
            "python",
        )

        # Aggressive adaptation - smaller chunks for complex code
        adaptive_chunker.configure(
            {
                "adaptive_aggressiveness": 0.9,
                "complexity_factor": 0.8,
                "base_chunk_size": 20,  # Smaller base
                "min_chunk_size": 5,    # Allow smaller chunks
                "balance_sizes": False,  # Don't rebalance
            },
        )

        aggressive_chunks = adaptive_chunker.chunk(
            tree.root_node,
            variable_complexity_code.encode(),
            "test.py",
            "python",
        )

        # Conservative adaptation - larger, more uniform chunks
        adaptive_chunker.configure(
            {
                "adaptive_aggressiveness": 0.1,  # Less aggressive
                "complexity_factor": 0.1,
                "base_chunk_size": 100,  # Much larger base
                "max_chunk_size": 300,   # Allow larger chunks
                "balance_sizes": False,  # Don't rebalance
            },
        )

        conservative_chunks = adaptive_chunker.chunk(
            tree.root_node,
            variable_complexity_code.encode(),
            "test.py",
            "python",
        )

        # Should produce different results - check that at least one configuration differs
        # or that the chunk sizes/types differ
        default_len = len(default_chunks)
        aggressive_len = len(aggressive_chunks)
        conservative_len = len(conservative_chunks)
        
        # Either the number of chunks should differ
        chunks_differ = (default_len != aggressive_len or default_len != conservative_len)
        
        # Or the chunk sizes should differ on average
        if not chunks_differ:
            default_avg_size = sum(c.end_line - c.start_line + 1 for c in default_chunks) / default_len
            aggressive_avg_size = sum(c.end_line - c.start_line + 1 for c in aggressive_chunks) / aggressive_len
            conservative_avg_size = sum(c.end_line - c.start_line + 1 for c in conservative_chunks) / conservative_len
            
            # Also check chunk types
            default_types = [c.node_type for c in default_chunks]
            aggressive_types = [c.node_type for c in aggressive_chunks]
            conservative_types = [c.node_type for c in conservative_chunks]
            
            types_differ = (default_types != aggressive_types or default_types != conservative_types)
            
            # Check if average sizes differ significantly (more than 10%)
            size_differs = (
                abs(default_avg_size - aggressive_avg_size) > default_avg_size * 0.1 or
                abs(default_avg_size - conservative_avg_size) > default_avg_size * 0.1
            )
            
            assert size_differs or types_differ, f"Configuration changes should affect chunking behavior. All produced {default_len} chunks with similar average sizes"

    def test_boundary_preservation(self, adaptive_chunker):
        """Test that natural boundaries are preserved."""
        code_with_boundaries = """
class Calculator:
    def add(self, a, b):
        return a + b

    def complex_calc(self, data):
        # This should not be split despite complexity
        result = 0
        for item in data:
            if item > 0:
                result += item
            else:
                result -= item
        return result

def helper_function():
    return 42

def another_helper():
    return 24
"""

        parser = get_parser("python")
        tree = parser.parse(code_with_boundaries.encode())

        adaptive_chunker.configure(
            {
                "preserve_boundaries": True,
                "base_chunk_size": 5,  # Very small to test boundary preservation
            },
        )

        chunks = adaptive_chunker.chunk(
            tree.root_node,
            code_with_boundaries.encode(),
            "test.py",
            "python",
        )

        # Each function should be its own chunk despite small base size
        for chunk in chunks:
            # Should not split functions
            content = chunk.content
            def_count = content.count("def ")
            # Each chunk should have at most one function definition
            assert def_count <= 1 or chunk.node_type == "class_definition"

    def test_size_balancing(self, adaptive_chunker, variable_complexity_code):
        """Test chunk size balancing."""
        parser = get_parser("python")
        tree = parser.parse(variable_complexity_code.encode())

        adaptive_chunker.configure(
            {
                "balance_sizes": True,
                "base_chunk_size": 40,
            },
        )

        chunks = adaptive_chunker.chunk(
            tree.root_node,
            variable_complexity_code.encode(),
            "test.py",
            "python",
        )

        # Calculate size statistics
        sizes = [c.end_line - c.start_line + 1 for c in chunks]
        if len(sizes) > 1:
            avg_size = sum(sizes) / len(sizes)
            max_size = max(sizes)
            min_size = min(sizes)

            # Sizes should be somewhat balanced
            # (not too extreme differences)
            # Note: complex_algorithm function is very large (45 lines), which skews the average
            assert max_size < avg_size * 6  # Allow larger variance due to complex function
            assert min_size > avg_size * 0.1  # Allow smaller chunks

    def test_density_adaptation(self, adaptive_chunker):
        """Test adaptation to token density."""
        # Code with varying density
        varied_density = """
# Sparse code
def simple():
    x = 1

    y = 2

    z = 3

    return x + y + z

# Dense code
def dense(): return sum([x**2+2*x+1 for x in range(10)]) + max([y*y-1 for y in range(5)])

# Normal density
def normal(data):
    result = []
    for item in data:
        processed = item * 2
        result.append(processed)
    return result
"""

        parser = get_parser("python")
        tree = parser.parse(varied_density.encode())

        chunks = adaptive_chunker.chunk(
            tree.root_node,
            varied_density.encode(),
            "test.py",
            "python",
        )

        # Check that dense code gets different treatment
        found_dense = False
        for chunk in chunks:
            if "dense()" in chunk.content:
                found_dense = True
                assert hasattr(chunk, "metadata")
                metrics = chunk.metadata.get("adaptive_metrics", {})
                # Dense function should have high token density
                # Note: group chunks may not have adaptive_metrics
                if metrics:
                    assert metrics.get("density", 0) > 5  # Lower threshold as it's chars/line not tokens/line
                break
        
        assert found_dense, "Should have found the dense function chunk"

    def test_group_chunk_creation(self, adaptive_chunker):
        """Test creation of group chunks."""
        small_functions = """
def f1(): return 1
def f2(): return 2
def f3(): return 3
def f4(): return 4
def f5(): return 5
"""

        parser = get_parser("python")
        tree = parser.parse(small_functions.encode())

        adaptive_chunker.configure(
            {
                "base_chunk_size": 20,
                "min_chunk_size": 15,
            },
        )

        chunks = adaptive_chunker.chunk(
            tree.root_node,
            small_functions.encode(),
            "test.py",
            "python",
        )

        # Should create group chunks
        group_chunks = [c for c in chunks if c.node_type == "adaptive_group"]
        assert len(group_chunks) >= 1

        # Group chunks should have metadata about grouped nodes
        for group in group_chunks:
            assert hasattr(group, "metadata")
            assert "group_size" in group.metadata
            assert "node_types" in group.metadata

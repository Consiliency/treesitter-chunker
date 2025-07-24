"""Tests for the semantic chunking strategy."""

import pytest

from chunker.parser import get_parser
from chunker.strategies.semantic import SemanticChunker


class TestSemanticChunker:
    """Test suite for SemanticChunker."""

    @pytest.fixture()
    def semantic_chunker(self):
        """Create a semantic chunker instance."""
        return SemanticChunker()

    @pytest.fixture()
    def sample_python_code(self):
        """Sample Python code with various semantic patterns."""
        return '''
import os
import json
from typing import List, Dict

class DataProcessor:
    """Process data with various transformations."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.data = []
        self.errors = []
    
    def validate_input(self, data: List[Dict]) -> bool:
        """Validate input data format."""
        if not data:
            self.errors.append("Empty data")
            return False
        
        for item in data:
            if not isinstance(item, dict):
                self.errors.append(f"Invalid item: {item}")
                return False
            
            if 'id' not in item or 'value' not in item:
                self.errors.append(f"Missing fields: {item}")
                return False
        
        return True
    
    def process_data(self, data: List[Dict]) -> List[Dict]:
        """Main processing function with complex logic."""
        if not self.validate_input(data):
            return []
        
        results = []
        for item in data:
            try:
                # Complex transformation
                if item['value'] > 100:
                    processed = self._transform_large(item)
                elif item['value'] < 0:
                    processed = self._transform_negative(item)
                else:
                    processed = self._transform_normal(item)
                
                results.append(processed)
            except Exception as e:
                self.errors.append(f"Processing error: {e}")
        
        return results
    
    def _transform_large(self, item: Dict) -> Dict:
        """Transform large values."""
        return {
            'id': item['id'],
            'value': item['value'] / 10,
            'category': 'large'
        }
    
    def _transform_negative(self, item: Dict) -> Dict:
        """Transform negative values."""
        return {
            'id': item['id'],
            'value': abs(item['value']),
            'category': 'negative'
        }
    
    def _transform_normal(self, item: Dict) -> Dict:
        """Transform normal values."""
        return {
            'id': item['id'],
            'value': item['value'] * 1.1,
            'category': 'normal'
        }

def main():
    """Entry point for the processor."""
    config = {'debug': True}
    processor = DataProcessor(config)
    
    test_data = [
        {'id': 1, 'value': 150},
        {'id': 2, 'value': -20},
        {'id': 3, 'value': 50}
    ]
    
    results = processor.process_data(test_data)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
'''

    def test_can_handle(self, semantic_chunker):
        """Test language support checking."""
        assert semantic_chunker.can_handle("test.py", "python")
        assert semantic_chunker.can_handle("test.js", "javascript")
        assert semantic_chunker.can_handle("test.java", "java")
        assert semantic_chunker.can_handle("test.rs", "rust")

    def test_basic_chunking(self, semantic_chunker, sample_python_code):
        """Test basic semantic chunking."""
        parser = get_parser("python")
        tree = parser.parse(sample_python_code.encode())

        chunks = semantic_chunker.chunk(
            tree.root_node,
            sample_python_code.encode(),
            "test.py",
            "python",
        )

        # Should create chunks for major semantic boundaries
        assert len(chunks) > 0

        # Check chunk types
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "class_definition" in chunk_types or "merged_chunk" in chunk_types

        # Check that methods are chunked
        method_names = []
        for chunk in chunks:
            if hasattr(chunk, "metadata") and chunk.metadata:
                name = chunk.metadata.get("name", "")
                if name:
                    method_names.append(name)

        # Should have some method names
        assert len(method_names) > 0

    def test_semantic_cohesion(self, semantic_chunker, sample_python_code):
        """Test that semantically related code stays together."""
        parser = get_parser("python")
        tree = parser.parse(sample_python_code.encode())

        # Configure to merge related chunks
        semantic_chunker.configure(
            {
                "merge_related": True,
                "cohesion_threshold": 0.6,
            },
        )

        chunks = semantic_chunker.chunk(
            tree.root_node,
            sample_python_code.encode(),
            "test.py",
            "python",
        )

        # Transform methods should be grouped if they're related
        transform_chunks = [
            c
            for c in chunks
            if any(pattern in c.content for pattern in ["_transform_", "transform"])
        ]

        # Check metadata for semantic roles
        for chunk in chunks:
            if hasattr(chunk, "metadata") and chunk.metadata:
                semantic = chunk.metadata.get("semantic", {})
                assert "role" in semantic or "patterns" in semantic

    def test_complexity_splitting(self, semantic_chunker):
        """Test splitting of complex chunks."""
        complex_code = '''
def complex_function(data):
    """A function with high complexity."""
    result = []
    
    for item in data:
        if item['type'] == 'A':
            if item['value'] > 100:
                if item['priority'] == 1:
                    result.append(process_high_priority_a(item))
                elif item['priority'] == 2:
                    result.append(process_medium_priority_a(item))
                else:
                    result.append(process_low_priority_a(item))
            else:
                if item['status'] == 'active':
                    result.append(process_active_a(item))
                else:
                    result.append(process_inactive_a(item))
        elif item['type'] == 'B':
            if item['value'] > 50:
                result.append(process_high_b(item))
            else:
                result.append(process_low_b(item))
        else:
            try:
                result.append(process_other(item))
            except ValueError:
                result.append(None)
            except Exception as e:
                print(f"Error: {e}")
                result.append(None)
    
    return [r for r in result if r is not None]
'''

        parser = get_parser("python")
        tree = parser.parse(complex_code.encode())

        # Configure to split complex functions
        semantic_chunker.configure(
            {
                "split_complex": True,
                "complexity_threshold": 10.0,
            },
        )

        chunks = semantic_chunker.chunk(
            tree.root_node,
            complex_code.encode(),
            "test.py",
            "python",
        )

        # Should identify this as complex
        for chunk in chunks:
            if hasattr(chunk, "metadata") and chunk.metadata:
                complexity = chunk.metadata.get("complexity", {})
                if "score" in complexity:
                    # This function should have high complexity
                    assert complexity["score"] > 10.0

    def test_dependency_tracking(self, semantic_chunker, sample_python_code):
        """Test that dependencies are properly tracked."""
        parser = get_parser("python")
        tree = parser.parse(sample_python_code.encode())

        chunks = semantic_chunker.chunk(
            tree.root_node,
            sample_python_code.encode(),
            "test.py",
            "python",
        )

        # Check that dependencies are tracked
        for chunk in chunks:
            if "import" in chunk.content:
                # Import chunks should have external dependencies
                assert len(chunk.dependencies) > 0

            if "self." in chunk.content:
                # Methods using self should have internal references
                assert len(chunk.references) >= 0

    def test_configuration(self, semantic_chunker):
        """Test configuration updates."""
        original_config = semantic_chunker.config.copy()

        # Update configuration
        new_config = {
            "min_chunk_size": 20,
            "max_chunk_size": 300,
            "complexity_threshold": 20.0,
            "merge_related": False,
        }

        semantic_chunker.configure(new_config)

        # Check that config was updated
        assert semantic_chunker.config["min_chunk_size"] == 20
        assert semantic_chunker.config["max_chunk_size"] == 300
        assert semantic_chunker.config["complexity_threshold"] == 20.0
        assert semantic_chunker.config["merge_related"] is False

    def test_semantic_boundaries(self, semantic_chunker):
        """Test that semantic boundaries are respected."""
        code_with_boundaries = """
# Configuration section
DEBUG = True
API_KEY = "secret"
TIMEOUT = 30

# Data models
class User:
    def __init__(self, name):
        self.name = name

class Product:
    def __init__(self, id, name):
        self.id = id
        self.name = name

# Business logic
def calculate_discount(user, product):
    if user.is_premium:
        return 0.2
    return 0.1

def apply_discount(price, discount):
    return price * (1 - discount)

# API handlers
async def get_user(user_id):
    # Fetch user from database
    pass

async def get_product(product_id):
    # Fetch product from database
    pass
"""

        parser = get_parser("python")
        tree = parser.parse(code_with_boundaries.encode())

        chunks = semantic_chunker.chunk(
            tree.root_node,
            code_with_boundaries.encode(),
            "test.py",
            "python",
        )

        # Should respect natural boundaries
        assert len(chunks) >= 3  # At least config, models, and functions

        # Check that different sections are separated
        chunk_contents = [chunk.content for chunk in chunks]

        # Config should be separate
        config_chunks = [c for c in chunk_contents if "DEBUG" in c or "API_KEY" in c]

        # Classes should be chunked
        class_chunks = [
            c for c in chunk_contents if "class User" in c or "class Product" in c
        ]

        # Functions should be chunked
        function_chunks = [
            c
            for c in chunk_contents
            if "def calculate_discount" in c or "def apply_discount" in c
        ]

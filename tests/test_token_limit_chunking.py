"""Tests for token limit handling in tree-sitter chunker."""

from chunker import CodeChunk, chunk_text_with_token_limit, count_chunk_tokens


class TestTokenLimitChunking:
    """Test token limit handling functionality."""

    def test_chunk_text_with_token_limit_basic(self):
        """Test basic token limit chunking."""
        code = """
def hello():
    print("Hello, World!")

def calculate_sum(a, b):
    # This is a simple function
    result = a + b
    print(f"The sum is {result}")
    return result
"""

        # Chunk with a generous token limit
        chunks = chunk_text_with_token_limit(code, "python", max_tokens=100)

        # Should have 2 chunks (one per function)
        assert len(chunks) == 2

        # Each chunk should have token count metadata
        for chunk in chunks:
            assert "token_count" in chunk.metadata
            assert chunk.metadata["token_count"] <= 100
            assert chunk.metadata["tokenizer_model"] == "gpt-4"

    def test_chunk_splits_large_function(self):
        """Test that large functions are split when exceeding token limit."""
        # Create a large function
        large_function = '''
def process_data(data):
    """Process data with many steps."""
    # Step 1: Validate input
    if not isinstance(data, list):
        raise ValueError("Data must be a list")
    
    # Step 2: Initialize variables
    results = []
    errors = []
    processed_count = 0
    
    # Step 3: Process each item
    for i, item in enumerate(data):
        try:
            # Validate item
            if not isinstance(item, dict):
                errors.append(f"Item {i} is not a dict")
                continue
                
            # Extract fields
            value = item.get('value', 0)
            multiplier = item.get('multiplier', 1)
            
            # Calculate result
            result = value * multiplier
            
            # Apply transformations
            if result > 100:
                result = result * 0.9
            elif result < 10:
                result = result * 1.1
                
            # Store result
            results.append({
                'index': i,
                'original': value,
                'result': result
            })
            
            processed_count += 1
            
        except Exception as e:
            errors.append(f"Error processing item {i}: {e}")
    
    # Step 4: Generate summary
    summary = {
        'total': len(data),
        'processed': processed_count,
        'errors': len(errors),
        'average': sum(r['result'] for r in results) / len(results) if results else 0
    }
    
    return results, errors, summary
'''

        # Chunk with a small token limit to force splitting
        chunks = chunk_text_with_token_limit(large_function, "python", max_tokens=200)

        # Should be split into multiple chunks
        assert len(chunks) > 1

        # All chunks should respect token limit
        for chunk in chunks:
            assert chunk.metadata["token_count"] <= 200
            assert chunk.metadata.get("is_split", False) or len(chunks) == 1

    def test_chunk_class_splits_by_methods(self):
        """Test that classes are split by methods when possible."""
        class_code = '''
class Calculator:
    """A calculator class."""
    
    def __init__(self):
        self.history = []
        
    def add(self, a, b):
        """Add two numbers."""
        result = a + b
        self.history.append(f"add({a}, {b}) = {result}")
        return result
        
    def multiply(self, a, b):
        """Multiply two numbers."""
        result = a * b
        self.history.append(f"multiply({a}, {b}) = {result}")
        return result
        
    def divide(self, a, b):
        """Divide two numbers."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(f"divide({a}, {b}) = {result}")
        return result
'''

        # Chunk with moderate limit
        chunks = chunk_text_with_token_limit(class_code, "python", max_tokens=150)

        # Should split the class
        assert len(chunks) >= 2

        # Check that class header is preserved in splits
        split_chunks = [c for c in chunks if c.metadata.get("is_split", False)]
        if split_chunks:
            for chunk in split_chunks:
                # Class definition should be included
                assert (
                    "class Calculator" in chunk.content
                    or chunk.node_type.startswith("method_")
                )

    def test_count_chunk_tokens(self):
        """Test token counting for individual chunks."""
        chunk = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="def hello():\n    print('Hello, World!')",
        )

        # Count tokens
        token_count = count_chunk_tokens(chunk)

        # Should return a reasonable token count
        assert token_count > 0
        assert token_count < 50  # Simple function should be less than 50 tokens

    def test_different_tokenizer_models(self):
        """Test using different tokenizer models."""
        code = "def hello(): return 'Hello'"

        # Try different models
        for model in ["gpt-4", "claude", "gpt-3.5-turbo"]:
            chunks = chunk_text_with_token_limit(
                code,
                "python",
                max_tokens=50,
                model=model,
            )

            assert len(chunks) == 1
            assert chunks[0].metadata["tokenizer_model"] == model
            assert chunks[0].metadata["token_count"] > 0

    def test_metadata_preservation(self):
        """Test that metadata extraction still works with token limits."""
        code = '''
def calculate(x, y):
    """Calculate something."""
    return x + y
'''

        chunks = chunk_text_with_token_limit(
            code,
            "python",
            max_tokens=100,
            extract_metadata=True,
        )

        assert len(chunks) == 1
        chunk = chunks[0]

        # Should have both token metadata and regular metadata
        assert "token_count" in chunk.metadata
        assert "signature" in chunk.metadata
        assert chunk.metadata["signature"]["name"] == "calculate"

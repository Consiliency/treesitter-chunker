"""Example demonstrating token counting integration with Tree-sitter chunks."""

import json
import os
import tempfile

from chunker.token import TiktokenCounter
from chunker.token.chunker import TreeSitterTokenAwareChunker


def main():
    """Demonstrate token counting features."""

    # Example 1: Basic token counting
    print("=== Basic Token Counting ===")
    counter = TiktokenCounter()

    sample_code = """
def calculate_fibonacci(n):
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
"""

    token_count = counter.count_tokens(sample_code)
    print(f"Sample code has {token_count} tokens")
    print(f"GPT-4 limit: {counter.get_token_limit('gpt-4')} tokens")
    print(f"Claude limit: {counter.get_token_limit('claude')} tokens")

    # Example 2: Chunking with token information
    print("\n=== Token-Aware Chunking ===")
    chunker = TreeSitterTokenAwareChunker()

    # Create a test file
    test_file = "examples/example.py"

    # Regular chunking with token info added
    chunks = chunker.chunk_file(test_file, "python")

    print(f"\nFound {len(chunks)} chunks in {test_file}")
    for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
        print(f"\nChunk {i+1}:")
        print(f"  Type: {chunk.node_type}")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
        print(f"  Tokens: {chunk.metadata.get('token_count', 'N/A')}")
        print(f"  Content preview: {chunk.content[:50]}...")

    # Example 3: Chunking with token limits
    print("\n=== Chunking with Token Limits ===")

    # Create a large class for demonstration
    large_class = '''
class DataProcessor:
    """A class with many methods to demonstrate splitting."""

    def __init__(self, config):
        self.config = config
        self.data = []
        self.results = {}
        self.cache = {}
        self.errors = []

    def load_data(self, file_path):
        """Load data from file."""
        with Path(file_path).open('r') as f:
            self.data = json.load(f)
        return len(self.data)

    def validate_data(self):
        """Validate loaded data."""
        errors = []
        for i, item in enumerate(self.data):
            if not isinstance(item, dict):
                errors.append(f"Item {i} is not a dictionary")
            if 'id' not in item:
                errors.append(f"Item {i} missing 'id' field")
            if 'value' not in item:
                errors.append(f"Item {i} missing 'value' field")
        self.errors = errors
        return len(errors) == 0

    def process_data(self):
        """Process the validated data."""
        for item in self.data:
            item_id = item.get('id')
            value = item.get('value', 0)

            # Complex processing logic
            processed = value * 2 + len(str(value))

            # Store in results
            self.results[item_id] = {
                'original': value,
                'processed': processed,
                'timestamp': 'now'
            }

            # Cache for future use
            self.cache[item_id] = processed

        return len(self.results)

    def get_summary(self):
        """Get processing summary."""
        return {
            'total_items': len(self.data),
            'processed_items': len(self.results),
            'errors': len(self.errors),
            'cache_size': len(self.cache)
        }
'''

    # Write to a temporary file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(large_class)
        temp_file = f.name

    # Chunk with a small token limit to force splitting
    limited_chunks = chunker.chunk_with_token_limit(
        temp_file,
        "python",
        max_tokens=150,
        model="gpt-4",
    )

    print("\nOriginal class would be 1 chunk, but with 150 token limit:")
    print(f"Split into {len(limited_chunks)} chunks")

    for i, chunk in enumerate(limited_chunks):
        is_split = chunk.metadata.get("is_split", False)
        print(f"\nChunk {i+1}:")
        print(f"  Type: {chunk.node_type}")
        print(f"  Tokens: {chunk.metadata['token_count']}")
        print(f"  Is split: {is_split}")
        if is_split:
            print(f"  Split index: {chunk.metadata.get('split_index')}")
        print(f"  First line: {chunk.content.split(chr(10))[0][:60]}...")

    # Example 4: Different models
    print("\n=== Different Tokenizer Models ===")

    sample = "This is a sample text to show different tokenizer models."

    for model in ["gpt-4", "claude", "gpt-3.5-turbo"]:
        count = counter.count_tokens(sample, model)
        limit = counter.get_token_limit(model)
        print(f"{model}: {count} tokens (limit: {limit})")

    # Clean up

    os.unlink(temp_file)

    print("\n=== Token Metadata Structure ===")
    if chunks:
        print("Sample chunk metadata:")
        print(json.dumps(chunks[0].metadata, indent=2))


if __name__ == "__main__":
    main()

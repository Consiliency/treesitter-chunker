#!/usr/bin/env python3
"""Standalone demo of token integration functionality."""

import sys
import tempfile

sys.path.insert(0, ".")

import pathlib

from chunker.token.chunker import TreeSitterTokenAwareChunker
from chunker.token.counter import TiktokenCounter
from chunker.types import CodeChunk


def demo():
    print("=== Token Integration Demo ===\n")

    # 1. Basic token counting
    print("1. Basic Token Counting")
    print("-" * 40)
    counter = TiktokenCounter()

    samples = [
        "Hello, world!",
        "def add(a, b): return a + b",
        "The quick brown fox jumps over the lazy dog.",
    ]

    for text in samples:
        count = counter.count_tokens(text)
        print(f"Text: '{text}'")
        print(f"Tokens: {count}\n")

    # 2. Model token limits
    print("\n2. Model Token Limits")
    print("-" * 40)
    models = ["gpt-4", "gpt-3.5-turbo", "claude", "claude-3"]
    for model in models:
        limit = counter.get_token_limit(model)
        print(f"{model}: {limit:,} tokens")

    # 3. Text splitting by tokens
    print("\n\n3. Text Splitting by Tokens")
    print("-" * 40)
    long_text = "This is a sentence. " * 20
    chunks = counter.split_text_by_tokens(long_text, max_tokens=30)
    print(
        f"Original text: {len(long_text)} chars, {counter.count_tokens(long_text)} tokens",
    )
    print(f"Split into {len(chunks)} chunks with max 30 tokens each:")
    for i, chunk in enumerate(chunks[:3]):  # Show first 3
        tokens = counter.count_tokens(chunk)
        print(f"  Chunk {i + 1}: {tokens} tokens, {len(chunk)} chars")

    # 4. Token-aware chunking
    print("\n\n4. Token-Aware Chunking")
    print("-" * 40)

    # Create a test file
    test_code = '''
def calculate_sum(numbers):
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        total += num
    return total

def calculate_average(numbers):
    """Calculate average of numbers."""
    if not numbers:
        return 0
    return calculate_sum(numbers) / len(numbers)

class Statistics:
    """A class for statistical calculations."""

    def __init__(self):
        self.data = []

    def add_data(self, values):
        """Add data values."""
        self.data.extend(values)

    def mean(self):
        """Calculate mean."""
        return calculate_average(self.data)
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_file = f.name

    try:
        # Create chunker
        chunker = TreeSitterTokenAwareChunker()

        # Create a simple chunk to demonstrate add_token_info
        chunk = CodeChunk(
            language="python",
            file_path=temp_file,
            node_type="function_definition",
            start_line=1,
            end_line=7,
            byte_start=0,
            byte_end=200,
            parent_context="module",
            content='''def calculate_sum(numbers):
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        total += num
    return total''',
        )

        # Add token info
        enhanced_chunks = chunker.add_token_info([chunk])
        enhanced = enhanced_chunks[0]

        print("Sample chunk with token info:")
        print(f"  Type: {enhanced.node_type}")
        print(f"  Lines: {enhanced.start_line}-{enhanced.end_line}")
        print(f"  Token count: {enhanced.metadata['token_count']}")
        print(f"  Tokenizer model: {enhanced.metadata['tokenizer_model']}")
        print(
            f"  Chars per token: {enhanced.metadata.get('chars_per_token', 'N/A'):.2f}",
        )

    finally:
        pathlib.Path(temp_file).unlink()

    print("\n\n=== Demo Complete ===")


if __name__ == "__main__":
    demo()

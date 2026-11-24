"""Tests for token limit handling in tree-sitter chunker."""

import pytest
import tiktoken

from chunker import (
    CodeChunk,
    chunk_text,
    chunk_text_with_token_limit,
    count_chunk_tokens,
)
from chunker.chunker import chunk_file_with_token_limit
from chunker.token import TiktokenCounter
from chunker.token.chunker import TreeSitterTokenAwareChunker


class TestTokenLimitChunking:
    """Test token limit handling functionality."""

    @staticmethod
    def test_chunk_text_with_token_limit_basic():
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
        chunks = chunk_text_with_token_limit(code, "python", max_tokens=100)
        assert len(chunks) == 2
        for chunk in chunks:
            assert "token_count" in chunk.metadata
            assert chunk.metadata["token_count"] <= 100
            assert chunk.metadata["tokenizer_model"] == "gpt-4"

    @staticmethod
    def test_chunk_splits_large_function():
        """Test that large functions are split when exceeding token limit."""
        large_function = """
def process_data(data):
    ""\"Process data with many steps.""\"
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

        except (IndexError, KeyError) as e:
            errors.append(f"Error processing item {i}: {e}")

    # Step 4: Generate summary
    summary = {
        'total': len(data),
        'processed': processed_count,
        'errors': len(errors),
        'average': sum(r['result'] for r in results) / len(results) if results else 0
    }

    return results, errors, summary
"""
        chunks = chunk_text_with_token_limit(large_function, "python", max_tokens=200)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["token_count"] <= 200
            assert chunk.metadata.get("is_split", False) or len(chunks) == 1

    @staticmethod
    def test_chunk_class_splits_by_methods():
        """Test that classes are split by methods when possible."""
        class_code = """
class Calculator:
    ""\"A calculator class.""\"

    def __init__(self):
        self.history = []

    def add(self, a, b):
        ""\"Add two numbers.""\"
        result = a + b
        self.history.append(f"add({a}, {b}) = {result}")
        return result

    def multiply(self, a, b):
        ""\"Multiply two numbers.""\"
        result = a * b
        self.history.append(f"multiply({a}, {b}) = {result}")
        return result

    def divide(self, a, b):
        ""\"Divide two numbers.""\"
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(f"divide({a}, {b}) = {result}")
        return result
"""
        chunks = chunk_text_with_token_limit(class_code, "python", max_tokens=150)
        assert len(chunks) >= 2
        split_chunks = [c for c in chunks if c.metadata.get("is_split", False)]
        if split_chunks:
            for chunk in split_chunks:
                # Class context is preserved in parent_context (not prepended
                # into content) so the span slices back to content. Assert the
                # invariant directly — no always-true node_type escape hatch.
                assert "class Calculator" in (chunk.parent_context or "")

    @classmethod
    def test_count_chunk_tokens(cls):
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
            content="""def hello():
    print('Hello, World!')""",
        )
        token_count = count_chunk_tokens(chunk)
        assert token_count > 0
        assert token_count < 50

    @staticmethod
    def test_different_tokenizer_models():
        """Test using different tokenizer models."""
        code = "def hello(): return 'Hello'"
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

    @staticmethod
    def test_metadata_preservation():
        """Test that metadata extraction still works with token limits."""
        code = (
            '\ndef calculate(x, y):\n    """Calculate something."""\n    return x + y\n'
        )
        chunks = chunk_text_with_token_limit(
            code,
            "python",
            max_tokens=100,
            extract_metadata=True,
        )
        assert len(chunks) == 1
        chunk = chunks[0]
        assert "token_count" in chunk.metadata
        assert "signature" in chunk.metadata
        assert chunk.metadata["signature"]["name"] == "calculate"


def assert_partition(parent, result, raw, budget, encoding, model):
    parts = [
        part
        for part in result
        if part.metadata.get("original_chunk_id") == parent.chunk_id
    ]
    assert parts
    cursor = parent.byte_start
    line = parent.start_line
    assert "".join(part.content for part in parts) == parent.content
    for index, part in enumerate(parts, 1):
        assert part.content
        assert part.byte_start == cursor
        assert raw[cursor : part.byte_end] == part.content.encode()
        assert part.start_line == line
        line += part.content.count("\n")
        assert part.end_line == line
        cursor = part.byte_end
        count = len(encoding.encode(part.content))
        assert part.metadata["token_count"] == count
        assert part.metadata["tokenizer_model"] == model
        assert part.metadata["split_index"] == index
        assert part.parent_chunk_id == parent.chunk_id
        if count > budget:
            assert len(part.content) == 1
            assert part.metadata["token_limit_exceeded"] is True
        else:
            assert "token_limit_exceeded" not in part.metadata
    assert cursor == parent.byte_end
    return parts


LONG_LITERAL = 'def f(): return "' + "ABCDEFGHIJKLMNOPQRSTUVWX" * 5 + '"'
LARGE_METHOD = "    def f(self):\n" + "".join(
    f"        value_{i} = {i}\n" for i in range(20)
)
SMALL_METHOD = "    def g(self): return 2\n"


@pytest.mark.parametrize(
    ("code", "budget"),
    [
        (LONG_LITERAL, 8),
        ("class C:\n" + LARGE_METHOD, 20),
        ("class C:\n" + SMALL_METHOD + LARGE_METHOD + SMALL_METHOD, 20),
        ("class C:\n    s = '" + "aZ" * 100 + "'\n" + SMALL_METHOD, 20),
        ("class C:\n    s = '" + "aZ" * 100 + "'", 20),
        ('def f(): return "🌍"', 1),
    ],
    ids=[
        "long-literal",
        "large-method",
        "mixed-methods",
        "large-header",
        "no-methods",
        "singleton",
    ],
)
def test_semantic_parent_reconstruction(code, budget):
    enc = tiktoken.get_encoding("cl100k_base")
    parents = chunk_text(code, "python")
    result = chunk_text_with_token_limit(code, "python", budget)
    assert parents
    for parent in parents:
        if len(enc.encode(parent.content)) <= budget:
            assert any(child.chunk_id == parent.chunk_id for child in result)
            continue
        parts = assert_partition(parent, result, code.encode(), budget, enc, "gpt-4")
        if parent.node_type == "class_definition" and "def " in code:
            assert all("class C:" in part.parent_context for part in parts)
            if SMALL_METHOD in code:
                assert sum(
                    SMALL_METHOD.rstrip() in part.content for part in parts
                ) == code.count(SMALL_METHOD)
        if "🌍" in code:
            assert [
                p.content for p in parts if p.metadata.get("token_limit_exceeded")
            ] == ["🌍"]


@pytest.mark.parametrize(
    ("model", "name", "expected"),
    [("gpt-4", "cl100k_base", 7), ("text-davinci-003", "p50k_base", 12)],
)
def test_exact_model_budget(model, name, expected):
    code = 'def f(): return "こんにちは"'
    enc = tiktoken.get_encoding(name)
    assert len(enc.encode(code)) == expected
    (parent,) = chunk_text(code, "python")
    for budget in {7, expected, expected - 1}:
        result = chunk_text_with_token_limit(code, "python", budget, model=model)
        if budget >= expected:
            (intact,) = result
            assert intact.content == code
            assert intact.metadata["token_count"] == expected
            assert "is_split" not in intact.metadata
        else:
            assert_partition(parent, result, code.encode(), budget, enc, model)


@pytest.mark.parametrize(
    ("mode", "newline"),
    [("text", "\r\n"), ("strategy", "\r\n"), ("strategy", "\n"), ("file", "\n")],
)
def test_token_entry_offsets(tmp_path, mode, newline):
    code = newline.join(["# é", "def café():", '\treturn "é🌍' + "ABCD" * 30 + '"'])
    path = tmp_path / "source.py"
    raw = code.encode()
    path.write_bytes(raw)
    (parent,) = chunk_text(code, "python", str(path))
    if mode == "strategy":
        result = TreeSitterTokenAwareChunker().chunk_with_token_limit(
            str(path), "python", 8
        )
    elif mode == "file":
        result = chunk_file_with_token_limit(path, "python", 8)
    else:
        result = chunk_text_with_token_limit(code, "python", 8, str(path))
    assert_partition(
        parent, result, raw, 8, tiktoken.get_encoding("cl100k_base"), "gpt-4"
    )


@pytest.mark.parametrize("budget", [0, -1])
def test_invalid_budget_on_empty_input(tmp_path, budget):
    path = tmp_path / "empty.py"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="positive"):
        TiktokenCounter().split_text_by_tokens("", budget)
    with pytest.raises(ValueError, match="positive"):
        chunk_text_with_token_limit("", "python", budget)
    with pytest.raises(ValueError, match="positive"):
        chunk_file_with_token_limit(path, "python", budget)
    with pytest.raises(ValueError, match="positive"):
        TreeSitterTokenAwareChunker().chunk_with_token_limit(
            str(path), "python", budget
        )


@pytest.mark.parametrize(
    ("parts", "message"),
    [
        (["+"], "incomplete"),
        (["", "+", "🌍"], "empty"),
        (["🌍", "+"], "order"),
        (["+🌍"], "divisible"),
        (["+", "🌍"], None),
    ],
)
def test_custom_counter_partition(monkeypatch, parts, message):
    counter = TiktokenCounter()
    monkeypatch.setattr(counter, "split_text_by_tokens", lambda *args: parts)
    original = CodeChunk("python", "x.py", "function_definition", 1, 1, 0, 5, "", "+🌍")
    strategy = TreeSitterTokenAwareChunker(counter)
    if message:
        with pytest.raises(ValueError, match=message):
            strategy._split_large_chunk(original, 1, "gpt-4")
    else:
        result = strategy._split_large_chunk(original, 1, "gpt-4")
        assert_partition(
            original,
            result,
            original.content.encode(),
            1,
            tiktoken.get_encoding("cl100k_base"),
            "gpt-4",
        )


def test_counter_lossless_boundaries():
    counter = TiktokenCounter()
    enc = tiktoken.get_encoding("cl100k_base")
    assert counter.split_text_by_tokens("", 1) == []
    assert counter.split_text_by_tokens("こんにちは", 1) == ["こんにちは"]
    assert counter.split_text_by_tokens("🌍", 1) == ["🌍"]
    assert (
        len(enc.encode("a\n")) + len(enc.encode("\n")) > len(enc.encode("a\n\n")) == 2
    )
    assert counter.split_text_by_tokens("a\n\nnot another newline", 2)[0] == "a\n\n"
    for text in [" \t\n\n" * 32, " \t\n\n" * 32 + "\t", "A_b" * 100]:
        parts = counter.split_text_by_tokens(text, 3)
        assert "".join(parts) == text
        assert all(0 < len(enc.encode(part)) <= 3 for part in parts)

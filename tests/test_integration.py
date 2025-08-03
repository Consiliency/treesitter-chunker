"""Integration tests for the parser module across all languages."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from chunker.factory import ParserFactory
from chunker.registry import LanguageRegistry

from chunker import (
    ParserConfig,
    clear_cache,
    get_language_info,
    get_parser,
    list_languages,
    return_parser,
)
from chunker._internal.factory import ParserFactory
from chunker._internal.registry import LanguageRegistry
from chunker.exceptions import ParserConfigError
from chunker.parser import _factory


class TestAllLanguages:
    """Test parsing functionality for all supported languages."""

    @staticmethod
    @pytest.fixture(autouse=True)
    def setup_teardown():
        """Setup and teardown for each test."""
        clear_cache()
        yield
        clear_cache()

    def test_all_languages_parse(self):
        """Test that all languages can parse basic code."""
        test_samples = {"python":
            """
def factorial(n: int) -> int:
    ""\"Calculate factorial of n.""\"
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
"""
            , "javascript":
            """
function factorial(n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

class Calculator {
    add(a, b) {
        return a + b;
    }
}

const arrow = (x) => x * 2;
"""
            , "c":
            """
#include <stdio.h>

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

struct Point {
    int x;
    int y;
};

typedef struct Point Point;
"""
            , "cpp":
            """
#include <iostream>
#include <string>

class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }

    template<typename T>
    T multiply(T a, T b) {
        return a * b;
    }
};

namespace math {
    int factorial(int n) {
        return (n <= 1) ? 1 : n * factorial(n - 1);
    }
}
"""
            , "rust":
            """
fn factorial(n: u32) -> u32 {
    match n {
        0 | 1 => 1,
        _ => n * factorial(n - 1),
    }
}

struct Calculator {
    value: i32,
}

impl Calculator {
    fn new(value: i32) -> Self {
        Calculator { value }
    }

    fn add(&self, other: i32) -> i32 {
        self.value + other
    }
}

trait Compute {
    fn compute(&self) -> i32;
}
""",
            }
        results = {}
        for lang, code in test_samples.items():
            try:
                parser = get_parser(lang)
                tree = parser.parse(bytes(code, "utf8"))
                root = tree.root_node
                assert root is not None
                assert root.child_count > 0
                has_error = self._has_error_node(root)
                results[lang] = {"success": True, "node_count": self.
                    _count_nodes(root), "has_error": has_error, "root_type":
                    root.type}
            except (IndexError, KeyError, SyntaxError) as e:
                results[lang] = {"success": False, "error": str(e)}
        for lang, result in results.items():
            assert result["success"
                ], f"{lang} failed: {result.get('error', 'Unknown error')}"
            assert not result["has_error"], f"{lang} has parsing errors"
            assert result["node_count"] > 10, f"{lang} parsed too few nodes"

    def _has_error_node(self, node):
        """Check if tree contains any ERROR nodes."""
        if node.type == "ERROR" or node.is_error:
            return True
        return any(self._has_error_node(child) for child in node.children)

    def _count_nodes(self, node):
        """Count total nodes in tree."""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count

    @staticmethod
    def test_language_metadata_consistency():
        """Test that language metadata is consistent across all languages."""
        languages = list_languages()
        assert len(languages) >= 5
        for lang in languages:
            info = get_language_info(lang)
            assert info.name == lang
            assert info.symbol_name == f"tree_sitter_{lang}"
            assert isinstance(info.version, str)
            assert isinstance(info.has_scanner, bool)
            assert isinstance(info.capabilities, dict)
            assert "compatible" in info.capabilities
            assert "language_version" in info.capabilities
            assert info.capabilities["compatible"] is True
            parser = get_parser(lang)
            assert parser is not None


class TestConcurrentParsing:
    """Test concurrent parsing across multiple languages."""

    @classmethod
    def test_concurrent_multi_language_parsing(cls):
        """Test parsing multiple languages concurrently."""
        samples = {"python": "def test(): return 42", "javascript":
            "function test() { return 42; }", "c":
            "int test() { return 42; }", "cpp": "int test() { return 42; }",
            "rust": "fn test() -> i32 { 42 }"}

        def parse_code(lang, code):
            """Parse code and return results."""
            try:
                parser = get_parser(lang)
                tree = parser.parse(bytes(code, "utf8"))
                return_parser(lang, parser)
                return lang, True, tree.root_node.type
            except (OSError, SyntaxError) as e:
                return lang, False, str(e)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(parse_code, lang, code): lang for
                lang, code in samples.items()}
            results = {}
            for future in as_completed(futures):
                lang, success, data = future.result()
                results[lang] = success, data
        for lang, (success, data) in results.items():
            assert success, f"{lang} failed: {data}"

    @staticmethod
    def test_stress_concurrent_parsing():
        """Stress test with many concurrent parser requests."""
        languages = ["python", "javascript", "rust"]
        iterations = 10
        threads_per_language = 3
        errors = []
        parse_counts = dict.fromkeys(languages, 0)
        lock = threading.Lock()

        def worker(lang, thread_id):
            """Worker thread that repeatedly gets parsers and parses code."""
            code = (
                f"// Thread {thread_id}\nfunction test{thread_id}() {{ return {thread_id}; }}"
                )
            try:
                for _i in range(iterations):
                    parser = get_parser(lang)
                    tree = parser.parse(bytes(code, "utf8"))
                    assert tree.root_node is not None
                    return_parser(lang, parser)
                    with lock:
                        parse_counts[lang] += 1
                    time.sleep(0.001)
            except (OSError, IndexError, KeyError) as e:
                errors.append((lang, thread_id, str(e)))
        threads = []
        for lang in languages:
            for i in range(threads_per_language):
                t = threading.Thread(target=worker, args=(lang, i))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0, f"Errors occurred: {errors}"
        for lang, count in parse_counts.items():
            expected = iterations * threads_per_language
            assert count == expected, f"{lang}: expected {expected} parses, got {count}"


class TestParserConfiguration:
    """Test parser configuration across languages."""

    @classmethod
    def test_timeout_configuration(cls):
        """Test timeout configuration for all languages."""
        languages = list_languages()
        config = ParserConfig(timeout_ms=100)
        for lang in languages:
            parser = get_parser(lang, config)
            tree = parser.parse(b"test")
            assert tree is not None

    @classmethod
    def test_invalid_configurations(cls):
        """Test that invalid configurations are rejected."""
        invalid_configs = [ParserConfig(timeout_ms=-1), ParserConfig(
            timeout_ms="not a number"), ParserConfig(included_ranges="not a list")]
        for config in invalid_configs:
            with pytest.raises(ParserConfigError):
                get_parser("python", config)


class TestMemoryEfficiency:
    """Test memory efficiency of parser caching and pooling."""

    @classmethod
    def test_parser_reuse(cls):
        """Test that parsers are properly reused from cache/pool."""
        if _factory is None:
            lib_path = Path(__file__,
                ).parent.parent / "build" / "my-languages.so"
            test_registry = LanguageRegistry(lib_path)
            test_factory = ParserFactory(test_registry)
            initial_stats = test_factory.get_stats()
            initial_count = initial_stats["total_parsers_created"]
            for _ in range(10):
                parser = test_factory.get_parser("python")
                test_factory.return_parser("python", parser)
            [test_factory.get_parser("python") for _ in range(3)]
            final_stats = test_factory.get_stats()
            final_count = final_stats["total_parsers_created"]
        else:
            initial_stats = _factory.get_stats()
            initial_count = initial_stats["total_parsers_created"]
            for _ in range(10):
                parser = get_parser("python")
                return_parser("python", parser)
            [get_parser("python") for _ in range(3)]
            final_stats = _factory.get_stats()
            final_count = final_stats["total_parsers_created"]
        parsers_created = final_count - initial_count
        assert parsers_created <= 5, f"Created too many parsers: {parsers_created}"

    @classmethod
    def test_cache_effectiveness(cls):
        """Test cache hit rate under typical usage."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        test_registry = LanguageRegistry(lib_path)
        test_factory = ParserFactory(test_registry, cache_size=10)
        languages = ["python", "javascript", "rust"]
        initial_stats = test_factory.get_stats()
        initial_count = initial_stats["total_parsers_created"]
        for _ in range(5):
            for lang in languages:
                parser = test_factory.get_parser(lang)
                tree = parser.parse(b"test")
                assert tree is not None
        final_stats = test_factory.get_stats()
        parsers_created = final_stats["total_parsers_created"] - initial_count
        assert parsers_created == len(languages,
            ), f"Cache not effective: created {parsers_created} parsers for {len(languages)} languages"


class TestErrorScenarios:
    """Test error handling in integration scenarios."""

    @staticmethod
    def test_large_file_parsing():
        """Test parsing large files."""
        code_parts = ['"""Large test file."""\n']
        code_parts.extend(
            f"""
def function_{i}(param_{i}: int) -> int:
    ""\"Function {i} docstring.""\"
    result = param_{i} * 2
    if result > 100:
        return result - 10
    return result + 10

class Class_{i}:
    ""\"Class {i} docstring.""\"

    def method_{i}(self, value: int) -> str:
        ""\"Method {i} docstring.""\"
        return f"Value: {{value}}\"
"""
             for i in range(1000))
        large_code = "\n".join(code_parts)
        parser = get_parser("python")
        start_time = time.time()
        tree = parser.parse(bytes(large_code, "utf8"))
        parse_time = time.time() - start_time
        assert tree is not None
        assert tree.root_node.child_count > 0
        assert parse_time < 1.0, f"Parsing took too long: {parse_time:.2f}s"

    @staticmethod
    def test_malformed_code_handling():
        """Test handling of malformed code."""
        malformed_samples = {"python":
            'def incomplete_function(\n    print("unclosed', "javascript":
            "function test() { return }", "c": "int main() { return }",
            "cpp": "class Test { public: int get( };", "rust":
            'fn test() -> { println!("incomplete'}
        for lang, code in malformed_samples.items():
            parser = get_parser(lang)
            tree = parser.parse(bytes(code, "utf8"))
            assert tree is not None
            assert tree.root_node is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

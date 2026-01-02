"""
Additional tests for Python extractor edge cases and error conditions.

These tests target specific lines and edge cases to improve test coverage.
"""

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from chunker.extractors.core.extraction_framework import CallSite, ExtractionResult
from chunker.extractors.python.python_extractor import (
    PythonCallVisitor,
    PythonExtractor,
    PythonPatterns,
)


class TestPythonExtractorEdgeCases(unittest.TestCase):
    """Additional test cases for edge cases and error conditions."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = PythonExtractor()

    def test_extract_calls_with_none_input(self):
        """Test extract_calls with None input."""
        result = self.extractor.extract_calls(None)
        self.assertFalse(result.is_successful())
        self.assertGreater(len(result.errors), 0)

    def test_extract_calls_with_non_string_input(self):
        """Test extract_calls with non-string input."""
        result = self.extractor.extract_calls(123)
        self.assertFalse(result.is_successful())
        self.assertGreater(len(result.errors), 0)

    def test_extract_calls_with_empty_string(self):
        """Test extract_calls with empty string."""
        result = self.extractor.extract_calls("")
        self.assertFalse(result.is_successful())
        self.assertGreater(len(result.errors), 0)

    def test_extract_calls_with_whitespace_only(self):
        """Test extract_calls with whitespace-only string."""
        result = self.extractor.extract_calls("   \n\t  ")
        self.assertFalse(result.is_successful())
        self.assertGreater(len(result.errors), 0)

    def test_extract_calls_syntax_error_handling(self):
        """Test syntax error handling."""
        invalid_code = "def func(\nprint 'invalid'"
        result = self.extractor.extract_calls(invalid_code)

        self.assertFalse(result.is_successful())
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("syntax" in error.lower() for error in result.errors))

    def test_extract_calls_unexpected_error(self):
        """Test handling of unexpected errors during extraction."""
        valid_code = "print('hello')"

        # Mock the visitor to raise an unexpected exception
        with patch(
            "chunker.extractors.python.python_extractor.PythonCallVisitor",
        ) as mock_visitor:
            mock_instance = MagicMock()
            mock_instance.visit.side_effect = RuntimeError("Unexpected error")
            mock_visitor.return_value = mock_instance

            result = self.extractor.extract_calls(valid_code)

            self.assertFalse(result.is_successful())
            self.assertGreater(len(result.errors), 0)

    def test_validate_source_with_non_string(self):
        """Test validate_source with non-string input."""
        self.assertFalse(self.extractor.validate_source(None))
        self.assertFalse(self.extractor.validate_source(123))
        self.assertFalse(self.extractor.validate_source([]))

    def test_validate_source_unexpected_error(self):
        """Test validate_source with unexpected errors."""
        # This should still return False gracefully
        with patch("ast.parse") as mock_parse:
            mock_parse.side_effect = RuntimeError("Unexpected error")

            result = self.extractor.validate_source("print('hello')")
            self.assertFalse(result)

    def test_performance_metrics_collection(self):
        """Test that performance metrics are properly collected."""
        code = "print('hello')"
        result = self.extractor.extract_calls(code)

        self.assertIsInstance(result.performance_metrics, dict)
        self.assertGreater(result.extraction_time, 0)

        # Check that extractor metrics are available
        extractor_metrics = self.extractor.get_performance_metrics()
        self.assertIsInstance(extractor_metrics, dict)


class TestPythonCallVisitorEdgeCases(unittest.TestCase):
    """Additional test cases for PythonCallVisitor edge cases."""

    def test_initialization_with_invalid_import_code(self):
        """Test visitor initialization with code that has import errors."""
        # Code with syntax errors in imports
        invalid_import_code = """
import os
from broken import
import json as
"""

        # Should not raise exception during initialization
        visitor = PythonCallVisitor(invalid_import_code)
        self.assertIsInstance(visitor.current_context["imports"], set)

    def test_visit_call_with_complex_nested_expressions(self):
        """Test call visiting with deeply nested expressions."""
        complex_code = """
result = func1(
    func2(
        func3(
            func4(
                func5()
            )
        )
    )
)
"""

        visitor = PythonCallVisitor(complex_code)
        tree = ast.parse(complex_code)
        visitor.visit(tree)

        # Should find all nested calls
        self.assertGreaterEqual(len(visitor.call_sites), 5)

    def test_visit_call_error_handling(self):
        """Test error handling during call node processing."""
        code = "func()"
        visitor = PythonCallVisitor(code)

        # Create a mock call node that will cause errors
        mock_call = MagicMock()
        mock_call.func = None
        mock_call.lineno = None
        mock_call.col_offset = None

        # Should not raise exception
        try:
            visitor.visit_Call(mock_call)
            success = True
        except Exception:
            success = False

        self.assertTrue(success)

    def test_extract_function_info_error_handling(self):
        """Test error handling in function info extraction."""
        visitor = PythonCallVisitor("")

        # Create malformed node
        mock_node = MagicMock()
        mock_node.func = None

        name, call_type = visitor._extract_function_info(mock_node)
        self.assertIn(name, ["<complex>", "<unknown>"])  # Either is acceptable
        self.assertEqual(call_type, "complex")

    def test_get_attribute_chain_error_handling(self):
        """Test error handling in attribute chain extraction."""
        visitor = PythonCallVisitor("")

        # Create malformed attribute node
        mock_attr = MagicMock()
        mock_attr.value = None
        mock_attr.attr = "method"

        result = visitor._get_attribute_chain(mock_attr)
        self.assertIsInstance(result, str)

    def test_extract_complex_call_name_various_types(self):
        """Test complex call name extraction with various node types."""
        visitor = PythonCallVisitor("")

        # Test with different node types
        test_cases = [
            (ast.parse("variable").body[0].value, "variable"),
            (None, "<complex>"),
        ]

        for node, expected_prefix in test_cases:
            if node is not None:
                result = visitor._extract_complex_call_name(node)
                if expected_prefix:
                    self.assertIn(expected_prefix, result)

    def test_calculate_byte_offsets_error_conditions(self):
        """Test byte offset calculation with error conditions."""
        visitor = PythonCallVisitor("test code")

        # Test with mock node that lacks position info
        mock_node = MagicMock()
        mock_node.lineno = None
        mock_node.col_offset = None

        start, end = visitor._calculate_byte_offsets(mock_node)
        self.assertEqual(start, 0)
        self.assertEqual(end, 0)

    def test_line_col_to_byte_edge_cases(self):
        """Test line/column to byte conversion edge cases."""
        code = "line1\nline2\nline3"
        visitor = PythonCallVisitor(code)

        # Test out of bounds line
        result = visitor._line_col_to_byte(999, 0)
        self.assertGreaterEqual(result, 0)

        # Test negative line/column
        result = visitor._line_col_to_byte(-1, -1)
        self.assertGreaterEqual(result, 0)

    def test_extract_call_context_error_handling(self):
        """Test error handling in call context extraction."""
        visitor = PythonCallVisitor("")

        # Create mock node that will cause errors
        mock_node = MagicMock()
        mock_node.args = None
        mock_node.keywords = None

        context = visitor._extract_call_context(mock_node)
        self.assertIn("context_error", context)

    def test_get_node_type_info_error_handling(self):
        """Test error handling in node type info extraction."""
        visitor = PythonCallVisitor("")

        # Test with None
        result = visitor._get_node_type_info(None)
        self.assertEqual(result, "Unknown")

        # Test with mock node that raises exception
        mock_node = MagicMock()
        mock_node.value = MagicMock()
        mock_node.value.__name__ = MagicMock(side_effect=AttributeError())

        result = visitor._get_node_type_info(mock_node)
        self.assertIsInstance(result, str)

    def test_decorator_and_base_extraction_errors(self):
        """Test error handling in decorator and base class extraction."""
        visitor = PythonCallVisitor("")

        # Test decorator extraction with None
        result = visitor._get_decorator_name(None)
        self.assertEqual(result, "<unknown>")

        # Test base extraction with None
        result = visitor._get_base_name(None)
        self.assertEqual(result, "<unknown>")

    def test_scope_tracking_with_deeply_nested_code(self):
        """Test scope tracking with very deeply nested code."""
        nested_code = """
class A:
    class B:
        class C:
            def method1(self):
                def inner1():
                    def inner2():
                        class InnerClass:
                            def inner_method(self):
                                print("very deep")
                                return len("test")
"""

        visitor = PythonCallVisitor(nested_code)
        tree = ast.parse(nested_code)
        visitor.visit(tree)

        # Should handle deep nesting without errors
        self.assertGreater(len(visitor.call_sites), 0)

        # Check that scope depths are tracked
        max_depth = max(cs.context.get("scope_depth", 0) for cs in visitor.call_sites)
        self.assertGreater(max_depth, 3)


class TestPythonPatternsEdgeCases(unittest.TestCase):
    """Additional test cases for PythonPatterns edge cases."""

    def test_extract_call_context_with_malformed_arguments(self):
        """Test context extraction with malformed arguments."""
        # Create a call with problematic arguments
        code = "func(arg1, arg2=value)"
        call_node = ast.parse(code).body[0].value

        # Mock one of the arguments to cause an error
        call_node.args[0] = MagicMock()
        call_node.args[0].__class__ = MagicMock()
        call_node.args[0].__class__.__name__ = "BadType"

        context = PythonPatterns.extract_call_context(call_node, {})

        # Should handle the error gracefully
        self.assertIsInstance(context, dict)

    def test_get_call_complexity_score_error_conditions(self):
        """Test complexity scoring with error conditions."""
        # Test with None
        score = PythonPatterns.get_call_complexity_score(None)
        self.assertEqual(score, 10)  # Should default to high complexity

        # Test with malformed node
        mock_node = MagicMock()
        mock_node.args = None
        mock_node.keywords = None

        score = PythonPatterns.get_call_complexity_score(mock_node)
        self.assertEqual(score, 10)  # Should default to high complexity on error

    def test_builtin_function_edge_cases(self):
        """Test builtin function detection edge cases."""
        self.assertFalse(PythonPatterns.is_builtin_function(""))
        self.assertFalse(PythonPatterns.is_builtin_function(None))
        self.assertFalse(PythonPatterns.is_builtin_function("not_a_builtin"))

    def test_dunder_method_edge_cases(self):
        """Test dunder method detection edge cases."""
        edge_cases = [
            ("", False),
            ("__", False),
            ("____", False),  # Only underscores
            ("__a", False),  # Incomplete
            ("a__", False),  # Incomplete
            ("__a__", True),  # Valid short dunder
            ("__very_long_dunder_method_name__", True),  # Valid long dunder
        ]

        for method_name, expected in edge_cases:
            with self.subTest(method_name=method_name):
                result = PythonPatterns.is_dunder_method(method_name)
                self.assertEqual(result, expected)

    def test_call_pattern_detection_with_unusual_nodes(self):
        """Test call pattern detection with unusual AST nodes."""
        # Test with subscript call
        subscript_code = "obj[key]()"
        call_node = ast.parse(subscript_code).body[0].value

        self.assertFalse(PythonPatterns.is_function_call(call_node))
        self.assertFalse(PythonPatterns.is_method_call(call_node))

        # Test with generator expression call
        generator_code = "(x for x in range(10))"
        gen_node = ast.parse(generator_code).body[0].value

        # These are not Call nodes, so should return False
        self.assertFalse(PythonPatterns.is_function_call(gen_node))
        self.assertFalse(PythonPatterns.is_method_call(gen_node))


class TestPythonExtractorIntegrationEdgeCases(unittest.TestCase):
    """Integration tests for edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = PythonExtractor()

    def test_extract_from_file_with_encoding_issues(self):
        """Test extraction from code with unusual characters."""
        unicode_code = """
def greet():
    print("Hello 🌍!")  # Unicode emoji
    print("Café")       # Accented characters
    return "Naïve résumé"  # More accents

greet()
len("🐍 Python")
"""

        result = self.extractor.extract_calls(unicode_code)
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 0)

    def test_extract_from_very_long_code(self):
        """Test extraction from very long code."""
        # Generate a long piece of code
        long_code = "# Very long file\n"
        for i in range(100):
            long_code += f"func_{i}(arg_{i})\n"

        result = self.extractor.extract_calls(long_code)
        self.assertTrue(result.is_successful())
        self.assertGreaterEqual(len(result.call_sites), 100)

    def test_extract_with_all_python_features(self):
        """Test extraction from code using many Python features."""
        comprehensive_code = """
# Comprehensive Python feature test
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager

@dataclass
class Example:
    value: int = 0
    items: List[str] = field(default_factory=list)

async def async_function():
    await asyncio.sleep(1)
    return "done"

@contextmanager
def resource_manager():
    print("acquiring")
    try:
        yield "resource"
    finally:
        print("releasing")

def comprehension_example():
    # List comprehension
    squares = [x**2 for x in range(10) if x % 2 == 0]

    # Dict comprehension
    square_dict = {x: x**2 for x in range(5)}

    # Set comprehension
    unique_squares = {x**2 for x in range(10)}

    # Generator expression
    square_gen = (x**2 for x in range(10))

    return list(square_gen)

def decorator_example():
    @property
    def computed(self):
        return sum(range(10))

    return computed

def lambda_example():
    # Lambda functions
    square = lambda x: x**2
    add = lambda a, b: a + b

    # Higher-order functions
    numbers = list(map(square, range(10)))
    filtered = list(filter(lambda x: x > 5, numbers))

    return max(filtered)

def exception_example():
    try:
        result = int("not_a_number")
    except ValueError as e:
        print(f"Error: {e}")
        raise RuntimeError("Failed") from e
    finally:
        print("cleanup")

def context_manager_example():
    with resource_manager() as resource:
        print(f"Using {resource}")

    with open("file.txt", "w") as f:
        f.write("content")

# Class with various features
class AdvancedClass:
    class_var = "shared"

    def __init__(self, name):
        self.name = name
        self._private = "secret"

    @classmethod
    def create(cls, name):
        return cls(name)

    @staticmethod
    def utility():
        return "useful"

    @property
    def display_name(self):
        return f"Display: {self.name}"

    def __str__(self):
        return f"AdvancedClass({self.name})"

    def __call__(self, *args, **kwargs):
        return f"Called with {args}, {kwargs}"

# Usage examples
obj = AdvancedClass.create("test")
print(obj.display_name)
result = obj("arg1", "arg2", key="value")
utility_result = AdvancedClass.utility()

# Async usage
async def main():
    result = await async_function()
    print(result)

# Run everything
if __name__ == "__main__":
    comprehension_example()
    lambda_example()
    context_manager_example()
    asyncio.run(main())
"""

        result = self.extractor.extract_calls(comprehensive_code)
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 20)

        # Check for various call types
        call_names = [cs.function_name for cs in result.call_sites]

        # Should find built-in functions
        self.assertTrue(any("print" in name for name in call_names))
        self.assertTrue(any("range" in name for name in call_names))
        # len might not be found if it's in a comprehension that's not extracted

        # Should find method calls
        self.assertTrue(any("create" in name for name in call_names))
        self.assertTrue(any("write" in name for name in call_names))


if __name__ == "__main__":
    unittest.main()

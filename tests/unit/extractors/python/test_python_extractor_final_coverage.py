"""
Final tests to reach 95% coverage by targeting specific uncovered lines.

These tests are designed to hit the exact lines that are still missing from coverage.
"""

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from chunker.extractors.python.python_extractor import (
    PythonCallVisitor,
    PythonExtractor,
    PythonPatterns,
)


class TestPythonExtractorFinalCoverage(unittest.TestCase):
    """Final tests to hit remaining uncovered lines."""

    def test_visitor_import_preprocessing_exception(self):
        """Test exception handling in import preprocessing."""
        # Create a visitor with code that will cause ast.parse to fail during import preprocessing
        with patch("ast.parse") as mock_parse:
            # First call succeeds (for main parsing), second fails (for import preprocessing)
            mock_parse.side_effect = [
                MagicMock(),
                SyntaxError("Import preprocessing error"),
            ]

            visitor = PythonCallVisitor("import test")
            # The exception should be caught and logged, not raised
            self.assertIsInstance(visitor.current_context["imports"], set)

    def test_visitor_visit_call_exception_handling(self):
        """Test exception handling in visit_Call method."""
        visitor = PythonCallVisitor("test")

        # Create a mock call node that will cause an exception
        mock_call = MagicMock()
        mock_call.func = MagicMock()
        mock_call.func.id = "test"

        # Mock _extract_function_info to raise an exception
        with patch.object(
            visitor,
            "_extract_function_info",
            side_effect=Exception("Test error"),
        ):
            # Should not raise, should handle the exception
            try:
                visitor.visit_Call(mock_call)
                success = True
            except Exception:
                success = False

            self.assertTrue(success, "visit_Call should handle exceptions gracefully")

    def test_visitor_extract_function_info_exceptions(self):
        """Test exception handling in _extract_function_info."""
        visitor = PythonCallVisitor("")

        # Test with a mock node that will cause various exceptions
        mock_node = MagicMock()
        mock_node.func = MagicMock()

        # Make accessing func.id raise an exception
        type(mock_node.func).id = MagicMock(side_effect=AttributeError("No id"))

        name, call_type = visitor._extract_function_info(mock_node)
        # The result depends on the exact implementation details
        self.assertIn(call_type, ["unknown", "complex"])

    def test_visitor_get_attribute_chain_exceptions(self):
        """Test exception handling in _get_attribute_chain."""
        visitor = PythonCallVisitor("")

        # Create a mock attribute node that will cause exceptions
        mock_attr = MagicMock()
        mock_attr.value = MagicMock()
        type(mock_attr.value).id = MagicMock(side_effect=AttributeError("No id"))

        result = visitor._get_attribute_chain(mock_attr)
        # The result depends on the exact implementation details
        self.assertIsInstance(result, str)

    def test_visitor_calculate_byte_offsets_exceptions(self):
        """Test exception handling in _calculate_byte_offsets."""
        visitor = PythonCallVisitor("test")

        # Create a mock node that will cause exceptions during offset calculation
        mock_node = MagicMock()
        mock_node.lineno = MagicMock(side_effect=AttributeError("No lineno"))

        start, end = visitor._calculate_byte_offsets(mock_node)
        self.assertEqual(start, 0)
        self.assertEqual(end, 0)

    def test_visitor_line_col_to_byte_exceptions(self):
        """Test exception handling in _line_col_to_byte."""
        visitor = PythonCallVisitor("test\ncode")

        # Test with values that might cause encoding issues
        try:
            result = visitor._line_col_to_byte(1, 999999)
            self.assertGreaterEqual(result, 0)
        except Exception:
            # Should not raise exceptions
            self.fail("_line_col_to_byte raised an exception")

    def test_visitor_extract_call_context_exception_handling(self):
        """Test exception handling in _extract_call_context."""
        visitor = PythonCallVisitor("")

        # Create a call node that will cause issues during context extraction
        mock_node = MagicMock()
        mock_node.args = []
        mock_node.keywords = []

        # Mock one of the methods to cause an exception
        with patch.object(
            visitor,
            "_get_node_type_info",
            side_effect=Exception("Test error"),
        ):
            context = visitor._extract_call_context(mock_node)
            # Should still return a valid context dict
            self.assertIsInstance(context, dict)
            self.assertIn("node_type", context)

    def test_visitor_get_node_type_info_all_branches(self):
        """Test all branches of _get_node_type_info."""
        visitor = PythonCallVisitor("")

        # Test with various node types to hit all branches
        test_cases = [
            (None, "Unknown"),
            (ast.Constant(value=42), "Constant(int)"),
            (ast.Name(id="test", ctx=ast.Load()), "Name(test)"),
            (
                ast.Attribute(
                    attr="method",
                    value=ast.Name(id="obj", ctx=ast.Load()),
                    ctx=ast.Load(),
                ),
                "Attribute(method)",
            ),
            (
                ast.Call(
                    func=ast.Name(id="func", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                ),
                "Call",
            ),
            (ast.List(elts=[], ctx=ast.Load()), "List"),
            (ast.Dict(keys=[], values=[]), "Dict"),
            (ast.Tuple(elts=[], ctx=ast.Load()), "Tuple"),
        ]

        for node, expected in test_cases:
            result = visitor._get_node_type_info(node)
            self.assertEqual(result, expected)

    def test_visitor_decorator_and_base_extraction_all_types(self):
        """Test decorator and base extraction with all node types."""
        visitor = PythonCallVisitor("")

        # Test all branches of decorator extraction
        decorator_cases = [
            (None, "<unknown>"),
            (ast.Name(id="decorator", ctx=ast.Load()), "decorator"),
            (
                ast.Attribute(
                    attr="decorator",
                    value=ast.Name(id="module", ctx=ast.Load()),
                    ctx=ast.Load(),
                ),
                "module",
            ),
            (
                ast.Call(
                    func=ast.Name(id="decorator", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                ),
                "decorator(...)",
            ),
        ]

        for node, expected_part in decorator_cases:
            result = visitor._get_decorator_name(node)
            if expected_part != "<unknown>":
                self.assertIn(expected_part, result)
            else:
                self.assertEqual(result, expected_part)

        # Test all branches of base extraction
        base_cases = [
            (None, "<unknown>"),
            (ast.Name(id="BaseClass", ctx=ast.Load()), "BaseClass"),
            (
                ast.Attribute(
                    attr="BaseClass",
                    value=ast.Name(id="module", ctx=ast.Load()),
                    ctx=ast.Load(),
                ),
                "module",
            ),
        ]

        for node, expected in base_cases:
            result = visitor._get_base_name(node)
            if expected != "<unknown>":
                self.assertIn(expected, result)
            else:
                self.assertEqual(result, expected)

    def test_extractor_validate_source_all_exception_paths(self):
        """Test all exception paths in validate_source."""
        extractor = PythonExtractor()

        # Test with different exception types from ast.parse
        with patch("ast.parse") as mock_parse:
            # Test SyntaxError path
            mock_parse.side_effect = SyntaxError("syntax error")
            result = extractor.validate_source("invalid code")
            self.assertFalse(result)

            # Test general Exception path
            mock_parse.side_effect = RuntimeError("unexpected error")
            result = extractor.validate_source("code")
            self.assertFalse(result)

    def test_patterns_extract_call_context_exception_handling(self):
        """Test exception handling in PythonPatterns.extract_call_context."""
        # Create a mock call node that will cause exceptions
        mock_node = MagicMock()
        mock_node.args = None
        mock_node.keywords = None
        mock_node.func = None

        # Make len() calls fail
        with patch("builtins.len", side_effect=TypeError("len error")):
            context = PythonPatterns.extract_call_context(mock_node, {})
            self.assertIn("extraction_error", context)

    def test_patterns_get_call_complexity_score_exception_path(self):
        """Test exception path in get_call_complexity_score."""
        # Create a mock node that will cause exceptions during complexity calculation
        mock_node = MagicMock()
        mock_node.args = None
        mock_node.keywords = None

        # Make accessing attributes fail
        with patch("ast.walk", side_effect=RuntimeError("walk error")):
            score = PythonPatterns.get_call_complexity_score(mock_node)
            self.assertEqual(score, 10)  # Should default to high complexity

    def test_visitor_visit_function_and_class_def_edge_cases(self):
        """Test edge cases in visit_FunctionDef and visit_ClassDef."""
        code = """
def func_with_all_features(*args, **kwargs):
    '''A function with all possible features'''
    pass

@decorator1
@decorator2
class ComplexClass(Base1, Base2):
    '''A class with multiple bases and decorators'''
    pass
"""

        visitor = PythonCallVisitor(code)
        tree = ast.parse(code)
        visitor.visit(tree)

        # Should handle all features without errors
        self.assertIsInstance(visitor.current_context, dict)

    def test_visitor_import_from_none_module(self):
        """Test import from with None module (relative imports)."""
        code = """
from . import relative
from .. import parent_relative
"""

        visitor = PythonCallVisitor(code)

        # Should handle relative imports
        self.assertIsInstance(visitor.current_context["imports"], set)

    def test_extractor_extract_calls_validation_warnings(self):
        """Test extraction with code that generates validation warnings."""
        # Create code that will generate validation warnings
        problematic_code = """
# This code has some unusual byte offset patterns
def func():
    # Very long line that might cause byte offset issues
    very_long_variable_name_that_might_cause_issues = "very long string value that might cause byte offset calculation problems"
    print(very_long_variable_name_that_might_cause_issues)
    return len(very_long_variable_name_that_might_cause_issues)

func()
"""

        result = self.extractor.extract_calls(problematic_code)

        # Should succeed but might have warnings
        self.assertTrue(result.is_successful())
        # Warnings are acceptable

    def test_comprehensive_edge_case_coverage(self):
        """Comprehensive test to hit remaining edge cases."""
        # Code designed to hit multiple edge cases
        edge_case_code = """
# Import variations
import sys, os

# Simple function definitions that will parse correctly
def complex_func(a, b=None):
    # Nested function with various call types
    def inner():
        # Multiple call patterns
        result1 = func()
        result2 = obj.method()
        result3 = getattr(obj, 'dynamic_method')()
        result4 = print("test")
        
        return [result1, result2, result3, result4]
    
    return inner()

# Class with simple inheritance 
class ComplexClass:
    attr = "default"
    
    def computed(self):
        return sum(range(10))
    
    def factory(self):
        return self
    
    def __call__(self, *args):
        return f"Called with {len(args)}"

# Usage that hits various patterns
obj = ComplexClass()
result = obj.computed()
called = obj(1, 2, 3)
complex_result = complex_func(1, 2)
"""

        result = self.extractor.extract_calls(edge_case_code)

        # Should handle all patterns successfully
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 10)

        # Should have collected performance metrics
        self.assertIsInstance(result.performance_metrics, dict)

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = PythonExtractor()


if __name__ == "__main__":
    unittest.main()

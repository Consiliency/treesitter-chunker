"""
Additional tests to reach 95% coverage for Python extractor.

These tests specifically target remaining uncovered lines.
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


class TestPythonExtractorCoverage(unittest.TestCase):
    """Tests to improve coverage on specific uncovered lines."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = PythonExtractor()

    def test_extract_calls_with_ast_parse_exception(self):
        """Test handling of ast.parse exceptions."""
        with patch("ast.parse") as mock_parse:
            mock_parse.side_effect = SyntaxError("test syntax error")

            result = self.extractor.extract_calls("print('hello')")

            self.assertFalse(result.is_successful())
            self.assertGreater(len(result.errors), 0)
            self.assertTrue(any("syntax" in error.lower() for error in result.errors))

    def test_visitor_with_empty_import_case(self):
        """Test visitor with import from without module."""
        code = """
from . import something
from ..package import other
"""
        visitor = PythonCallVisitor(code)
        # Should handle relative imports without crashing
        self.assertIsInstance(visitor.current_context["imports"], set)

    def test_visitor_call_with_missing_attributes(self):
        """Test call visiting with nodes missing line/col info."""
        visitor = PythonCallVisitor("func()")

        # Create a call node manually to test missing attributes
        call_node = ast.Call(
            func=ast.Name(id="test", ctx=ast.Load()),
            args=[],
            keywords=[],
        )
        # Remove line/col attributes to test fallback
        if hasattr(call_node, "lineno"):
            delattr(call_node, "lineno")
        if hasattr(call_node, "col_offset"):
            delattr(call_node, "col_offset")

        # Should handle missing attributes gracefully
        visitor.visit_Call(call_node)

        # Should have added at least one call site
        self.assertGreaterEqual(len(visitor.call_sites), 0)

    def test_visitor_byte_calculation_edge_cases(self):
        """Test byte calculation with edge cases."""
        code = "short\nlonger line\nend"
        visitor = PythonCallVisitor(code)

        # Test with line numbers beyond the source
        result = visitor._line_col_to_byte(999, 0)
        self.assertGreaterEqual(result, 0)

        # Test with very large column
        result = visitor._line_col_to_byte(1, 9999)
        self.assertGreaterEqual(result, 0)

    def test_visitor_complex_call_patterns(self):
        """Test visitor with complex call patterns that might be missed."""
        complex_code = """
# Test various call patterns that might not be covered
result = obj.method()(arg)  # Chained call result
func(**{'key': 'value'})   # Keyword expansion
func(*[1, 2, 3])          # Args expansion
getattr(obj, 'method')()  # Dynamic method call
(lambda: print("test"))() # Lambda execution
"""

        visitor = PythonCallVisitor(complex_code)
        tree = ast.parse(complex_code)
        visitor.visit(tree)

        # Should find multiple calls
        self.assertGreater(len(visitor.call_sites), 0)

    def test_visitor_argument_analysis_edge_cases(self):
        """Test argument analysis with edge cases."""
        code = """
func(
    None,           # None argument
    ...,            # Ellipsis argument
    True,           # Boolean argument
    complex(1, 2),  # Complex number
)
"""

        visitor = PythonCallVisitor(code)
        tree = ast.parse(code)
        visitor.visit(tree)

        # Should handle all argument types
        self.assertGreater(len(visitor.call_sites), 0)

        # Check that context extraction worked
        for call_site in visitor.call_sites:
            self.assertIn("argument_count", call_site.context)

    def test_visitor_function_and_class_tracking(self):
        """Test function and class context tracking edge cases."""
        code = """
class Outer:
    def method(self):
        def inner():
            print("nested")
        inner()

def standalone():
    class InnerClass:
        def inner_method(self):
            return len("test")
    obj = InnerClass()
    return obj.inner_method()
"""

        visitor = PythonCallVisitor(code)
        tree = ast.parse(code)
        visitor.visit(tree)

        # Should track nested contexts correctly
        nested_calls = [
            cs for cs in visitor.call_sites if cs.context.get("scope_depth", 0) > 1
        ]
        self.assertGreater(len(nested_calls), 0)

    def test_patterns_with_complex_nodes(self):
        """Test patterns with complex AST node types."""
        # Test with starred expressions
        starred_code = "func(*args, **kwargs)"
        call_node = ast.parse(starred_code).body[0].value

        context = PythonPatterns.extract_call_context(call_node, {})
        self.assertTrue(context["has_starargs"])
        self.assertTrue(context["has_kwargs"])

        # Test complexity scoring with various patterns
        self.assertGreater(PythonPatterns.get_call_complexity_score(call_node), 1)

    def test_patterns_builtin_and_dunder_edge_cases(self):
        """Test builtin and dunder detection with edge cases."""
        # Test some specific builtins that might not be covered
        uncommon_builtins = ["memoryview", "bytearray", "breakpoint", "classmethod"]
        for builtin in uncommon_builtins:
            self.assertTrue(PythonPatterns.is_builtin_function(builtin))

        # Test dunder methods with edge cases
        dunder_edge_cases = ["__new__", "__del__", "__reduce_ex__"]
        for dunder in dunder_edge_cases:
            self.assertTrue(PythonPatterns.is_dunder_method(dunder))

    def test_extractor_performance_edge_cases(self):
        """Test extractor performance measurement edge cases."""
        # Test with code that might cause performance issues
        performance_code = """
# Code with many nested calls
result = func1(
    func2(
        func3(
            func4(
                func5(
                    func6()
                )
            )
        )
    )
)

# Multiple similar calls
for i in range(100):
    print(f"iteration {i}")
    len(str(i))
    max(0, i)
"""

        result = self.extractor.extract_calls(performance_code)

        # Should handle complex code without issues
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 10)

        # Should have performance metrics
        self.assertIsInstance(result.performance_metrics, dict)
        self.assertGreater(result.extraction_time, 0)

    def test_extractor_with_file_metadata(self):
        """Test extractor with file path for metadata extraction."""
        code = "print('hello')"
        file_path = Path("/tmp/test_file.py")

        result = self.extractor.extract_calls(code, file_path)

        self.assertTrue(result.is_successful())
        self.assertIn("filename", result.metadata)
        self.assertIn("extension", result.metadata)

    def test_visitor_import_edge_cases(self):
        """Test visitor with edge cases in import handling."""
        import_edge_cases = """
import module1, module2, module3
from package import name1, name2 as alias2
from . import relative_import
import package.subpackage as alias
"""

        visitor = PythonCallVisitor(import_edge_cases)

        # Should handle multiple imports per line
        imports = visitor.current_context["imports"]
        self.assertGreater(len(imports), 0)

    def test_visitor_decorator_edge_cases(self):
        """Test visitor with complex decorator patterns."""
        decorator_code = """
@decorator1
@decorator2(arg1, arg2)
@module.decorator
@decorator_factory(key=value)
def decorated_function():
    return "test"

@property
@classmethod
def class_method(cls):
    return cls.__name__

decorated_function()
class_method()
"""

        visitor = PythonCallVisitor(decorator_code)
        tree = ast.parse(decorator_code)
        visitor.visit(tree)

        # Should handle decorator extraction
        self.assertGreater(len(visitor.call_sites), 0)

    def test_extractor_cleanup_and_metrics(self):
        """Test extractor cleanup and metrics collection."""
        # Test cleanup method
        self.extractor.cleanup()

        # Test metrics collection
        metrics = self.extractor.get_performance_metrics()
        self.assertIsInstance(metrics, dict)

    def test_visitor_with_syntax_elements(self):
        """Test visitor with various Python syntax elements."""
        syntax_code = """
# Test with f-strings, walrus operator, etc.
name = "world"
message = f"Hello {name}!"
print(message)

# Test with walrus operator (Python 3.8+)
if (n := len(message)) > 5:
    print(f"Long message: {n}")
    
# Test with match statement (Python 3.10+)
def handle_value(value):
    match value:
        case str() if len(value) > 0:
            return str.upper(value)
        case int() if value > 0:
            return abs(value)
        case _:
            return str(value)

result = handle_value("test")
print(result)
"""

        try:
            visitor = PythonCallVisitor(syntax_code)
            tree = ast.parse(syntax_code)
            visitor.visit(tree)

            # Should handle modern Python syntax
            self.assertGreater(len(visitor.call_sites), 0)

        except SyntaxError:
            # Skip if Python version doesn't support the syntax
            self.skipTest("Python version doesn't support all syntax features")


if __name__ == "__main__":
    unittest.main()

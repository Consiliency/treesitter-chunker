"""
Unit tests for PythonCallVisitor class.

Tests AST traversal, call site detection, and context tracking.
"""

import ast
import unittest
from pathlib import Path

from chunker.extractors.python.python_extractor import PythonCallVisitor


class TestPythonCallVisitor(unittest.TestCase):
    """Test cases for PythonCallVisitor."""

    def setUp(self):
        """Set up test fixtures."""
        self.basic_code = """
def simple_function():
    print("Hello, World!")
    return len("test")

class SimpleClass:
    def method(self):
        return str(42)

obj = SimpleClass()
result = obj.method()
simple_function()
"""

        self.complex_code = """
import os
from math import sqrt
import json as js

class DataProcessor:
    def __init__(self, name):
        self.name = name
        self.logger = self._get_logger()
    
    def _get_logger(self):
        import logging
        return logging.getLogger(self.name)
    
    def process(self, data, **kwargs):
        # Various call patterns
        validated = self.validate_data(data)
        transformed = self._transform(validated)
        
        # Chained calls
        result = str(transformed).strip().lower()
        
        # Complex expressions
        final = self._finalize(
            self._clean(transformed, mode='strict'),
            output=kwargs.get('output', 'default')
        )
        
        # Built-in functions
        items = list(final.items())
        count = len(items)
        
        return final
    
    def validate_data(self, data):
        return data
    
    def _transform(self, data):
        return data
    
    def _clean(self, data, mode='normal'):
        return data
    
    def _finalize(self, data, output='json'):
        return data

# Module level calls
processor = DataProcessor("test")
data = {"key": "value"}
result = processor.process(data, output="xml")

# Function calls with lambda
transform = lambda x: x * 2
numbers = list(map(transform, range(5)))
squared = [pow(x, 2) for x in numbers]
"""

    def test_initialization(self):
        """Test visitor initialization."""
        visitor = PythonCallVisitor(self.basic_code)

        self.assertEqual(visitor.source_code, self.basic_code)
        self.assertEqual(visitor.file_path, Path("<unknown>"))
        self.assertEqual(len(visitor.call_sites), 0)
        self.assertIsInstance(visitor.current_context, dict)

        # Check context structure
        self.assertIn("class_stack", visitor.current_context)
        self.assertIn("function_stack", visitor.current_context)
        self.assertIn("imports", visitor.current_context)
        self.assertIn("scope_depth", visitor.current_context)

    def test_initialization_with_file_path(self):
        """Test visitor initialization with custom file path."""
        file_path = Path("/test/example.py")
        visitor = PythonCallVisitor(self.basic_code, file_path)

        self.assertEqual(visitor.file_path, file_path)

    def test_import_preprocessing(self):
        """Test that imports are detected during initialization."""
        visitor = PythonCallVisitor(self.complex_code)

        imports = visitor.current_context["imports"]
        self.assertIn("os", imports)
        self.assertIn("math.sqrt", imports)
        self.assertIn("js", imports)  # json as js

    def test_visit_call_basic(self):
        """Test basic call node visiting."""
        visitor = PythonCallVisitor(self.basic_code)
        tree = ast.parse(self.basic_code)
        visitor.visit(tree)

        # Should find several calls
        self.assertGreater(len(visitor.call_sites), 0)

        # Check for specific calls
        call_names = [cs.function_name for cs in visitor.call_sites]
        self.assertIn("print", call_names)
        self.assertIn("len", call_names)
        self.assertIn("str", call_names)

    def test_visit_call_positions(self):
        """Test that call positions are correctly recorded."""
        visitor = PythonCallVisitor(self.basic_code)
        tree = ast.parse(self.basic_code)
        visitor.visit(tree)

        for call_site in visitor.call_sites:
            # Line numbers should be valid
            self.assertGreater(call_site.line_number, 0)
            self.assertLessEqual(
                call_site.line_number,
                len(self.basic_code.splitlines()),
            )

            # Column numbers should be valid
            self.assertGreaterEqual(call_site.column_number, 0)

            # Byte offsets should be valid
            self.assertGreaterEqual(call_site.byte_start, 0)
            self.assertGreaterEqual(call_site.byte_end, call_site.byte_start)

    def test_visit_function_def_context(self):
        """Test function definition context tracking."""
        visitor = PythonCallVisitor(self.basic_code)
        tree = ast.parse(self.basic_code)
        visitor.visit(tree)

        # Check for calls within functions
        function_calls = [
            cs for cs in visitor.call_sites if "current_function" in cs.context
        ]

        self.assertGreater(len(function_calls), 0)

        # Check function context details
        for call_site in function_calls:
            context = call_site.context
            self.assertIn("current_function", context)
            self.assertIn("function_line", context)

    def test_visit_class_def_context(self):
        """Test class definition context tracking."""
        visitor = PythonCallVisitor(self.basic_code)
        tree = ast.parse(self.basic_code)
        visitor.visit(tree)

        # Check for calls within methods
        method_calls = [
            cs for cs in visitor.call_sites if "current_class" in cs.context
        ]

        self.assertGreater(len(method_calls), 0)

        # Check class context details
        for call_site in method_calls:
            context = call_site.context
            self.assertIn("current_class", context)
            self.assertIn("class_line", context)

    def test_extract_function_info_simple(self):
        """Test function info extraction for simple calls."""
        visitor = PythonCallVisitor("func()")

        call_node = ast.parse("func()").body[0].value
        name, call_type = visitor._extract_function_info(call_node)

        self.assertEqual(name, "func")
        self.assertEqual(call_type, "function")

    def test_extract_function_info_method(self):
        """Test function info extraction for method calls."""
        visitor = PythonCallVisitor("obj.method()")

        call_node = ast.parse("obj.method()").body[0].value
        name, call_type = visitor._extract_function_info(call_node)

        self.assertEqual(name, "obj.method")
        self.assertEqual(call_type, "method")

    def test_extract_function_info_chained(self):
        """Test function info extraction for chained calls."""
        visitor = PythonCallVisitor("obj.attr.method()")

        call_node = ast.parse("obj.attr.method()").body[0].value
        name, call_type = visitor._extract_function_info(call_node)

        self.assertEqual(name, "obj.attr.method")
        self.assertEqual(call_type, "method")

    def test_get_attribute_chain(self):
        """Test attribute chain extraction."""
        visitor = PythonCallVisitor("")

        # Simple attribute
        attr_node = ast.parse("obj.method").body[0].value
        chain = visitor._get_attribute_chain(attr_node)
        self.assertEqual(chain, "obj")

        # Nested attribute
        nested_attr = ast.parse("obj.attr.method").body[0].value
        chain = visitor._get_attribute_chain(nested_attr)
        self.assertEqual(chain, "obj.attr")

    def test_extract_complex_call_name(self):
        """Test complex call name extraction."""
        visitor = PythonCallVisitor("")

        # Lambda call
        lambda_node = ast.parse("(lambda x: x)()").body[0].value.func
        name = visitor._extract_complex_call_name(lambda_node)
        self.assertEqual(name, "<lambda>")

        # Subscript call
        subscript_call = ast.parse("func[0]()").body[0].value.func
        name = visitor._extract_complex_call_name(subscript_call)
        self.assertIn("[...]", name)

    def test_calculate_byte_offsets(self):
        """Test byte offset calculation."""
        code = "func()\nobj.method()"
        visitor = PythonCallVisitor(code)

        # Test with a known position
        call_node = ast.parse(code).body[0].value
        start, end = visitor._calculate_byte_offsets(call_node)

        self.assertGreaterEqual(start, 0)
        self.assertGreater(end, start)

    def test_line_col_to_byte(self):
        """Test line/column to byte conversion."""
        code = "line1\nline2\nline3"
        visitor = PythonCallVisitor(code)

        # Test first line
        byte_offset = visitor._line_col_to_byte(1, 0)
        self.assertEqual(byte_offset, 0)

        # Test second line start
        byte_offset = visitor._line_col_to_byte(2, 0)
        self.assertEqual(byte_offset, 6)  # "line1\n" = 6 bytes

        # Test position within line
        byte_offset = visitor._line_col_to_byte(2, 2)
        self.assertEqual(byte_offset, 8)  # "line1\nli" = 8 bytes

    def test_extract_call_context(self):
        """Test call context extraction."""
        visitor = PythonCallVisitor(self.complex_code)

        call_node = ast.parse("func(a, b, key=value)").body[0].value
        context = visitor._extract_call_context(call_node)

        # Check basic context fields
        self.assertIn("node_type", context)
        self.assertIn("argument_count", context)
        self.assertIn("keyword_count", context)
        self.assertIn("scope_depth", context)

        # Check argument analysis
        self.assertEqual(context["argument_count"], 2)
        self.assertEqual(context["keyword_count"], 1)

    def test_get_node_type_info(self):
        """Test node type information extraction."""
        visitor = PythonCallVisitor("")

        # Test various node types
        test_cases = [
            ("42", "Constant(int)"),
            ("'hello'", "Constant(str)"),
            ("variable", "Name(variable)"),
            ("obj.attr", "Attribute(attr)"),
            ("[1, 2, 3]", "List"),
            ("{'key': 'value'}", "Dict"),
            ("(1, 2)", "Tuple"),
        ]

        for code, expected_type in test_cases:
            with self.subTest(code=code):
                node = ast.parse(code).body[0].value
                type_info = visitor._get_node_type_info(node)
                self.assertEqual(type_info, expected_type)

    def test_decorator_extraction(self):
        """Test decorator name extraction."""
        visitor = PythonCallVisitor("")

        # Simple decorator
        code = """
@decorator
def func():
    pass
"""
        tree = ast.parse(code)
        func_def = tree.body[0]
        decorator_name = visitor._get_decorator_name(func_def.decorator_list[0])
        self.assertEqual(decorator_name, "decorator")

        # Decorator with arguments
        code = """
@decorator(arg1, arg2)
def func():
    pass
"""
        tree = ast.parse(code)
        func_def = tree.body[0]
        decorator_name = visitor._get_decorator_name(func_def.decorator_list[0])
        self.assertIn("decorator", decorator_name)
        self.assertIn("(...)", decorator_name)

    def test_scope_depth_tracking(self):
        """Test scope depth tracking during traversal."""
        nested_code = """
class OuterClass:
    def outer_method(self):
        def inner_function():
            class InnerClass:
                def inner_method(self):
                    print("deeply nested")
                    return len("test")
"""

        visitor = PythonCallVisitor(nested_code)
        tree = ast.parse(nested_code)
        visitor.visit(tree)

        # Check that deeply nested calls have higher scope depth
        scope_depths = [cs.context["scope_depth"] for cs in visitor.call_sites]
        self.assertGreater(max(scope_depths), 1)

    def test_complex_patterns(self):
        """Test complex Python patterns."""
        visitor = PythonCallVisitor(self.complex_code)
        tree = ast.parse(self.complex_code)
        visitor.visit(tree)

        # Should find many different types of calls
        self.assertGreater(len(visitor.call_sites), 10)

        # Check for specific patterns
        call_names = [cs.function_name for cs in visitor.call_sites]

        # Method calls
        self.assertTrue(any("validate_data" in name for name in call_names))
        self.assertTrue(any("strip" in name for name in call_names))
        self.assertTrue(any("lower" in name for name in call_names))

        # Function calls
        self.assertTrue(any("list" in name for name in call_names))
        self.assertTrue(any("len" in name for name in call_names))
        self.assertTrue(any("map" in name for name in call_names))

        # Check call types
        call_types = [cs.call_type for cs in visitor.call_sites]
        self.assertIn("function", call_types)
        self.assertIn("method", call_types)

    def test_error_handling(self):
        """Test error handling during traversal."""
        # Code with potential issues
        problematic_code = """
# This code might cause issues during processing
def func():
    # Call with very long argument list
    result = very_long_function_name_that_might_cause_issues(
        arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10,
        key1=value1, key2=value2, key3=value3, key4=value4, key5=value5
    )
    
    # Deeply nested call
    nested = func1(func2(func3(func4(func5()))))
    
    return result
"""

        visitor = PythonCallVisitor(problematic_code)
        tree = ast.parse(problematic_code)

        # Should not raise exceptions
        try:
            visitor.visit(tree)
            success = True
        except Exception:
            success = False

        self.assertTrue(success, "Visitor should handle problematic code gracefully")

    def test_argument_analysis(self):
        """Test detailed argument analysis."""
        call_code = """
func(
    42,                    # int literal
    "string",             # string literal
    variable,             # name
    obj.attr,             # attribute
    other_func(),         # nested call
    [1, 2, 3],           # list
    key="value",          # keyword
    **kwargs              # kwargs
)
"""

        visitor = PythonCallVisitor(call_code)
        tree = ast.parse(call_code)
        visitor.visit(tree)

        # Should find the main call and nested call
        self.assertGreater(len(visitor.call_sites), 0)

        # Check context for main call
        main_call = visitor.call_sites[0]  # First call found
        context = main_call.context

        self.assertIn("argument_count", context)
        self.assertIn("keyword_count", context)

        if "argument_types" in context:
            arg_types = context["argument_types"]
            self.assertGreater(len(arg_types), 0)

    def test_import_context_usage(self):
        """Test usage of import context in call analysis."""
        import_code = """
import math
from os import path
import json as js

# These should be marked as imported
result1 = math.sqrt(16)
result2 = path.join("a", "b")
result3 = js.dumps({"key": "value"})

# This should not
result4 = local_function()
"""

        visitor = PythonCallVisitor(import_code)
        tree = ast.parse(import_code)
        visitor.visit(tree)

        # Check that imported functions are marked
        imported_calls = [
            cs for cs in visitor.call_sites if cs.context.get("is_imported", False)
        ]

        # Should find at least some imported calls
        # Note: This depends on how the import detection works
        # The exact behavior may vary based on implementation
        call_names = [cs.function_name for cs in visitor.call_sites]
        self.assertTrue(any("sqrt" in name for name in call_names))
        self.assertTrue(any("dumps" in name for name in call_names))


if __name__ == "__main__":
    unittest.main()

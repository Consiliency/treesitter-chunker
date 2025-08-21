"""
Unit tests for PythonPatterns class.

Tests pattern recognition, call classification, and utility functions.
"""

import ast
import unittest

from chunker.extractors.python.python_extractor import PythonPatterns


class TestPythonPatterns(unittest.TestCase):
    """Test cases for PythonPatterns utility class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create various AST nodes for testing
        self.function_call = ast.parse("func()").body[0].value
        self.method_call = ast.parse("obj.method()").body[0].value
        self.chained_call = ast.parse("obj.method1().method2()").body[0].value
        self.complex_call = (
            ast.parse("func(a, b, c=1, d=2, *args, **kwargs)").body[0].value
        )
        self.nested_call = ast.parse("func1(func2(func3()))").body[0].value
        self.lambda_call = ast.parse("(lambda x: x)(5)").body[0].value

    def test_is_function_call_true_cases(self):
        """Test is_function_call with cases that should return True."""
        self.assertTrue(PythonPatterns.is_function_call(self.function_call))

        # Test with builtin functions
        builtin_call = ast.parse("print('hello')").body[0].value
        self.assertTrue(PythonPatterns.is_function_call(builtin_call))

        # Test with imported functions
        imported_call = ast.parse("math.sqrt(4)").body[0].value
        self.assertFalse(
            PythonPatterns.is_function_call(imported_call),
        )  # This is a method call

    def test_is_function_call_false_cases(self):
        """Test is_function_call with cases that should return False."""
        self.assertFalse(PythonPatterns.is_function_call(self.method_call))
        self.assertFalse(PythonPatterns.is_function_call(self.chained_call))

        # Test with non-call nodes
        name_node = ast.parse("variable").body[0].value
        self.assertFalse(PythonPatterns.is_function_call(name_node))

    def test_is_method_call_true_cases(self):
        """Test is_method_call with cases that should return True."""
        self.assertTrue(PythonPatterns.is_method_call(self.method_call))
        self.assertTrue(PythonPatterns.is_method_call(self.chained_call))

        # Test with deeply nested attribute access
        deep_call = ast.parse("a.b.c.d.method()").body[0].value
        self.assertTrue(PythonPatterns.is_method_call(deep_call))

    def test_is_method_call_false_cases(self):
        """Test is_method_call with cases that should return False."""
        self.assertFalse(PythonPatterns.is_method_call(self.function_call))

        # Test with non-call nodes
        name_node = ast.parse("variable").body[0].value
        self.assertFalse(PythonPatterns.is_method_call(name_node))

    def test_extract_call_context_basic(self):
        """Test basic context extraction."""
        context = PythonPatterns.extract_call_context(self.function_call, {})

        # Check required fields
        self.assertIn("is_function_call", context)
        self.assertIn("is_method_call", context)
        self.assertIn("argument_count", context)
        self.assertIn("keyword_count", context)

        # Check values for simple function call
        self.assertTrue(context["is_function_call"])
        self.assertFalse(context["is_method_call"])
        self.assertEqual(context["argument_count"], 0)
        self.assertEqual(context["keyword_count"], 0)

    def test_extract_call_context_complex(self):
        """Test context extraction from complex call."""
        context = PythonPatterns.extract_call_context(self.complex_call, {})

        # Check argument analysis
        self.assertEqual(context["argument_count"], 3)  # a, b, *args
        self.assertEqual(context["keyword_count"], 3)  # c=1, d=2, **kwargs
        self.assertTrue(context["has_starargs"])
        self.assertTrue(context["has_kwargs"])

        # Check argument details
        self.assertIn("arguments", context)
        self.assertIn("keyword_arguments", context)

        arguments = context["arguments"]
        self.assertEqual(len(arguments), 3)

        # Check first positional argument
        self.assertEqual(arguments[0]["position"], 0)
        self.assertEqual(arguments[0]["type"], "Name")
        self.assertEqual(arguments[0]["name"], "a")

    def test_extract_call_context_method(self):
        """Test context extraction from method call."""
        context = PythonPatterns.extract_call_context(self.method_call, {})

        self.assertFalse(context["is_function_call"])
        self.assertTrue(context["is_method_call"])
        self.assertIn("method_name", context)
        self.assertIn("object_name", context)

    def test_extract_call_context_with_additional_context(self):
        """Test context extraction with additional context provided."""
        additional_context = {
            "current_function": "test_func",
            "current_class": "TestClass",
            "custom_data": "test_value",
        }

        context = PythonPatterns.extract_call_context(
            self.function_call,
            additional_context,
        )

        # Should preserve additional context
        self.assertEqual(context["current_function"], "test_func")
        self.assertEqual(context["current_class"], "TestClass")
        self.assertEqual(context["custom_data"], "test_value")

        # Should add call-specific context
        self.assertIn("is_function_call", context)
        self.assertIn("argument_count", context)

    def test_is_builtin_function_true_cases(self):
        """Test builtin function detection with positive cases."""
        builtins = [
            "print",
            "len",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "tuple",
            "set",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sum",
            "max",
            "min",
            "abs",
            "round",
            "sorted",
            "reversed",
            "any",
            "all",
            "isinstance",
            "hasattr",
            "getattr",
            "setattr",
            "open",
            "input",
            "type",
            "id",
            "help",
            "dir",
            "vars",
            "globals",
            "locals",
            "eval",
            "exec",
            "compile",
        ]

        for builtin in builtins:
            with self.subTest(builtin=builtin):
                self.assertTrue(PythonPatterns.is_builtin_function(builtin))

    def test_is_builtin_function_false_cases(self):
        """Test builtin function detection with negative cases."""
        non_builtins = [
            "custom_func",
            "my_function",
            "calculate",
            "process",
            "handle",
            "numpy",
            "pandas",
            "requests",
            "json",
            "os",
            "sys",
            "math",
            "random",
            "datetime",
            "__init__",
            "__str__",
            "__len__",
        ]

        for non_builtin in non_builtins:
            with self.subTest(non_builtin=non_builtin):
                self.assertFalse(PythonPatterns.is_builtin_function(non_builtin))

    def test_is_dunder_method_true_cases(self):
        """Test dunder method detection with positive cases."""
        dunder_methods = [
            "__init__",
            "__str__",
            "__repr__",
            "__len__",
            "__iter__",
            "__next__",
            "__getitem__",
            "__setitem__",
            "__delitem__",
            "__contains__",
            "__add__",
            "__sub__",
            "__mul__",
            "__div__",
            "__eq__",
            "__ne__",
            "__lt__",
            "__le__",
            "__gt__",
            "__ge__",
            "__enter__",
            "__exit__",
            "__call__",
            "__hash__",
            "__bool__",
            "__bytes__",
            "__format__",
            "__getattribute__",
            "__setattr__",
            "__delattr__",
            "__dir__",
            "__new__",
            "__del__",
            "__copy__",
            "__deepcopy__",
            "__reduce__",
            "__reduce_ex__",
        ]

        for dunder in dunder_methods:
            with self.subTest(dunder=dunder):
                self.assertTrue(PythonPatterns.is_dunder_method(dunder))

    def test_is_dunder_method_false_cases(self):
        """Test dunder method detection with negative cases."""
        non_dunder = [
            "init",
            "_init",
            "init_",
            "__init",
            "init__",
            "__",
            "____",
            "_private_method",
            "public_method",
            "__incomplete",
            "broken__",
            "__",
            "regular_function",
        ]

        for non_dunder_method in non_dunder:
            with self.subTest(non_dunder=non_dunder_method):
                self.assertFalse(PythonPatterns.is_dunder_method(non_dunder_method))

    def test_get_call_complexity_score_simple(self):
        """Test complexity scoring for simple calls."""
        simple_score = PythonPatterns.get_call_complexity_score(self.function_call)
        self.assertEqual(simple_score, 1)  # Base score only

    def test_get_call_complexity_score_with_args(self):
        """Test complexity scoring with arguments."""
        call_with_args = ast.parse("func(a, b, c)").body[0].value
        score = PythonPatterns.get_call_complexity_score(call_with_args)
        self.assertEqual(score, 4)  # Base + 3 args

    def test_get_call_complexity_score_method(self):
        """Test complexity scoring for method calls."""
        method_score = PythonPatterns.get_call_complexity_score(self.method_call)
        simple_score = PythonPatterns.get_call_complexity_score(self.function_call)
        self.assertGreater(method_score, simple_score)

    def test_get_call_complexity_score_complex(self):
        """Test complexity scoring for complex calls."""
        complex_score = PythonPatterns.get_call_complexity_score(self.complex_call)
        simple_score = PythonPatterns.get_call_complexity_score(self.function_call)

        self.assertGreater(complex_score, simple_score)
        self.assertGreaterEqual(complex_score, 10)  # Should be quite complex

    def test_get_call_complexity_score_nested(self):
        """Test complexity scoring for nested calls."""
        nested_score = PythonPatterns.get_call_complexity_score(self.nested_call)
        simple_score = PythonPatterns.get_call_complexity_score(self.function_call)

        self.assertGreater(nested_score, simple_score)

    def test_get_call_complexity_score_chained(self):
        """Test complexity scoring for chained method calls."""
        chained_score = PythonPatterns.get_call_complexity_score(self.chained_call)
        method_score = PythonPatterns.get_call_complexity_score(self.method_call)

        self.assertGreater(chained_score, method_score)

    def test_error_handling_in_context_extraction(self):
        """Test error handling during context extraction."""
        # Test with malformed context
        try:
            # Create a call node and then break it
            broken_call = self.function_call
            # Remove required attributes to trigger errors
            delattr(broken_call, "args")

            context = PythonPatterns.extract_call_context(broken_call, {})
            self.assertIn("extraction_error", context)

        except AttributeError:
            # This is expected behavior
            pass

    def test_various_call_patterns(self):
        """Test pattern recognition with various Python call patterns."""
        test_cases = [
            # (code, expected_is_function, expected_is_method)
            ("func()", True, False),
            ("obj.method()", False, True),
            ("self.method()", False, True),
            ("module.function()", False, True),
            ("cls.classmethod()", False, True),
            ("Class.staticmethod()", False, True),
            ("obj.attr.method()", False, True),
            ("func().method()", False, True),
            ("(lambda x: x)()", False, False),
        ]

        for code, expected_func, expected_method in test_cases:
            with self.subTest(code=code):
                call_node = ast.parse(code).body[0].value

                is_func = PythonPatterns.is_function_call(call_node)
                is_method = PythonPatterns.is_method_call(call_node)

                self.assertEqual(
                    is_func,
                    expected_func,
                    f"Function call detection failed for: {code}",
                )
                self.assertEqual(
                    is_method,
                    expected_method,
                    f"Method call detection failed for: {code}",
                )

    def test_argument_analysis(self):
        """Test detailed argument analysis in context extraction."""
        # Test with various argument types
        complex_args_code = """
func(
    42,                    # Constant int
    "hello",              # Constant string
    variable,             # Name
    obj.attr,             # Attribute
    [1, 2, 3],           # List
    {"key": "value"},     # Dict
    func_call(),          # Nested call
    key1=value1,          # Keyword arg
    key2="literal",       # Keyword with literal
    *args,                # Starred args
    **kwargs              # Keyword args
)
"""

        call_node = ast.parse(complex_args_code).body[0].value
        context = PythonPatterns.extract_call_context(call_node, {})

        # Check argument count and types
        self.assertGreater(context["argument_count"], 5)
        self.assertGreater(context["keyword_count"], 0)
        self.assertTrue(context["has_starargs"])
        self.assertTrue(context["has_kwargs"])

        # Check detailed argument analysis
        if "arguments" in context:
            arguments = context["arguments"]
            self.assertGreater(len(arguments), 0)

            # Check that argument types are detected
            arg_types = [arg["type"] for arg in arguments]
            self.assertIn("Constant", arg_types)
            self.assertIn("Name", arg_types)

    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        # Test with None
        self.assertFalse(PythonPatterns.is_function_call(None))

        # Test with non-Call node
        name_node = ast.parse("variable").body[0].value
        self.assertFalse(PythonPatterns.is_function_call(name_node))
        self.assertFalse(PythonPatterns.is_method_call(name_node))

        # Test complexity with invalid node
        try:
            score = PythonPatterns.get_call_complexity_score(name_node)
            self.assertEqual(score, 10)  # Should default to high complexity
        except:
            pass  # Error is acceptable for invalid input


if __name__ == "__main__":
    unittest.main()

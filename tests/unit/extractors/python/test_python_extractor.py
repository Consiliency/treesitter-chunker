"""
Comprehensive unit tests for Python extractor.

Tests cover all functionality including AST parsing, call site extraction,
context tracking, and error handling scenarios.
"""

import ast
import unittest
from pathlib import Path
from typing import Any, Dict, List

from chunker.extractors.core.extraction_framework import CallSite, ExtractionResult
from chunker.extractors.python.python_extractor import (
    PythonCallVisitor,
    PythonExtractor,
    PythonPatterns,
)


class TestPythonCallVisitor(unittest.TestCase):
    """Test cases for PythonCallVisitor."""

    def setUp(self):
        """Set up test fixtures."""
        self.simple_code = """
def greet(name):
    print(f"Hello, {name}!")
    return len(name)

class Calculator:
    def add(self, a, b):
        return a + b

    def multiply(self, x, y):
        result = self.add(x * y, 0)
        return result

calc = Calculator()
result = calc.add(5, 3)
calc.multiply(2, 4)
greet("World")
max(1, 2, 3)
"""

        self.complex_code = """
import os
from datetime import datetime
import json as js

class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.logger = self._setup_logger()

    def _setup_logger(self):
        import logging
        return logging.getLogger(__name__)

    def process_data(self, data, **kwargs):
        # Method calls with various patterns
        processed = self._transform(data)
        validated = self.validate(processed, strict=True)

        # Chained method calls
        result = self.config.get('output', {}).get('format', 'json')

        # Function calls with complex arguments
        output = json.dumps(validated, default=str, indent=2)

        # Built-in functions
        items = list(validated.items())
        count = len(items)

        # Nested calls
        final = self._finalize(self._cleanup(validated))

        return final

    def _transform(self, data):
        return data

    def validate(self, data, strict=False):
        return data

    def _cleanup(self, data):
        return data

    def _finalize(self, data):
        return data

# Module-level function calls
processor = DataProcessor({'output': {'format': 'json'}})
result = processor.process_data({'key': 'value'}, timeout=30)

# Lambda calls
transform = lambda x: x * 2
values = list(map(transform, [1, 2, 3]))

# Decorators and complex expressions
@property
def computed_value(self):
    return sum(range(10))
"""

    def test_initialization(self):
        """Test visitor initialization."""
        visitor = PythonCallVisitor(self.simple_code)

        self.assertEqual(visitor.source_code, self.simple_code)
        self.assertEqual(visitor.file_path, Path("<unknown>"))
        self.assertEqual(visitor.call_sites, [])
        self.assertIsInstance(visitor.current_context, dict)
        self.assertIn("class_stack", visitor.current_context)
        self.assertIn("function_stack", visitor.current_context)
        self.assertIn("imports", visitor.current_context)

    def test_initialization_with_file_path(self):
        """Test visitor initialization with file path."""
        file_path = Path("/test/file.py")
        visitor = PythonCallVisitor(self.simple_code, file_path)

        self.assertEqual(visitor.file_path, file_path)

    def test_simple_function_calls(self):
        """Test extraction of simple function calls."""
        visitor = PythonCallVisitor(self.simple_code)
        tree = ast.parse(self.simple_code)
        visitor.visit(tree)

        # Should find: print, len, greet, max
        function_calls = [cs for cs in visitor.call_sites if cs.call_type == "function"]
        function_names = [cs.function_name for cs in function_calls]

        self.assertIn("print", function_names)
        self.assertIn("len", function_names)
        self.assertIn("greet", function_names)
        self.assertIn("max", function_names)

    def test_method_calls(self):
        """Test extraction of method calls."""
        visitor = PythonCallVisitor(self.simple_code)
        tree = ast.parse(self.simple_code)
        visitor.visit(tree)

        # Should find: calc.add, calc.multiply, self.add
        method_calls = [cs for cs in visitor.call_sites if cs.call_type == "method"]

        # Check for method calls
        calc_add_calls = [cs for cs in method_calls if cs.function_name.endswith("add")]
        calc_multiply_calls = [
            cs for cs in method_calls if cs.function_name.endswith("multiply")
        ]

        self.assertGreater(len(calc_add_calls), 0)
        self.assertGreater(len(calc_multiply_calls), 0)

    def test_context_tracking(self):
        """Test context tracking during traversal."""
        visitor = PythonCallVisitor(self.simple_code)
        tree = ast.parse(self.simple_code)
        visitor.visit(tree)

        # Check that some call sites have context information
        for call_site in visitor.call_sites:
            self.assertIsInstance(call_site.context, dict)
            self.assertIn("node_type", call_site.context)
            self.assertIn("argument_count", call_site.context)

        # Check for calls inside methods
        method_calls = [
            cs for cs in visitor.call_sites if "current_function" in cs.context
        ]
        self.assertGreater(len(method_calls), 0)

    def test_complex_calls(self):
        """Test extraction from complex code patterns."""
        visitor = PythonCallVisitor(self.complex_code)
        tree = ast.parse(self.complex_code)
        visitor.visit(tree)

        # Should find various types of calls
        call_names = [cs.function_name for cs in visitor.call_sites]

        # Check for different call patterns
        self.assertTrue(any("dumps" in name for name in call_names))
        self.assertTrue(any("get" in name for name in call_names))
        self.assertTrue(any("items" in name for name in call_names))
        self.assertTrue(any("map" in name for name in call_names))

    def test_chained_method_calls(self):
        """Test extraction of chained method calls."""
        code = """
obj.method1().method2().method3()
config.get('key').strip().lower()
"""
        visitor = PythonCallVisitor(code)
        tree = ast.parse(code)
        visitor.visit(tree)

        # Should find multiple method calls
        method_calls = [cs for cs in visitor.call_sites if cs.call_type == "method"]
        self.assertGreaterEqual(len(method_calls), 5)  # At least 5 method calls

    def test_nested_calls(self):
        """Test extraction of nested function calls."""
        code = """
result = func1(func2(func3(x, y), z))
print(str(len(data.split(','))))
"""
        visitor = PythonCallVisitor(code)
        tree = ast.parse(code)
        visitor.visit(tree)

        # Should find all nested calls
        call_names = [cs.function_name for cs in visitor.call_sites]

        expected_calls = ["func1", "func2", "func3", "print", "str", "len"]
        for expected in expected_calls:
            self.assertTrue(any(expected in name for name in call_names))

    def test_call_site_positions(self):
        """Test that call sites have correct position information."""
        visitor = PythonCallVisitor(self.simple_code)
        tree = ast.parse(self.simple_code)
        visitor.visit(tree)

        for call_site in visitor.call_sites:
            # Check line numbers are valid
            self.assertGreater(call_site.line_number, 0)
            self.assertGreaterEqual(call_site.column_number, 0)

            # Check byte offsets are valid
            self.assertGreaterEqual(call_site.byte_start, 0)
            self.assertGreaterEqual(call_site.byte_end, call_site.byte_start)

    def test_import_tracking(self):
        """Test import tracking functionality."""
        visitor = PythonCallVisitor(self.complex_code)
        tree = ast.parse(self.complex_code)
        visitor.visit(tree)

        # Check that imports were detected
        imports = visitor.current_context["imports"]
        self.assertIn("os", imports)
        self.assertIn("datetime.datetime", imports)
        self.assertIn("js", imports)  # json as js


class TestPythonExtractor(unittest.TestCase):
    """Test cases for PythonExtractor."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = PythonExtractor()

        self.valid_python_code = """
def calculate_sum(numbers):
    total = sum(numbers)
    print(f"Sum is: {total}")
    return total

class MathUtils:
    @staticmethod
    def multiply(a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Division by zero")
        return a / b

# Usage
numbers = [1, 2, 3, 4, 5]
result = calculate_sum(numbers)
utils = MathUtils()
product = utils.multiply(3, 4)
quotient = utils.divide(10, 2)
"""

        self.invalid_python_code = """
def broken_function(
    # Missing closing parenthesis and other syntax errors
    print "Hello World"  # Python 2 style print
    return
"""

    def test_initialization(self):
        """Test extractor initialization."""
        self.assertEqual(self.extractor.language, "python")
        self.assertIsInstance(self.extractor.patterns, PythonPatterns)

    def test_extract_calls_valid_code(self):
        """Test call extraction from valid Python code."""
        result = self.extractor.extract_calls(self.valid_python_code)

        self.assertIsInstance(result, ExtractionResult)
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 0)
        self.assertGreater(result.extraction_time, 0)

        # Check metadata
        self.assertEqual(result.metadata["language"], "python")
        self.assertIn("ast_node_count", result.metadata)
        self.assertIn("source_lines", result.metadata)

    def test_extract_calls_with_file_path(self):
        """Test call extraction with file path."""
        file_path = Path("/test/example.py")
        result = self.extractor.extract_calls(self.valid_python_code, file_path)

        self.assertTrue(result.is_successful())

        # Check that all call sites have the correct file path
        for call_site in result.call_sites:
            self.assertEqual(call_site.file_path, file_path)

    def test_extract_calls_invalid_code(self):
        """Test call extraction from invalid Python code."""
        result = self.extractor.extract_calls(self.invalid_python_code)

        self.assertFalse(result.is_successful())
        self.assertGreater(len(result.errors), 0)
        self.assertEqual(len(result.call_sites), 0)

    def test_validate_source_valid(self):
        """Test source validation with valid code."""
        self.assertTrue(self.extractor.validate_source(self.valid_python_code))
        self.assertTrue(self.extractor.validate_source(""))  # Empty is valid
        self.assertTrue(self.extractor.validate_source("# Just a comment"))

    def test_validate_source_invalid(self):
        """Test source validation with invalid code."""
        self.assertFalse(self.extractor.validate_source(self.invalid_python_code))
        self.assertFalse(self.extractor.validate_source("def func("))  # Incomplete
        self.assertFalse(self.extractor.validate_source(123))  # Not a string

    def test_extract_function_calls(self):
        """Test extraction of function calls only."""
        function_calls = self.extractor.extract_function_calls(self.valid_python_code)

        self.assertIsInstance(function_calls, list)

        # All returned calls should be function calls
        for call_site in function_calls:
            self.assertEqual(call_site.call_type, "function")

        # Should find function calls like sum, print, ValueError
        function_names = [cs.function_name for cs in function_calls]
        self.assertIn("sum", function_names)
        self.assertIn("print", function_names)

    def test_extract_method_calls(self):
        """Test extraction of method calls only."""
        method_calls = self.extractor.extract_method_calls(self.valid_python_code)

        self.assertIsInstance(method_calls, list)

        # All returned calls should be method calls
        for call_site in method_calls:
            self.assertEqual(call_site.call_type, "method")

        # Should find method calls like utils.multiply, utils.divide
        method_names = [cs.function_name for cs in method_calls]
        self.assertTrue(any("multiply" in name for name in method_names))
        self.assertTrue(any("divide" in name for name in method_names))

    def test_error_handling(self):
        """Test error handling in extraction."""
        # Test with None input
        result = self.extractor.extract_calls(None)
        self.assertFalse(result.is_successful())

        # Test with empty string
        result = self.extractor.extract_calls("")
        self.assertFalse(result.is_successful())

    def test_performance_metrics(self):
        """Test that performance metrics are collected."""
        result = self.extractor.extract_calls(self.valid_python_code)

        self.assertIsInstance(result.performance_metrics, dict)
        self.assertGreater(result.extraction_time, 0)

    def test_call_site_validation(self):
        """Test that extracted call sites are valid."""
        result = self.extractor.extract_calls(self.valid_python_code)

        for call_site in result.call_sites:
            # Basic validation
            self.assertIsNotNone(call_site.function_name)
            self.assertGreater(call_site.line_number, 0)
            self.assertGreaterEqual(call_site.column_number, 0)
            self.assertGreaterEqual(call_site.byte_start, 0)
            self.assertGreaterEqual(call_site.byte_end, call_site.byte_start)
            self.assertEqual(call_site.language, "python")

    def test_complex_python_patterns(self):
        """Test extraction from complex Python patterns."""
        complex_code = """
import functools
from collections import defaultdict

# Decorators
@functools.lru_cache(maxsize=None)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Lambda functions
square = lambda x: x ** 2
numbers = list(map(square, range(10)))

# Comprehensions with calls
results = [str(fibonacci(i)) for i in range(5)]
data = {k: len(v) for k, v in defaultdict(list).items()}

# Context managers
with open('file.txt', 'r') as f:
    content = f.read().strip()

# Exception handling
try:
    result = int(input("Enter number: "))
except ValueError as e:
    print(f"Error: {e}")

# Async calls (if supported)
async def async_func():
    await some_async_call()
"""

        result = self.extractor.extract_calls(complex_code)
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 0)

        # Should find various types of calls
        call_names = [cs.function_name for cs in result.call_sites]
        self.assertTrue(any("fibonacci" in name for name in call_names))
        self.assertTrue(any("map" in name for name in call_names))
        self.assertTrue(any("str" in name for name in call_names))


class TestPythonPatterns(unittest.TestCase):
    """Test cases for PythonPatterns."""

    def setUp(self):
        """Set up test fixtures."""
        self.simple_call = ast.parse("func()").body[0].value
        self.method_call = ast.parse("obj.method()").body[0].value
        self.complex_call = ast.parse("obj.method(arg1, arg2, key=value)").body[0].value

    def test_is_function_call(self):
        """Test function call detection."""
        self.assertTrue(PythonPatterns.is_function_call(self.simple_call))
        self.assertFalse(PythonPatterns.is_function_call(self.method_call))

    def test_is_method_call(self):
        """Test method call detection."""
        self.assertFalse(PythonPatterns.is_method_call(self.simple_call))
        self.assertTrue(PythonPatterns.is_method_call(self.method_call))

    def test_extract_call_context(self):
        """Test context extraction from call nodes."""
        context = PythonPatterns.extract_call_context(self.complex_call, {})

        self.assertIsInstance(context, dict)
        self.assertIn("is_function_call", context)
        self.assertIn("is_method_call", context)
        self.assertIn("argument_count", context)
        self.assertIn("keyword_count", context)

        # Check specific values for complex call
        self.assertEqual(context["argument_count"], 2)
        self.assertEqual(context["keyword_count"], 1)

    def test_is_builtin_function(self):
        """Test builtin function detection."""
        self.assertTrue(PythonPatterns.is_builtin_function("print"))
        self.assertTrue(PythonPatterns.is_builtin_function("len"))
        self.assertTrue(PythonPatterns.is_builtin_function("str"))
        self.assertTrue(PythonPatterns.is_builtin_function("int"))

        self.assertFalse(PythonPatterns.is_builtin_function("custom_func"))
        self.assertFalse(PythonPatterns.is_builtin_function("my_function"))

    def test_is_dunder_method(self):
        """Test dunder method detection."""
        self.assertTrue(PythonPatterns.is_dunder_method("__init__"))
        self.assertTrue(PythonPatterns.is_dunder_method("__str__"))
        self.assertTrue(PythonPatterns.is_dunder_method("__len__"))

        self.assertFalse(PythonPatterns.is_dunder_method("init"))
        self.assertFalse(PythonPatterns.is_dunder_method("_private"))
        self.assertFalse(PythonPatterns.is_dunder_method("__"))

    def test_get_call_complexity_score(self):
        """Test call complexity scoring."""
        simple_score = PythonPatterns.get_call_complexity_score(self.simple_call)
        complex_score = PythonPatterns.get_call_complexity_score(self.complex_call)

        self.assertGreater(complex_score, simple_score)
        self.assertGreater(simple_score, 0)

        # Test nested call complexity
        nested_call = ast.parse("func(other_func(x, y))").body[0].value
        nested_score = PythonPatterns.get_call_complexity_score(nested_call)
        self.assertGreater(nested_score, simple_score)


class TestPythonExtractorIntegration(unittest.TestCase):
    """Integration tests for Python extractor."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = PythonExtractor()

    def test_real_world_python_file(self):
        """Test extraction from a realistic Python file."""
        real_world_code = '''
#!/usr/bin/env python3
"""
A sample Python module demonstrating various call patterns.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Configuration data class."""
    debug: bool = False
    max_workers: int = 4
    output_dir: Path = Path("output")

    def __post_init__(self):
        """Post-initialization validation."""
        if not isinstance(self.output_dir, Path):
            self.output_dir = Path(self.output_dir)

        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

class DataProcessor:
    """Process data with various operations."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()

    def _setup_logging(self):
        """Set up logging configuration."""
        level = logging.DEBUG if self.config.debug else logging.INFO
        logging.basicConfig(level=level)

    def process_files(self, file_paths: List[Path]) -> Dict[str, any]:
        """Process multiple files."""
        results = {}

        for file_path in file_paths:
            try:
                self.logger.info(f"Processing {file_path}")
                data = self._read_file(file_path)
                processed = self._process_data(data)
                results[str(file_path)] = processed

            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
                results[str(file_path)] = None

        return results

    def _read_file(self, file_path: Path) -> Dict:
        """Read and parse JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _process_data(self, data: Dict) -> Dict:
        """Process data with transformations."""
        # Various data transformations
        processed = {}

        for key, value in data.items():
            if isinstance(value, str):
                processed[key] = value.strip().lower()
            elif isinstance(value, (int, float)):
                processed[key] = abs(value)
            elif isinstance(value, list):
                processed[key] = [self._normalize_item(item) for item in value]
            else:
                processed[key] = str(value)

        return processed

    def _normalize_item(self, item):
        """Normalize individual items."""
        if hasattr(item, 'strip'):
            return item.strip()
        return item

    def save_results(self, results: Dict, output_file: Optional[Path] = None):
        """Save processing results."""
        if output_file is None:
            output_file = self.config.output_dir / "results.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)

        self.logger.info(f"Results saved to {output_file}")

def main():
    """Main entry point."""
    config = Config(debug=True)
    processor = DataProcessor(config)

    # Get files from command line or default
    if len(sys.argv) > 1:
        file_paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        file_paths = list(Path.cwd().glob("*.json"))

    if not file_paths:
        print("No files to process")
        return

    results = processor.process_files(file_paths)
    processor.save_results(results)

    print(f"Processed {len(results)} files")

if __name__ == "__main__":
    main()
'''

        result = self.extractor.extract_calls(real_world_code)

        # Should successfully extract calls
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 0)

        # Should find various types of calls
        call_names = [cs.function_name for cs in result.call_sites]

        # Function calls
        self.assertTrue(any("print" in name for name in call_names))
        self.assertTrue(any("len" in name for name in call_names))

        # Method calls
        self.assertTrue(any("strip" in name for name in call_names))
        self.assertTrue(any("lower" in name for name in call_names))
        self.assertTrue(any("mkdir" in name for name in call_names))

        # Module function calls
        self.assertTrue(any("getLogger" in name for name in call_names))

        # Check call types distribution
        call_types = [cs.call_type for cs in result.call_sites]
        self.assertIn("function", call_types)
        self.assertIn("method", call_types)

    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        # Empty code
        result = self.extractor.extract_calls("")
        self.assertFalse(result.is_successful())

        # Only comments
        result = self.extractor.extract_calls("# Just a comment\n")
        self.assertTrue(result.is_successful())
        self.assertEqual(len(result.call_sites), 0)

        # Code with syntax errors
        result = self.extractor.extract_calls("def func(\n")
        self.assertFalse(result.is_successful())

        # Code with unusual characters
        result = self.extractor.extract_calls("print('Hello 🌍')")
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 0)


if __name__ == "__main__":
    unittest.main()

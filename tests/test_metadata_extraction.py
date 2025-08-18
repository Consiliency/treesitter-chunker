"""Tests for metadata extraction functionality."""

import pytest

from chunker.core import chunk_text
from chunker.metadata import MetadataExtractorFactory
from chunker.metadata.languages import (
    JavaScriptComplexityAnalyzer,
    JavaScriptMetadataExtractor,
    PythonComplexityAnalyzer,
    PythonMetadataExtractor,
    TypeScriptMetadataExtractor,
)
from chunker.parser import get_parser


class TestMetadataExtractorFactory:
    """Test the metadata extractor factory."""

    @staticmethod
    def test_create_python_extractor():
        """Test creating Python metadata extractor."""
        extractor = MetadataExtractorFactory.create_extractor("python")
        assert isinstance(extractor, PythonMetadataExtractor)

    @staticmethod
    def test_create_javascript_extractor():
        """Test creating JavaScript metadata extractor."""
        extractor = MetadataExtractorFactory.create_extractor("javascript")
        assert isinstance(extractor, JavaScriptMetadataExtractor)

    @staticmethod
    def test_create_typescript_extractor():
        """Test creating TypeScript metadata extractor."""
        extractor = MetadataExtractorFactory.create_extractor("typescript")
        assert isinstance(extractor, TypeScriptMetadataExtractor)

    @staticmethod
    def test_create_unsupported_language():
        """Test creating extractor for unsupported language."""
        extractor = MetadataExtractorFactory.create_extractor("cobol")
        assert extractor is None

    @staticmethod
    def test_create_analyzer():
        """Test creating complexity analyzer."""
        analyzer = MetadataExtractorFactory.create_analyzer("python")
        assert isinstance(analyzer, PythonComplexityAnalyzer)

    @staticmethod
    def test_create_both():
        """Test creating both extractor and analyzer."""
        extractor, analyzer = MetadataExtractorFactory.create_both(
            "javascript",
        )
        assert isinstance(extractor, JavaScriptMetadataExtractor)
        assert isinstance(analyzer, JavaScriptComplexityAnalyzer)

    @staticmethod
    def test_is_supported():
        """Test language support check."""
        assert MetadataExtractorFactory.is_supported("python")
        assert MetadataExtractorFactory.is_supported("javascript")
        assert MetadataExtractorFactory.is_supported("typescript")
        assert not MetadataExtractorFactory.is_supported("cobol")

    @staticmethod
    def test_supported_languages():
        """Test getting list of supported languages."""
        languages = MetadataExtractorFactory.supported_languages()
        assert "python" in languages
        assert "javascript" in languages
        assert "typescript" in languages
        assert "jsx" in languages
        assert "tsx" in languages


class TestPythonMetadataExtraction:
    """Test Python-specific metadata extraction."""

    @classmethod
    @pytest.fixture()
    def extractor(cls):
        return PythonMetadataExtractor()

    @classmethod
    @pytest.fixture()
    def analyzer(cls):
        return PythonComplexityAnalyzer()

    @staticmethod
    def test_extract_simple_function_signature(extractor):
        """Test extracting signature from simple function."""
        code = '\ndef hello():\n    print("Hello, world!")\n'
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature is not None
        assert signature.name == "hello"
        assert signature.parameters == []
        assert signature.return_type is None
        assert signature.decorators == []
        assert signature.modifiers == []

    @staticmethod
    def test_extract_function_with_parameters(extractor):
        """Test extracting function with parameters."""
        code = """
def greet(name: str, age: int = 18) -> str:
    return f"Hello {name}, you are {age}\"
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature.name == "greet"
        assert len(signature.parameters) == 2
        assert signature.parameters[0]["name"] == "name"
        assert signature.parameters[0]["type"] == "str"
        assert signature.parameters[1]["name"] == "age"
        assert signature.parameters[1]["type"] == "int"
        assert signature.parameters[1]["default"] == "18"
        assert signature.return_type == "str"

    @staticmethod
    def test_extract_decorated_function(extractor):
        """Test extracting decorated function."""
        code = """
@staticmethod
@lru_cache(maxsize=128)
def compute(x: int) -> int:
    return x * x
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        decorated_node = tree.root_node.children[0]
        func_node = None
        for child in decorated_node.children:
            if child.type == "function_definition":
                func_node = child
                break
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature.name == "compute"
        assert "staticmethod" in signature.decorators
        assert "lru_cache(maxsize=128)" in signature.decorators
        assert "staticmethod" in signature.modifiers

    @staticmethod
    def test_extract_async_function(extractor):
        """Test extracting async function."""
        code = '\nasync def fetch_data(url: str) -> dict:\n    return {"data": "example"}\n'
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature.name == "fetch_data"
        assert "async" in signature.modifiers

    @staticmethod
    def test_extract_docstring(extractor):
        """Test extracting docstring."""
        code = """
def calculate(x: int, y: int) -> int:
    ""\"Calculate the sum of two numbers.

    Args:
        x: First number
        y: Second number

    Returns:
        The sum of x and y
    ""\"
    return x + y
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        docstring = extractor.extract_docstring(func_node, code.encode())
        assert docstring is not None
        assert "Calculate the sum of two numbers" in docstring
        assert "Args:" in docstring
        assert "Returns:" in docstring

    @staticmethod
    def test_extract_dependencies(extractor):
        """Test extracting dependencies."""
        code = """
def process_data(data: List[str]) -> Dict[str, int]:
    result = defaultdict(int)
    for item in data:
        cleaned = clean_text(item)
        result[cleaned] += 1
    return dict(result)
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        dependencies = extractor.extract_dependencies(func_node, code.encode())
        assert "List" in dependencies
        assert "Dict" in dependencies
        assert "defaultdict" in dependencies
        assert "clean_text" in dependencies
        assert "result" not in dependencies
        assert "item" not in dependencies
        assert "cleaned" not in dependencies

    @staticmethod
    def test_cyclomatic_complexity_simple(analyzer):
        """Test cyclomatic complexity for simple function."""
        code = "\ndef simple():\n    return 42\n"
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        complexity = analyzer.calculate_cyclomatic_complexity(func_node)
        assert complexity == 1

    @staticmethod
    def test_cyclomatic_complexity_with_conditions(analyzer):
        """Test cyclomatic complexity with conditions."""
        code = """
def check_value(x):
    if x > 0:
        if x > 10:
            return "large"
        else:
            return "small"
    elif x < 0:
        return "negative"
    else:
        return "zero\"
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        complexity = analyzer.calculate_cyclomatic_complexity(func_node)
        assert complexity == 4

    @staticmethod
    def test_cognitive_complexity(analyzer):
        """Test cognitive complexity calculation."""
        code = """
def complex_logic(items):
    total = 0
    for item in items:  # +1
        if item > 0:    # +2 (1 + 1 for nesting)
            if item % 2 == 0:  # +3 (1 + 2 for nesting)
                total += item
            else:
                total -= item
    return total
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        complexity = analyzer.calculate_cognitive_complexity(func_node)
        assert complexity >= 6

    @staticmethod
    def test_nesting_depth(analyzer):
        """Test nesting depth calculation."""
        code = """
def nested_function():
    if True:
        for i in range(10):
            while i > 0:
                if i % 2 == 0:
                    pass
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        depth = analyzer.calculate_nesting_depth(func_node)
        assert depth == 4

    @staticmethod
    def test_logical_lines_count(analyzer):
        """Test counting logical lines."""
        code = """
def example():
    # This is a comment
    x = 1  # inline comment

    ""\"
    This is a docstring
    spanning multiple lines
    ""\"

    y = 2
    return x + y
"""
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        lines = analyzer.count_logical_lines(func_node, code.encode())
        assert lines >= 3


class TestJavaScriptMetadataExtraction:
    """Test JavaScript-specific metadata extraction."""

    @classmethod
    @pytest.fixture()
    def extractor(cls):
        return JavaScriptMetadataExtractor()

    @classmethod
    @pytest.fixture()
    def analyzer(cls):
        return JavaScriptComplexityAnalyzer()

    @staticmethod
    def test_extract_function_declaration(extractor):
        """Test extracting function declaration."""
        code = """
function greet(name, age = 18) {
    return `Hello ${name}, you are ${age}`;
}
"""
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature.name == "greet"
        assert len(signature.parameters) == 2
        assert signature.parameters[0]["name"] == "name"
        assert signature.parameters[1]["name"] == "age"
        assert signature.parameters[1]["default"] == "18"

    @staticmethod
    def test_extract_arrow_function(extractor):
        """Test extracting arrow function."""
        code = "\nconst multiply = (a, b) => a * b;\n"
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        arrow_func = None

        def find_arrow_func(node):
            nonlocal arrow_func
            if node.type == "arrow_function":
                arrow_func = node
                return
            for child in node.children:
                find_arrow_func(child)

        find_arrow_func(tree.root_node)
        assert arrow_func is not None, "Arrow function not found in AST"
        signature = extractor.extract_signature(arrow_func, code.encode())
        assert signature.name == "<anonymous>"
        assert len(signature.parameters) == 2

    @staticmethod
    def test_extract_async_function(extractor):
        """Test extracting async function."""
        code = "\nasync function fetchData(url) {\n    return await fetch(url);\n}\n"
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature.name == "fetchData"
        assert "async" in signature.modifiers

    @staticmethod
    def test_extract_generator_function(extractor):
        """Test extracting generator function."""
        code = """
function* fibonacci() {
    let a = 0, b = 1;
    while (true) {
        yield a;
        [a, b] = [b, a + b];
    }
}
"""
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature.name == "fibonacci"
        assert "generator" in signature.modifiers

    @staticmethod
    def test_extract_jsdoc(extractor):
        """Test extracting JSDoc comments."""
        code = """
/**
 * Calculates the area of a rectangle.
 * @param {number} width - The width of the rectangle
 * @param {number} height - The height of the rectangle
 * @returns {number} The area of the rectangle
 */
function calculateArea(width, height) {
    return width * height;
}
"""
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[1]
        docstring = extractor.extract_docstring(func_node, code.encode())
        assert docstring is not None
        assert "Calculates the area of a rectangle" in docstring

    @staticmethod
    def test_javascript_complexity(analyzer):
        """Test JavaScript complexity analysis."""
        code = """
function processItems(items) {
    let result = [];
    for (let item of items) {
        if (item && item.active) {
            try {
                result.push(transform(item));
            } catch (e) {
                console.error(e);
            }
        }
    }
    return result;
}
"""
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        cyclomatic = analyzer.calculate_cyclomatic_complexity(func_node)
        assert cyclomatic >= 4
        cognitive = analyzer.calculate_cognitive_complexity(func_node)
        assert cognitive >= 5


class TestTypeScriptMetadataExtraction:
    """Test TypeScript-specific metadata extraction."""

    @classmethod
    @pytest.fixture()
    def extractor(cls):
        return TypeScriptMetadataExtractor()

    @staticmethod
    @pytest.mark.skip(reason="TypeScript grammar not available in test environment")
    def test_extract_typed_function(extractor):
        """Test extracting TypeScript function with types."""
        code = "\nfunction add(a: number, b: number): number {\n    return a + b;\n}\n"
        parser = get_parser("typescript")
        tree = parser.parse(code.encode())
        func_node = tree.root_node.children[0]
        signature = extractor.extract_signature(func_node, code.encode())
        assert signature.name == "add"
        assert len(signature.parameters) == 2
        assert signature.parameters[0]["name"] == "a"
        assert signature.parameters[0]["type"] == "number"
        assert signature.parameters[1]["name"] == "b"
        assert signature.parameters[1]["type"] == "number"
        assert signature.return_type == "number"

    @staticmethod
    @pytest.mark.skip(reason="TypeScript grammar not available in test environment")
    def test_extract_interface_method(extractor):
        """Test extracting interface method signature."""
        code = """
interface Calculator {
    add(a: number, b: number): number;
    subtract(a: number, b: number): number;
}
"""
        parser = get_parser("typescript")
        tree = parser.parse(code.encode())
        interface_node = tree.root_node.children[0]
        method_nodes = [
            child
            for child in interface_node.children
            if child.type == "method_signature"
        ]
        if method_nodes:
            signature = extractor.extract_signature(method_nodes[0], code.encode())
            assert signature is not None
            assert "interface_method" in signature.modifiers


class TestIntegrationWithChunker:
    """Test metadata extraction integration with chunker."""

    @staticmethod
    def test_chunk_with_metadata_python():
        """Test chunking Python code with metadata extraction."""
        code = """
def factorial(n: int) -> int:
    ""\"Calculate factorial of n.""\"
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
"""
        chunks = chunk_text(code, "python", extract_metadata=True)
        factorial_chunk = next(
            c for c in chunks if c.node_type == "function_definition"
        )
        assert factorial_chunk.metadata is not None
        assert factorial_chunk.metadata["signature"]["name"] == "factorial"
        assert factorial_chunk.metadata["docstring"] == "Calculate factorial of n."
        assert factorial_chunk.metadata["complexity"]["cyclomatic"] == 2
        deps = factorial_chunk.metadata.get("dependencies", [])
        assert "factorial" in deps or len(deps) == 0
        add_chunk = next(
            (c for c in chunks if c.node_type == "method_definition"),
            None,
        )
        if add_chunk:
            assert add_chunk.metadata is not None
            assert add_chunk.metadata["signature"]["name"] == "add"
            assert add_chunk.metadata["signature"]["parameters"][0]["name"] == "self"
        else:
            assert any(c.node_type == "class_definition" for c in chunks)

    @staticmethod
    def test_chunk_without_metadata():
        """Test chunking without metadata extraction."""
        code = "\ndef simple():\n    return 42\n"
        chunks = chunk_text(code, "python", extract_metadata=False)
        assert len(chunks) == 1
        assert chunks[0].metadata == {}

    @staticmethod
    def test_chunk_with_metadata_javascript():
        """Test chunking JavaScript code with metadata."""
        code = """
/**
 * Greet a person
 * @param {string} name - Person's name
 */
function greet(name) {
    console.log(`Hello, ${name}!`);
}

const utils = {
    async fetchData(url) {
        const response = await fetch(url);
        return response.json();
    }
};
"""
        chunks = chunk_text(code, "javascript", extract_metadata=True)
        greet_chunk = next(
            (c for c in chunks if c.node_type == "function_declaration"),
            None,
        )
        assert greet_chunk is not None, "Expected function_declaration chunk not found"
        assert greet_chunk.metadata is not None
        assert greet_chunk.metadata["signature"]["name"] == "greet"
        assert "Greet a person" in greet_chunk.metadata["docstring"]
        deps = greet_chunk.metadata.get("dependencies", [])
        assert isinstance(deps, list)
        fetch_chunk = next(
            (c for c in chunks if c.node_type == "method_definition"),
            None,
        )
        assert fetch_chunk is not None, "Expected method_definition chunk not found"
        assert "async" in fetch_chunk.metadata["signature"]["modifiers"]
        deps = fetch_chunk.metadata.get("dependencies", [])
        assert isinstance(deps, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Test integration of language configurations with the chunker."""

import importlib

import chunker.languages.python
from chunker.chunker import chunk_file
from chunker.languages import LanguageConfig, language_config_registry


class TestLanguageIntegration:
    """Test that language configurations integrate properly with chunking."""

    def setup_method(self):
        """Ensure Python config is registered for each test."""
        # Clear and re-import to ensure clean state
        language_config_registry.clear()

        # Force re-import of python config

        importlib.reload(chunker.languages.python)

    def test_python_config_registered(self):
        """Test that Python configuration is automatically registered."""
        config = language_config_registry.get("python")
        assert config is not None
        assert config.language_id == "python"

        # Check aliases work
        assert language_config_registry.get("py") == config
        assert language_config_registry.get("python3") == config

    def test_python_chunking_with_config(self, tmp_path):
        """Test that Python chunking uses the configuration."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def regular_function():
    pass

async def async_function():
    pass

class MyClass:
    def method(self):
        pass

@decorator
def decorated_function():
    pass

# This is a comment
lambda x: x + 1
""",
        )

        chunks = chunk_file(test_file, "python")

        # Verify chunks are found according to config
        chunk_types = {chunk.node_type for chunk in chunks}
        expected_types = {
            "function_definition",  # regular_function, async_function, method
            "class_definition",  # MyClass
            "decorated_definition",  # decorated_function
        }

        # Check that we got at least the expected types
        assert expected_types.issubset(chunk_types)

        # Lambda should also be included due to our ChunkRule
        assert "lambda" in chunk_types

        # Verify we got the right number of chunks
        # Should have: regular_function, async_function, MyClass, method, decorated_function, lambda
        assert len(chunks) >= 5

    def test_chunking_without_config(self, tmp_path):
        """Test that chunking falls back to defaults for unconfigured languages."""
        # Use a language that doesn't have a configuration
        test_file = tmp_path / "test.js"
        test_file.write_text(
            """
function myFunction() {
    return 42;
}

class MyClass {
    method() {
        return true;
    }
}
""",
        )

        # Should still work with fallback defaults
        chunks = chunk_file(test_file, "javascript")
        assert len(chunks) > 0

    def test_custom_language_config(self, tmp_path):
        """Test registering and using a custom language configuration."""

        class CustomJSConfig(LanguageConfig):
            @property
            def language_id(self) -> str:
                return "javascript"

            @property
            def chunk_types(self) -> set[str]:
                return {
                    "function_declaration",
                    "class_declaration",
                    "method_definition",
                    "arrow_function",
                }

        # Register the custom config
        language_config_registry.register(CustomJSConfig())

        test_file = tmp_path / "test.js"
        test_file.write_text(
            """
function normalFunction() {
    return 1;
}

const arrowFunc = () => {
    return 2;
};

class TestClass {
    testMethod() {
        return 3;
    }
}
""",
        )

        chunks = chunk_file(test_file, "javascript")
        chunk_types = {chunk.node_type for chunk in chunks}

        # Verify our custom config is being used
        assert "function_declaration" in chunk_types or "arrow_function" in chunk_types
        assert len(chunks) >= 2  # At least function and class

        # Clean up
        language_config_registry.clear()
        # Re-register Python config for other tests

        importlib.reload(chunker.languages.python)

    def test_ignore_types_work(self, tmp_path):
        """Test that ignore types in config are respected."""

        # Save original Python config
        original_config = language_config_registry.get("python")

        class TestConfigAllNodes(LanguageConfig):
            """Config that chunks all major node types."""

            @property
            def language_id(self) -> str:
                return "python"

            @property
            def chunk_types(self) -> set[str]:
                # Include many node types to see the effect of ignoring
                return {
                    "function_definition",
                    "class_definition",
                    "if_statement",
                    "for_statement",
                    "assignment",
                }

        # Test file with various constructs
        test_file = tmp_path / "test_ignore.py"
        test_file.write_text(
            """
def my_function():
    x = 42
    if x > 0:
        for i in range(x):
            print(i)
    return x

class MyClass:
    pass
""",
        )

        # First test: chunk everything
        language_config_registry.clear()
        language_config_registry.register(TestConfigAllNodes())

        chunks = chunk_file(test_file, "python")
        chunk_types_all = {c.node_type for c in chunks}

        # Should have multiple chunk types
        assert "function_definition" in chunk_types_all
        assert "class_definition" in chunk_types_all
        # May or may not have these depending on tree-sitter's exact node names
        assert len(chunks) >= 2  # At least function and class

        # Second test: ignore certain types
        class TestConfigWithIgnores(LanguageConfig):
            """Config that ignores certain node types."""

            @property
            def language_id(self) -> str:
                return "python"

            @property
            def chunk_types(self) -> set[str]:
                # Only chunk functions and classes
                return {
                    "function_definition",
                    "class_definition",
                }

            def __init__(self):
                super().__init__()
                # Ignore these types during traversal
                self.add_ignore_type("if_statement")
                self.add_ignore_type("for_statement")
                self.add_ignore_type("assignment")

        language_config_registry.clear()
        language_config_registry.register(TestConfigWithIgnores())

        chunks_filtered = chunk_file(test_file, "python")
        chunk_types_filtered = {c.node_type for c in chunks_filtered}

        # Should still have function and class but not the ignored types
        assert "function_definition" in chunk_types_filtered
        assert "class_definition" in chunk_types_filtered
        assert "if_statement" not in chunk_types_filtered
        assert "for_statement" not in chunk_types_filtered
        assert "assignment" not in chunk_types_filtered

        # Restore original config
        language_config_registry.clear()
        if original_config:
            language_config_registry.register(
                original_config,
                aliases=["py", "python3"],
            )
        else:
            # Re-register default Python config

            importlib.reload(chunker.languages.python)


class TestChunkerIntegration:
    """Test advanced chunker integration scenarios."""

    def test_nested_chunk_parent_context(self, tmp_path):
        """Test that parent context is properly propagated in nested chunks."""
        test_file = tmp_path / "nested.py"
        test_file.write_text(
            """
class OuterClass:
    def outer_method(self):
        def inner_function():
            def deeply_nested():
                pass
            return deeply_nested

        class InnerClass:
            def inner_method(self):
                pass

def top_level_function():
    def nested_function():
        pass
""",
        )

        chunks = chunk_file(test_file, "python")

        # Debug: print what we got
        # for chunk in chunks:
        #     print(f"Node: {chunk.node_type}, Parent: '{chunk.parent_context}', Content preview: {chunk.content.strip()[:40]}")

        # Verify parent contexts are correct
        for chunk in chunks:
            if chunk.node_type == "class_definition" and "OuterClass" in chunk.content:
                # Top-level class has no parent
                assert chunk.parent_context == ""
            elif (
                chunk.node_type == "function_definition"
                and "outer_method" in chunk.content
            ):
                # Method inside OuterClass
                assert chunk.parent_context == "class_definition"
            elif (
                chunk.node_type == "function_definition"
                and "inner_function" in chunk.content
                and "deeply_nested" not in chunk.content
            ):
                # Function inside outer_method
                assert chunk.parent_context == "function_definition"
            elif (
                chunk.node_type == "function_definition"
                and "deeply_nested" in chunk.content
            ):
                # Function inside inner_function
                assert chunk.parent_context == "function_definition"
            elif (
                chunk.node_type == "class_definition" and "InnerClass" in chunk.content
            ):
                # Class inside outer_method
                assert chunk.parent_context == "function_definition"
            elif (
                chunk.node_type == "function_definition"
                and "inner_method" in chunk.content
            ):
                # Method inside InnerClass
                assert chunk.parent_context == "class_definition"
            elif (
                chunk.node_type == "function_definition"
                and "top_level_function():" in chunk.content
            ):
                # Top-level function
                assert chunk.parent_context == ""
            elif (
                chunk.node_type == "function_definition"
                and "nested_function():" in chunk.content
            ):
                # Function inside top_level_function
                assert chunk.parent_context == "function_definition"

    def test_config_none_vs_defaults(self, tmp_path):
        """Test chunking behavior with no config vs default fallback."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def function_test():
    pass

class ClassTest:
    def method_test(self):
        pass

lambda x: x + 1
""",
        )

        # First, test with no config (should use defaults)
        original_config = language_config_registry.get("python")
        language_config_registry.clear()

        chunks_no_config = chunk_file(test_file, "python")
        chunk_types_no_config = {c.node_type for c in chunks_no_config}

        # Should only have the default types
        assert "function_definition" in chunk_types_no_config
        assert "class_definition" in chunk_types_no_config
        # Note: Python tree-sitter uses "function_definition" for methods too
        assert "lambda" not in chunk_types_no_config  # Not in defaults

        # Now test with Python config
        if original_config:
            language_config_registry.register(
                original_config,
                aliases=["py", "python3"],
            )
        else:

            importlib.reload(chunker.languages.python)

        chunks_with_config = chunk_file(test_file, "python")
        chunk_types_with_config = {c.node_type for c in chunks_with_config}

        # Should have lambda due to ChunkRule
        assert "lambda" in chunk_types_with_config

    def test_deep_recursion(self, tmp_path):
        """Test handling of deeply nested code structures."""
        # Generate deeply nested code
        code_lines = []
        indent = ""
        for i in range(50):  # 50 levels deep
            code_lines.append(f"{indent}def level_{i}():")
            indent += "    "
            if i == 49:  # Last level
                code_lines.append(f"{indent}return 42")

        test_file = tmp_path / "deep_nested.py"
        test_file.write_text("\n".join(code_lines))

        # Should not crash with stack overflow
        chunks = chunk_file(test_file, "python")

        # Should have 50 function chunks
        assert len(chunks) == 50

        # Verify nesting via parent context
        for i, chunk in enumerate(chunks):
            if i == 0:
                assert chunk.parent_context == ""
            else:
                assert chunk.parent_context == "function_definition"

    def test_error_handling_malformed_code(self, tmp_path):
        """Test chunker handles malformed/incomplete code gracefully."""
        test_file = tmp_path / "malformed.py"
        test_file.write_text(
            """
def valid_function():
    pass

# Incomplete function
def incomplete_function(

class IncompleteClass:
    def method(self):
        # Missing closing

# Random syntax error
if True
    print("missing colon")

# Valid function after errors
def another_valid():
    return True
""",
        )

        # Should not crash - tree-sitter is resilient to syntax errors
        chunks = chunk_file(test_file, "python")

        # Should still find valid chunks
        chunk_contents = [c.content for c in chunks]
        assert any("valid_function" in c for c in chunk_contents)
        # Tree-sitter may or may not parse the function after syntax errors
        # depending on recovery strategy - just check we got some chunks
        assert len(chunks) >= 1

        # May or may not find incomplete ones depending on parser recovery
        # Just verify it doesn't crash
        assert isinstance(chunks, list)

    def test_unicode_content(self, tmp_path):
        """Test handling of Unicode content in code."""
        test_file = tmp_path / "unicode_test.py"
        test_file.write_text(
            """
def hello_世界():
    '''Function with unicode name'''
    emoji = "🐍🔥✨"
    return f"Hello {emoji}"

class 数学类:
    '''Class with Chinese name'''
    def calculate_π(self):
        return 3.14159

# Comment with emojis 🎉🎊
def process_données(données):  # French parameter names
    résultat = len(données)
    return résultat
""",
            encoding="utf-8",
        )

        chunks = chunk_file(test_file, "python")

        # Verify chunks are found
        assert len(chunks) >= 3

        # Verify Unicode content is preserved
        chunk_contents = [c.content for c in chunks]
        assert any("hello_世界" in c for c in chunk_contents)
        assert any("数学类" in c for c in chunk_contents)
        assert any("process_données" in c for c in chunk_contents)

        # Verify content decodes properly
        for chunk in chunks:
            assert isinstance(chunk.content, str)
            # Should not raise UnicodeDecodeError
            _ = chunk.content.encode("utf-8")


class TestPythonConfigSpecific:
    """Test Python-specific language configuration features."""

    def setup_method(self):
        """Ensure Python config is registered for each test."""
        # Clear and re-import to ensure clean state
        language_config_registry.clear()

        # Force re-import of python config

        importlib.reload(chunker.languages.python)

    def test_lambda_chunking(self, tmp_path):
        """Test that lambda functions are chunked according to the ChunkRule."""
        test_file = tmp_path / "lambdas.py"
        test_file.write_text(
            """
# Simple lambdas
simple = lambda x: x + 1
double = lambda x: x * 2

# Lambda in function
def use_lambdas():
    filtered = filter(lambda x: x > 0, [1, -2, 3, -4])
    mapped = map(lambda x: x ** 2, [1, 2, 3])

# Lambda in comprehension
squared = [(lambda x: x * x)(i) for i in range(5)]

# Multi-line lambda
complex_lambda = lambda x, y: (
    x + y if x > 0
    else x - y
)
""",
        )

        chunks = chunk_file(test_file, "python")

        # Filter to just lambda chunks
        lambda_chunks = [c for c in chunks if c.node_type == "lambda"]

        # Should find multiple lambdas
        assert len(lambda_chunks) >= 4  # At least the top-level ones

        # Verify lambda content is captured
        lambda_contents = [c.content for c in lambda_chunks]
        assert any("x + 1" in content for content in lambda_contents)
        assert any("x * 2" in content for content in lambda_contents)
        assert any("x > 0" in content for content in lambda_contents)

    def test_file_extensions_recognition(self):
        """Test that PythonConfig recognizes correct file extensions."""
        # Get the registered config instead of creating a new one
        config = language_config_registry.get("python")
        assert config is not None

        # Check standard extensions
        assert ".py" in config.file_extensions
        assert ".pyw" in config.file_extensions  # Windows Python files
        assert ".pyi" in config.file_extensions  # Type stub files

        # Should not have non-Python extensions
        assert ".js" not in config.file_extensions
        assert ".txt" not in config.file_extensions

    def test_string_and_comment_ignoring(self, tmp_path):
        """Test that string nodes themselves can be ignored."""

        # Create a custom config that chunks string nodes
        class StringChunkConfig(LanguageConfig):
            @property
            def language_id(self) -> str:
                return "python"

            @property
            def chunk_types(self) -> set[str]:
                return {"function_definition", "class_definition", "string"}

        # First test - with strings as chunks
        original_config = language_config_registry.get("python")
        language_config_registry.clear()
        language_config_registry.register(StringChunkConfig())

        test_file = tmp_path / "test_strings.py"
        test_file.write_text(
            '''
def my_function():
    """This is a docstring"""
    text = "This is a string literal"
    return text
''',
        )

        chunks_with_strings = chunk_file(test_file, "python")
        chunk_types = {c.node_type for c in chunks_with_strings}

        # Should have string chunks
        assert "string" in chunk_types
        string_chunks = [c for c in chunks_with_strings if c.node_type == "string"]
        assert len(string_chunks) >= 2  # docstring and literal

        # Now test with Python config that ignores strings
        language_config_registry.clear()
        if original_config:
            language_config_registry.register(
                original_config,
                aliases=["py", "python3"],
            )
        else:

            importlib.reload(chunker.languages.python)

        chunks_no_strings = chunk_file(test_file, "python")
        chunk_types_no_strings = {c.node_type for c in chunks_no_strings}

        # Should NOT have string chunks (they're ignored)
        assert "string" not in chunk_types_no_strings
        # But should still have the function
        assert "function_definition" in chunk_types_no_strings

    def test_decorated_definition_chunking(self, tmp_path):
        """Test that decorated definitions are properly chunked."""
        test_file = tmp_path / "decorators.py"
        test_file.write_text(
            """
# Simple decorator
@decorator
def decorated_function():
    pass

# Multiple decorators
@decorator1
@decorator2
@decorator3
def multi_decorated():
    pass

# Decorated with arguments
@decorator_with_args(arg1, arg2)
@another_decorator(key="value")
def complex_decorated():
    pass

# Decorated class
@dataclass
class DecoratedClass:
    field1: str
    field2: int

    def method(self):
        pass

# Nested decorators
class Container:
    @property
    def prop(self):
        return self._value

    @staticmethod
    def static_method():
        pass
""",
        )

        chunks = chunk_file(test_file, "python")

        # Find decorated definitions
        decorated_chunks = [c for c in chunks if c.node_type == "decorated_definition"]

        # Should find the decorated functions and class
        assert len(decorated_chunks) >= 4  # 3 functions + 1 class

        # Verify decorator content is included
        decorated_contents = [c.content for c in decorated_chunks]
        assert any(
            "@decorator" in c and "decorated_function" in c for c in decorated_contents
        )
        assert any(
            "@decorator1" in c and "@decorator2" in c for c in decorated_contents
        )
        assert any(
            "@dataclass" in c and "DecoratedClass" in c for c in decorated_contents
        )

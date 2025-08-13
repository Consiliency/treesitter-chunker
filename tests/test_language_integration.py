"""Test integration of language configurations with the chunker."""

import importlib

import chunker.languages.python
from chunker.core import chunk_file
from chunker.languages import LanguageConfig, language_config_registry


class TestLanguageIntegration:
    """Test that language configurations integrate properly with chunking."""

    @staticmethod
    def setup_method():
        """Ensure Python config is registered for each test."""
        language_config_registry.clear()
        importlib.reload(chunker.languages.python)

    @staticmethod
    def test_python_config_registered():
        """Test that Python configuration is automatically registered."""
        config = language_config_registry.get("python")
        assert config is not None
        assert config.language_id == "python"
        assert language_config_registry.get("py") == config
        assert language_config_registry.get("python3") == config

    @staticmethod
    def test_python_chunking_with_config(tmp_path):
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
        chunk_types = {chunk.node_type for chunk in chunks}
        expected_types = {
            "function_definition",
            "class_definition",
            "decorated_definition",
        }
        assert expected_types.issubset(chunk_types)
        assert "lambda" in chunk_types
        assert len(chunks) >= 5

    @staticmethod
    def test_chunking_without_config(tmp_path):
        """Test that chunking falls back to defaults for unconfigured languages."""
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
        chunks = chunk_file(test_file, "javascript")
        assert len(chunks) > 0

    @classmethod
    def test_custom_language_config(cls, tmp_path):
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
        assert "function_declaration" in chunk_types or "arrow_function" in chunk_types
        assert len(chunks) >= 2
        language_config_registry.clear()
        importlib.reload(chunker.languages.python)

    @staticmethod
    def test_ignore_types_work(tmp_path):
        """Test that ignore types in config are respected."""
        original_config = language_config_registry.get("python")

        class TestConfigAllNodes(LanguageConfig):
            """Config that chunks all major node types."""

            @property
            def language_id(self) -> str:
                return "python"

            @property
            def chunk_types(self) -> set[str]:
                return {
                    "function_definition",
                    "class_definition",
                    "if_statement",
                    "for_statement",
                    "assignment",
                }

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
        language_config_registry.clear()
        language_config_registry.register(TestConfigAllNodes())
        chunks = chunk_file(test_file, "python")
        chunk_types_all = {c.node_type for c in chunks}
        assert "function_definition" in chunk_types_all
        assert "class_definition" in chunk_types_all
        assert len(chunks) >= 2

        class TestConfigWithIgnores(LanguageConfig):
            """Config that ignores certain node types."""

            @property
            def language_id(self) -> str:
                return "python"

            @property
            def chunk_types(self) -> set[str]:
                return {"function_definition", "class_definition"}

            def __init__(self):
                super().__init__()
                self.add_ignore_type("if_statement")
                self.add_ignore_type("for_statement")
                self.add_ignore_type("assignment")

        language_config_registry.clear()
        language_config_registry.register(TestConfigWithIgnores())
        chunks_filtered = chunk_file(test_file, "python")
        chunk_types_filtered = {c.node_type for c in chunks_filtered}
        assert "function_definition" in chunk_types_filtered
        assert "class_definition" in chunk_types_filtered
        assert "if_statement" not in chunk_types_filtered
        assert "for_statement" not in chunk_types_filtered
        assert "assignment" not in chunk_types_filtered
        language_config_registry.clear()
        if original_config:
            language_config_registry.register(
                original_config,
                aliases=["py", "python3"],
            )
        else:
            importlib.reload(chunker.languages.python)


class TestChunkerIntegration:
    """Test advanced chunker integration scenarios."""

    @staticmethod
    def test_nested_chunk_parent_context(tmp_path):
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
        for chunk in chunks:
            if chunk.node_type == "class_definition" and "OuterClass" in chunk.content:
                assert not chunk.parent_context
            elif (
                chunk.node_type == "function_definition"
                and "outer_method" in chunk.content
            ):
                assert chunk.parent_context == "class_definition"
            elif (
                (
                    chunk.node_type == "function_definition"
                    and "inner_function" in chunk.content
                    and "deeply_nested" not in chunk.content
                )
                or (
                    chunk.node_type == "function_definition"
                    and "deeply_nested" in chunk.content
                )
                or (
                    chunk.node_type == "class_definition"
                    and "InnerClass" in chunk.content
                )
            ):
                assert chunk.parent_context == "function_definition"
            elif (
                chunk.node_type == "function_definition"
                and "inner_method" in chunk.content
            ):
                assert chunk.parent_context == "class_definition"
            elif (
                chunk.node_type == "function_definition"
                and "top_level_function():" in chunk.content
            ):
                assert not chunk.parent_context
            elif (
                chunk.node_type == "function_definition"
                and "nested_function():" in chunk.content
            ):
                assert chunk.parent_context == "function_definition"

    @staticmethod
    def test_config_none_vs_defaults(tmp_path):
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
        original_config = language_config_registry.get("python")

        # Test with no config by temporarily disabling lazy loading
        original_lazy_loading = language_config_registry._enable_lazy_loading
        language_config_registry._enable_lazy_loading = False
        language_config_registry.clear()
        chunks_no_config = chunk_file(test_file, "python")
        chunk_types_no_config = {c.node_type for c in chunks_no_config}
        assert "function_definition" in chunk_types_no_config
        assert "class_definition" in chunk_types_no_config
        assert "lambda" not in chunk_types_no_config

        # Restore lazy loading and test with config
        language_config_registry._enable_lazy_loading = original_lazy_loading
        if original_config:
            language_config_registry.register(
                original_config,
                aliases=["py", "python3"],
            )
        else:
            importlib.reload(chunker.languages.python)
        chunks_with_config = chunk_file(test_file, "python")
        chunk_types_with_config = {c.node_type for c in chunks_with_config}
        assert "lambda" in chunk_types_with_config

    @staticmethod
    def test_deep_recursion(tmp_path):
        """Test handling of deeply nested code structures."""
        code_lines = []
        indent = ""
        for i in range(50):
            code_lines.append(f"{indent}def level_{i}():")
            indent += "    "
            if i == 49:
                code_lines.append(f"{indent}return 42")
        test_file = tmp_path / "deep_nested.py"
        test_file.write_text("\n".join(code_lines))
        chunks = chunk_file(test_file, "python")
        assert len(chunks) == 50
        for i, chunk in enumerate(chunks):
            if i == 0:
                assert not chunk.parent_context
            else:
                assert chunk.parent_context == "function_definition"

    @staticmethod
    def test_error_handling_malformed_code(tmp_path):
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
        chunks = chunk_file(test_file, "python")
        chunk_contents = [c.content for c in chunks]
        assert any("valid_function" in c for c in chunk_contents)
        assert len(chunks) >= 1
        assert isinstance(chunks, list)

    @staticmethod
    def test_unicode_content(tmp_path):
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
        assert len(chunks) >= 3
        chunk_contents = [c.content for c in chunks]
        assert any("hello_世界" in c for c in chunk_contents)
        assert any("数学类" in c for c in chunk_contents)
        assert any("process_données" in c for c in chunk_contents)
        for chunk in chunks:
            assert isinstance(chunk.content, str)
            _ = chunk.content.encode("utf-8")


class TestPythonConfigSpecific:
    """Test Python-specific language configuration features."""

    @staticmethod
    def setup_method():
        """Ensure Python config is registered for each test."""
        language_config_registry.clear()
        importlib.reload(chunker.languages.python)

    @staticmethod
    def test_lambda_chunking(tmp_path):
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
        lambda_chunks = [c for c in chunks if c.node_type == "lambda"]
        assert len(lambda_chunks) >= 4
        lambda_contents = [c.content for c in lambda_chunks]
        assert any("x + 1" in content for content in lambda_contents)
        assert any("x * 2" in content for content in lambda_contents)
        assert any("x > 0" in content for content in lambda_contents)

    @staticmethod
    def test_file_extensions_recognition():
        """Test that PythonConfig recognizes correct file extensions."""
        config = language_config_registry.get("python")
        assert config is not None
        assert ".py" in config.file_extensions
        assert ".pyw" in config.file_extensions
        assert ".pyi" in config.file_extensions
        assert ".js" not in config.file_extensions
        assert ".txt" not in config.file_extensions

    @classmethod
    def test_string_and_comment_ignoring(cls, tmp_path):
        """Test that string nodes themselves can be ignored."""

        class StringChunkConfig(LanguageConfig):

            @property
            def language_id(self) -> str:
                return "python"

            @property
            def chunk_types(self) -> set[str]:
                return {"function_definition", "class_definition", "string"}

        original_config = language_config_registry.get("python")
        language_config_registry.clear()
        language_config_registry.register(StringChunkConfig())
        test_file = tmp_path / "test_strings.py"
        test_file.write_text(
            """
def my_function():
    ""\"This is a docstring""\"
    text = "This is a string literal"
    return text
""",
        )
        chunks_with_strings = chunk_file(test_file, "python")
        chunk_types = {c.node_type for c in chunks_with_strings}
        assert "string" in chunk_types
        string_chunks = [c for c in chunks_with_strings if c.node_type == "string"]
        assert len(string_chunks) >= 2
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
        assert "string" not in chunk_types_no_strings
        assert "function_definition" in chunk_types_no_strings

    @staticmethod
    def test_decorated_definition_chunking(tmp_path):
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
        decorated_chunks = [c for c in chunks if c.node_type == "decorated_definition"]
        assert len(decorated_chunks) >= 4
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

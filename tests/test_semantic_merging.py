"""Tests for semantic merging functionality."""

from chunker import CodeChunk
from chunker.semantic import (
    MergeConfig,
    TreeSitterRelationshipAnalyzer,
    TreeSitterSemanticMerger,
)


class TestRelationshipAnalyzer:
    """Test relationship analysis between chunks."""

    @classmethod
    def test_find_getter_setter_pairs_python(cls):
        """Test finding getter/setter pairs in Python code."""
        analyzer = TreeSitterRelationshipAnalyzer()
        getter_chunk = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""def get_name(self):
    return self._name""",
        )
        setter_chunk = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""def set_name(self, name):
    self._name = name""",
        )
        other_chunk = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=18,
            end_line=20,
            byte_start=220,
            byte_end=270,
            parent_context="class_definition:Person",
            content="""def greet(self):
    print(f'Hello, {self._name}')""",
        )
        chunks = [getter_chunk, setter_chunk, other_chunk]
        pairs = analyzer.find_getter_setter_pairs(chunks)
        assert len(pairs) == 1
        assert pairs[0] == (getter_chunk, setter_chunk)

    @classmethod
    def test_find_getter_setter_pairs_java(cls):
        """Test finding getter/setter pairs in Java code."""
        analyzer = TreeSitterRelationshipAnalyzer()
        getter_chunk = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""public String getName() {
    return this.name;
}""",
        )
        setter_chunk = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""public void setName(String name) {
    this.name = name;
}""",
        )
        chunks = [getter_chunk, setter_chunk]
        pairs = analyzer.find_getter_setter_pairs(chunks)
        assert len(pairs) == 1
        assert pairs[0] == (getter_chunk, setter_chunk)

    @classmethod
    def test_find_overloaded_functions(cls):
        """Test finding overloaded functions."""
        analyzer = TreeSitterRelationshipAnalyzer()
        func1 = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Calculator",
            content="""public int add(int a, int b) {
    return a + b;
}""",
        )
        func2 = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Calculator",
            content="""public double add(double a, double b) {
    return a + b;
}""",
        )
        func3 = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=18,
            end_line=20,
            byte_start=220,
            byte_end=270,
            parent_context="class_definition:Calculator",
            content="""public int add(int a, int b, int c) {
    return a + b + c;
}""",
        )
        other_func = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=22,
            end_line=24,
            byte_start=280,
            byte_end=330,
            parent_context="class_definition:Calculator",
            content="""public int subtract(int a, int b) {
    return a - b;
}""",
        )
        chunks = [func1, func2, func3, other_func]
        groups = analyzer.find_overloaded_functions(chunks)
        assert len(groups) == 1
        assert len(groups[0]) == 3
        group_ids = {chunk.chunk_id for chunk in groups[0]}
        expected_ids = {func1.chunk_id, func2.chunk_id, func3.chunk_id}
        assert group_ids == expected_ids

    @classmethod
    def test_calculate_cohesion_score(cls):
        """Test cohesion score calculation."""
        analyzer = TreeSitterRelationshipAnalyzer()
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""def get_name(self):
    return self._name""",
            references=["self", "_name"],
            dependencies=[],
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""def set_name(self, name):
    self._name = name""",
            references=["self", "_name"],
            dependencies=[],
        )
        chunk3 = CodeChunk(
            language="python",
            file_path="/other.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="""def unrelated():
    pass""",
            references=[],
            dependencies=[],
        )
        score1 = analyzer.calculate_cohesion_score(chunk1, chunk2)
        assert score1 > 0.8
        score2 = analyzer.calculate_cohesion_score(chunk1, chunk3)
        assert score2 < 0.3

    @classmethod
    def test_find_interface_implementations(cls):
        """Test finding interface/implementation relationships."""
        analyzer = TreeSitterRelationshipAnalyzer()
        interface_chunk = CodeChunk(
            language="java",
            file_path="/IShape.java",
            node_type="interface_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="""public interface IShape {
    double area();
    double perimeter();
}""",
        )
        implementation_chunk = CodeChunk(
            language="java",
            file_path="/Circle.java",
            node_type="class_definition",
            start_line=1,
            end_line=15,
            byte_start=0,
            byte_end=300,
            parent_context="",
            content="""public class Circle implements IShape {
    private double radius;
    public double area() { return Math.PI * radius * radius; }
    public double perimeter() { return 2 * Math.PI * radius; }
}""",
        )
        chunks = [interface_chunk, implementation_chunk]
        relationships = analyzer.find_interface_implementations(chunks)
        assert interface_chunk.chunk_id in relationships
        assert implementation_chunk.chunk_id in relationships[interface_chunk.chunk_id]


class TestSemanticMerger:
    """Test semantic chunk merging."""

    @classmethod
    def test_should_merge_getter_setter(cls):
        """Test that getter/setter pairs should be merged."""
        config = MergeConfig(merge_getters_setters=True)
        merger = TreeSitterSemanticMerger(config)
        getter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""def get_name(self):
    return self._name""",
        )
        setter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""def set_name(self, name):
    self._name = name""",
        )
        assert merger.should_merge(getter, setter)

    @classmethod
    def test_should_not_merge_different_files(cls):
        """Test that chunks from different files should not merge."""
        merger = TreeSitterSemanticMerger()
        chunk1 = CodeChunk(
            language="python",
            file_path="/test1.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="""def func1():
    pass""",
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test2.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="""def func2():
    pass""",
        )
        assert not merger.should_merge(chunk1, chunk2)

    @classmethod
    def test_should_not_merge_large_chunks(cls):
        """Test that large chunks should not be merged."""
        config = MergeConfig(max_merged_size=10)
        merger = TreeSitterSemanticMerger(config)
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=6,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="""def func1():
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    pass""",
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=8,
            end_line=13,
            byte_start=110,
            byte_end=200,
            parent_context="",
            content="""def func2():
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    pass""",
        )
        assert not merger.should_merge(chunk1, chunk2)

    @classmethod
    def test_merge_chunks_basic(cls):
        """Test basic chunk merging."""
        config = MergeConfig(
            merge_getters_setters=True,
            merge_small_methods=True,
            small_method_threshold=5,
        )
        merger = TreeSitterSemanticMerger(config)
        getter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""def get_name(self):
    return self._name""",
        )
        setter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""def set_name(self, name):
    self._name = name""",
        )
        other = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=20,
            end_line=30,
            byte_start=220,
            byte_end=400,
            parent_context="class_definition:Person",
            content="""def long_method(self):
    # Many lines of code
    pass""",
        )
        chunks = [getter, setter, other]
        merged = merger.merge_chunks(chunks)
        assert len(merged) == 2
        merged_chunk = None
        for chunk in merged:
            if "get_name" in chunk.content and "set_name" in chunk.content:
                merged_chunk = chunk
                break
        assert merged_chunk is not None
        assert merged_chunk.start_line == 10
        assert merged_chunk.end_line == 16
        assert merged_chunk.node_type in {"method_definition", "merged_chunk"}

    @classmethod
    def test_merge_overloaded_functions(cls):
        """Test merging overloaded functions."""
        config = MergeConfig(merge_overloaded_functions=True)
        merger = TreeSitterSemanticMerger(config)
        func1 = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Calculator",
            content="""public int add(int a, int b) {
    return a + b;
}""",
        )
        func2 = CodeChunk(
            language="java",
            file_path="/Test.java",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Calculator",
            content="""public double add(double a, double b) {
    return a + b;
}""",
        )
        chunks = [func1, func2]
        merged = merger.merge_chunks(chunks)
        assert len(merged) == 1
        assert "int add" in merged[0].content
        assert "double add" in merged[0].content

    @classmethod
    def test_get_merge_reason(cls):
        """Test getting merge reasons."""
        merger = TreeSitterSemanticMerger()
        getter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""def get_name(self):
    return self._name""",
        )
        setter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""def set_name(self, name):
    self._name = name""",
        )
        reason = merger.get_merge_reason(getter, setter)
        assert reason is not None
        assert "getter/setter pair" in reason
        assert "cohesion score:" in reason

    @classmethod
    def test_language_specific_merging(cls):
        """Test language-specific merging rules."""
        config = MergeConfig()
        merger = TreeSitterSemanticMerger(config)
        property_getter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=13,
            byte_start=100,
            byte_end=180,
            parent_context="class_definition:Person",
            content="""@property
def name(self):
    return self._name""",
        )
        property_setter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=15,
            end_line=18,
            byte_start=190,
            byte_end=270,
            parent_context="class_definition:Person",
            content="""@name.setter
def name(self, value):
    self._name = value""",
        )
        assert merger.should_merge(property_getter, property_setter)
        handler1 = CodeChunk(
            language="javascript",
            file_path="/test.js",
            node_type="function_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Form",
            content="""onClick(e) {
    e.preventDefault();
}""",
        )
        handler2 = CodeChunk(
            language="javascript",
            file_path="/test.js",
            node_type="function_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Form",
            content="""onSubmit(e) {
    this.submitForm();
}""",
        )
        assert merger.should_merge(handler1, handler2)


class TestMergeConfig:
    """Test merge configuration."""

    @classmethod
    def test_default_config(cls):
        """Test default configuration values."""
        config = MergeConfig()
        assert config.merge_getters_setters is True
        assert config.merge_overloaded_functions is True
        assert config.merge_small_methods is True
        assert config.merge_interface_implementations is False
        assert config.small_method_threshold == 10
        assert config.max_merged_size == 100
        assert config.cohesion_threshold == 0.6

    @classmethod
    def test_custom_config(cls):
        """Test custom configuration."""
        config = MergeConfig(
            merge_getters_setters=False,
            small_method_threshold=20,
            cohesion_threshold=0.8,
        )
        assert config.merge_getters_setters is False
        assert config.small_method_threshold == 20
        assert config.cohesion_threshold == 0.8

    @classmethod
    def test_language_specific_config(cls):
        """Test language-specific configuration."""
        config = MergeConfig()
        assert "python" in config.language_configs
        assert config.language_configs["python"]["merge_decorators"] is True
        assert config.language_configs["python"]["merge_property_methods"] is True
        assert "java" in config.language_configs
        assert config.language_configs["java"]["merge_constructors"] is False
        assert config.language_configs["java"]["merge_overrides"] is True


class TestAdvancedSemanticMerging:
    """Advanced tests for semantic merging edge cases and complex scenarios."""

    @classmethod
    def test_merge_empty_chunks(cls):
        """Test handling of empty chunks."""
        merger = TreeSitterSemanticMerger()
        assert merger.merge_chunks([]) == []
        chunk = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=1,
            byte_start=0,
            byte_end=0,
            parent_context="",
            content="",
        )
        result = merger.merge_chunks([chunk])
        assert len(result) == 1
        assert not result[0].content

    def test_merge_at_size_boundary(self):
        """Test merging when chunks are exactly at size limit."""
        config = MergeConfig(max_merged_size=10)
        merger = TreeSitterSemanticMerger(config)
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="class_definition:Test",
            content="""def get_x(self):
    # Line 2
    # Line 3
    # Line 4
    return self.x""",
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=7,
            end_line=11,
            byte_start=110,
            byte_end=210,
            parent_context="class_definition:Test",
            content="""def set_x(self, x):
    # Line 2
    # Line 3
    # Line 4
    self.x = x""",
        )
        assert merger.should_merge(chunk1, chunk2)
        chunk3 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=13,
            end_line=18,
            byte_start=220,
            byte_end=320,
            parent_context="class_definition:Test",
            content="""def get_y(self):
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    return self.y""",
        )
        assert not merger.should_merge(chunk1, chunk3)

    @classmethod
    def test_complex_merge_groups(cls):
        """Test merging multiple related chunks in complex scenarios."""
        config = MergeConfig(
            merge_getters_setters=True,
            merge_small_methods=True,
            small_method_threshold=5,
        )
        merger = TreeSitterSemanticMerger(config)
        get_x = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Point",
            content="""def get_x(self):
    return self._x""",
        )
        set_x = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Point",
            content="""def set_x(self, x):
    self._x = x""",
        )
        get_y = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=18,
            end_line=20,
            byte_start=220,
            byte_end=270,
            parent_context="class_definition:Point",
            content="""def get_y(self):
    return self._y""",
        )
        set_y = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=22,
            end_line=24,
            byte_start=280,
            byte_end=330,
            parent_context="class_definition:Point",
            content="""def set_y(self, y):
    self._y = y""",
        )
        validate = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=26,
            end_line=28,
            byte_start=340,
            byte_end=390,
            parent_context="class_definition:Point",
            content="""def validate(self):
    return self._x >= 0 and self._y >= 0""",
        )
        chunks = [get_x, set_x, get_y, set_y, validate]
        merged = merger.merge_chunks(chunks)
        assert len(merged) < len(chunks)
        merged_contents = [chunk.content for chunk in merged]
        assert any(
            "get_x" in content and "set_x" in content for content in merged_contents
        )
        assert any(
            "get_y" in content and "set_y" in content for content in merged_contents
        )

    @classmethod
    def test_cohesion_score_edge_cases(cls):
        """Test cohesion score calculation for edge cases."""
        analyzer = TreeSitterRelationshipAnalyzer()
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=30,
            parent_context="",
            content="""def func1():
    pass""",
            references=[],
            dependencies=[],
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=5,
            end_line=7,
            byte_start=40,
            byte_end=70,
            parent_context="",
            content="""def func2():
    pass""",
            references=[],
            dependencies=[],
        )
        score = analyzer.calculate_cohesion_score(chunk1, chunk2)
        assert 0 < score < 0.5
        chunk3 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=15,
            byte_start=100,
            byte_end=200,
            parent_context="class_definition:DataProcessor",
            content="""def process(self):
    # processing logic""",
            references=["self", "data", "config", "logger", "cache"],
            dependencies=["numpy", "pandas"],
        )
        chunk4 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=17,
            end_line=22,
            byte_start=210,
            byte_end=310,
            parent_context="class_definition:DataProcessor",
            content="""def validate(self):
    # validation logic""",
            references=["self", "data", "config", "logger", "validator"],
            dependencies=["numpy", "pandas", "validators"],
        )
        score2 = analyzer.calculate_cohesion_score(chunk3, chunk4)
        assert score2 > 0.7

    @classmethod
    def test_ruby_getter_setter_merging(cls):
        """Test Ruby-specific getter/setter patterns."""
        analyzer = TreeSitterRelationshipAnalyzer()
        getter = CodeChunk(
            language="ruby",
            file_path="/test.rb",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""def name
  @name
end""",
        )
        setter = CodeChunk(
            language="ruby",
            file_path="/test.rb",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""def name=(value)
  @name = value
end""",
        )
        assert analyzer._are_in_same_class(getter, setter)

    @classmethod
    def test_typescript_interface_implementation(cls):
        """Test TypeScript interface and implementation detection."""
        analyzer = TreeSitterRelationshipAnalyzer()
        interface = CodeChunk(
            language="typescript",
            file_path="/types.ts",
            node_type="interface_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="""interface IUserService {
  getUser(id: string): User;
  saveUser(user: User): void;
}""",
        )
        implementation = CodeChunk(
            language="typescript",
            file_path="/services.ts",
            node_type="class_definition",
            start_line=10,
            end_line=20,
            byte_start=200,
            byte_end=400,
            parent_context="",
            content="""class UserService implements IUserService {
  getUser(id: string): User { /* ... */ }
  saveUser(user: User): void { /* ... */ }
}""",
        )
        chunks = [interface, implementation]
        relationships = analyzer.find_interface_implementations(chunks)
        assert interface.chunk_id in relationships
        assert implementation.chunk_id in relationships[interface.chunk_id]

    @classmethod
    def test_merge_with_mixed_languages(cls):
        """Test that chunks with different languages are never merged."""
        merger = TreeSitterSemanticMerger()
        python_chunk = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="""def hello():
    print('Hello')""",
        )
        javascript_chunk = CodeChunk(
            language="javascript",
            file_path="/test.js",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="""function hello() {
    console.log('Hello');
}""",
        )
        assert not merger.should_merge(python_chunk, javascript_chunk)
        result = merger.merge_chunks([python_chunk, javascript_chunk])
        assert len(result) == 2
        assert result[0].language != result[1].language

    @classmethod
    def test_constructor_overloading(cls):
        """Test handling of overloaded constructors."""
        analyzer = TreeSitterRelationshipAnalyzer()
        config = MergeConfig(merge_overloaded_functions=True)
        TreeSitterSemanticMerger(config)
        constructor1 = CodeChunk(
            language="java",
            file_path="/Person.java",
            node_type="constructor",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="""public Person() {
    this.name = "Unknown";
}""",
        )
        constructor2 = CodeChunk(
            language="java",
            file_path="/Person.java",
            node_type="constructor",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Person",
            content="""public Person(String name) {
    this.name = name;
}""",
        )
        constructor3 = CodeChunk(
            language="java",
            file_path="/Person.java",
            node_type="constructor",
            start_line=18,
            end_line=21,
            byte_start=220,
            byte_end=300,
            parent_context="class_definition:Person",
            content="""public Person(String name, int age) {
    this.name = name;
    this.age = age;
}""",
        )
        chunks = [constructor1, constructor2, constructor3]
        groups = analyzer.find_overloaded_functions(chunks)
        assert len(groups) == 1
        assert len(groups[0]) == 3
        java_config = MergeConfig()
        java_config.language_configs["java"]["merge_constructors"] = True
        merger_java = TreeSitterSemanticMerger(java_config)
        merged = merger_java.merge_chunks(chunks)
        assert len(merged) == 1

    @classmethod
    def test_python_decorator_methods(cls):
        """Test Python decorator method merging."""
        config = MergeConfig()
        merger = TreeSitterSemanticMerger(config)
        static_method = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=13,
            byte_start=100,
            byte_end=180,
            parent_context="class_definition:Utils",
            content="""@staticmethod
def validate_email(email):
    return '@' in email""",
        )
        class_method = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=15,
            end_line=18,
            byte_start=190,
            byte_end=270,
            parent_context="class_definition:Utils",
            content="""@classmethod
def from_string(cls, string):
    return cls(string)""",
        )
        assert merger.should_merge(static_method, class_method)

    @classmethod
    def test_large_chunk_groups(cls):
        """Test handling of large groups of related chunks."""
        config = MergeConfig(merge_overloaded_functions=True, max_merged_size=200)
        merger = TreeSitterSemanticMerger(config)
        overloaded_chunks = []
        for i in range(5):
            chunk = CodeChunk(
                language="java",
                file_path="/Calculator.java",
                node_type="method_definition",
                start_line=10 + i * 5,
                end_line=13 + i * 5,
                byte_start=100 + i * 100,
                byte_end=190 + i * 100,
                parent_context="class_definition:Calculator",
                content=f"""public int calculate({', '.join([('int a' + str(j)) for j in range(i + 1)])}) {{
    return sum;
}}""",
            )
            overloaded_chunks.append(chunk)
        unrelated = CodeChunk(
            language="java",
            file_path="/Calculator.java",
            node_type="method_definition",
            start_line=40,
            end_line=43,
            byte_start=600,
            byte_end=690,
            parent_context="class_definition:Calculator",
            content="""public void reset() {
    this.result = 0;
}""",
        )
        all_chunks = [*overloaded_chunks, unrelated]
        merged = merger.merge_chunks(all_chunks)
        assert len(merged) == 2
        merged_chunk = next(c for c in merged if "calculate" in c.content)
        assert merged_chunk.start_line == 10
        assert merged_chunk.end_line == 33

    @classmethod
    def test_recursive_merge_groups(cls):
        """Test that merge groups are built correctly with transitive relationships."""
        config = MergeConfig(
            merge_small_methods=True,
            small_method_threshold=10,
            cohesion_threshold=0.5,
        )
        merger = TreeSitterSemanticMerger(config)
        method_a = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:DataHandler",
            content="""def validate_input(self):
    return True""",
            references=["self", "input_data"],
            dependencies=[],
        )
        method_b = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:DataHandler",
            content="""def clean_input(self):
    return cleaned""",
            references=["self", "input_data", "cleaned"],
            dependencies=[],
        )
        method_c = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=18,
            end_line=20,
            byte_start=220,
            byte_end=270,
            parent_context="class_definition:DataHandler",
            content="""def process_cleaned(self):
    return result""",
            references=["self", "cleaned", "result"],
            dependencies=[],
        )
        chunks = [method_a, method_b, method_c]
        merged = merger.merge_chunks(chunks)
        assert len(merged) == 1
        assert all(
            method in merged[0].content
            for method in ["validate_input", "clean_input", "process_cleaned"]
        )

    @classmethod
    def test_javascript_class_methods(cls):
        """Test JavaScript class method merging patterns."""
        config = MergeConfig(merge_getters_setters=True, merge_small_methods=False)
        merger = TreeSitterSemanticMerger(config)
        constructor = CodeChunk(
            language="javascript",
            file_path="/user.js",
            node_type="method_definition",
            start_line=5,
            end_line=8,
            byte_start=50,
            byte_end=120,
            parent_context="class_definition:User",
            content="""constructor(name) {
    this.name = name;
    this.id = null;
}""",
        )
        getter = CodeChunk(
            language="javascript",
            file_path="/user.js",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=130,
            byte_end=180,
            parent_context="class_definition:User",
            content="""get fullName() {
    return this.name;
}""",
        )
        setter = CodeChunk(
            language="javascript",
            file_path="/user.js",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=190,
            byte_end=250,
            parent_context="class_definition:User",
            content="""set fullName(value) {
    this.name = value;
}""",
        )
        assert merger.should_merge(getter, setter)
        assert not merger.should_merge(constructor, getter)

    @classmethod
    def test_go_method_receiver_patterns(cls):
        """Test Go method patterns with receivers."""
        analyzer = TreeSitterRelationshipAnalyzer()
        method1 = CodeChunk(
            language="go",
            file_path="/user.go",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="type:User",
            content="""func (u *User) GetName() string {
    return u.name
}""",
        )
        method2 = CodeChunk(
            language="go",
            file_path="/user.go",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="type:User",
            content="""func (u *User) SetName(name string) {
    u.name = name
}""",
        )
        pairs = analyzer.find_getter_setter_pairs([method1, method2])
        assert len(pairs) == 1

    @classmethod
    def test_merge_preserves_metadata(cls):
        """Test that merging preserves important metadata."""
        merger = TreeSitterSemanticMerger()
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Calculator",
            content="""def add(self, a, b):
    return a + b""",
            references=["self", "a", "b"],
            dependencies=["math"],
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:Calculator",
            content="""def subtract(self, a, b):
    return a - b""",
            references=["self", "a", "b", "c"],
            dependencies=["math", "numpy"],
        )
        merged_chunks = merger.merge_chunks([chunk1, chunk2])
        assert len(merged_chunks) == 1
        merged = merged_chunks[0]
        assert merged.language == "python"
        assert merged.file_path == "/test.py"
        assert merged.parent_context == "class_definition:Calculator"
        assert "self" in merged.references
        assert "a" in merged.references
        assert "b" in merged.references
        assert "c" in merged.references
        assert "math" in merged.dependencies
        assert "numpy" in merged.dependencies

    @classmethod
    def test_csharp_property_patterns(cls):
        """Test C# property getter/setter patterns."""
        analyzer = TreeSitterRelationshipAnalyzer()
        getter = CodeChunk(
            language="csharp",
            file_path="/User.cs",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:User",
            content="""public string GetName() {
    return _name;
}""",
        )
        setter = CodeChunk(
            language="csharp",
            file_path="/User.cs",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:User",
            content="""public void SetName(string value) {
    _name = value;
}""",
        )
        pairs = analyzer.find_getter_setter_pairs([getter, setter])
        assert len(pairs) == 1
        assert pairs[0] == (getter, setter)

    @classmethod
    def test_performance_caching(cls):
        """Test that merge decisions are cached for performance."""
        merger = TreeSitterSemanticMerger()
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="""def func1():
    pass""",
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=5,
            end_line=7,
            byte_start=60,
            byte_end=110,
            parent_context="",
            content="""def func2():
    pass""",
        )
        result1 = merger.should_merge(chunk1, chunk2)
        result2 = merger.should_merge(chunk1, chunk2)
        merger.should_merge(chunk2, chunk1)
        assert result1 == result2

    @classmethod
    def test_cohesion_score_caps_at_one(cls):
        """Test that cohesion score never exceeds 1.0."""
        analyzer = TreeSitterRelationshipAnalyzer()
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:DataProcessor",
            content="""def get_data(self):
    return self._data""",
            references=["self", "data", "cache", "config", "logger"],
            dependencies=["numpy", "pandas", "sklearn"],
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:DataProcessor",
            content="""def set_data(self, data):
    self._data = data""",
            references=["self", "data", "cache", "config", "logger"],
            dependencies=["numpy", "pandas", "sklearn"],
        )
        score = analyzer.calculate_cohesion_score(chunk1, chunk2)
        assert score <= 1.0
        assert score > 0.9

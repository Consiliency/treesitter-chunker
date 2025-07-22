"""Tests for semantic merging functionality."""

import pytest
from chunker import CodeChunk
from chunker.semantic import (
    TreeSitterRelationshipAnalyzer,
    TreeSitterSemanticMerger,
    MergeConfig
)


class TestRelationshipAnalyzer:
    """Test relationship analysis between chunks."""
    
    def test_find_getter_setter_pairs_python(self):
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
            content="def get_name(self):\n    return self._name"
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
            content="def set_name(self, name):\n    self._name = name"
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
            content="def greet(self):\n    print(f'Hello, {self._name}')"
        )
        
        chunks = [getter_chunk, setter_chunk, other_chunk]
        pairs = analyzer.find_getter_setter_pairs(chunks)
        
        assert len(pairs) == 1
        assert pairs[0] == (getter_chunk, setter_chunk)
    
    def test_find_getter_setter_pairs_java(self):
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
            content="public String getName() {\n    return this.name;\n}"
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
            content="public void setName(String name) {\n    this.name = name;\n}"
        )
        
        chunks = [getter_chunk, setter_chunk]
        pairs = analyzer.find_getter_setter_pairs(chunks)
        
        assert len(pairs) == 1
        assert pairs[0] == (getter_chunk, setter_chunk)
    
    def test_find_overloaded_functions(self):
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
            content="public int add(int a, int b) {\n    return a + b;\n}"
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
            content="public double add(double a, double b) {\n    return a + b;\n}"
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
            content="public int add(int a, int b, int c) {\n    return a + b + c;\n}"
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
            content="public int subtract(int a, int b) {\n    return a - b;\n}"
        )
        
        chunks = [func1, func2, func3, other_func]
        groups = analyzer.find_overloaded_functions(chunks)
        
        assert len(groups) == 1
        assert len(groups[0]) == 3
        # Convert to chunk_ids for comparison since CodeChunk is not hashable
        group_ids = {chunk.chunk_id for chunk in groups[0]}
        expected_ids = {func1.chunk_id, func2.chunk_id, func3.chunk_id}
        assert group_ids == expected_ids
    
    def test_calculate_cohesion_score(self):
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
            content="def get_name(self):\n    return self._name",
            references=["self", "_name"],
            dependencies=[]
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
            content="def set_name(self, name):\n    self._name = name",
            references=["self", "_name"],
            dependencies=[]
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
            content="def unrelated():\n    pass",
            references=[],
            dependencies=[]
        )
        
        # Same file, same class, getter/setter pair - high cohesion
        score1 = analyzer.calculate_cohesion_score(chunk1, chunk2)
        assert score1 > 0.8
        
        # Different file - low cohesion
        score2 = analyzer.calculate_cohesion_score(chunk1, chunk3)
        assert score2 < 0.3
    
    def test_find_interface_implementations(self):
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
            content="public interface IShape {\n    double area();\n    double perimeter();\n}"
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
            content="public class Circle implements IShape {\n    private double radius;\n    public double area() { return Math.PI * radius * radius; }\n    public double perimeter() { return 2 * Math.PI * radius; }\n}"
        )
        
        chunks = [interface_chunk, implementation_chunk]
        relationships = analyzer.find_interface_implementations(chunks)
        
        assert interface_chunk.chunk_id in relationships
        assert implementation_chunk.chunk_id in relationships[interface_chunk.chunk_id]


class TestSemanticMerger:
    """Test semantic chunk merging."""
    
    def test_should_merge_getter_setter(self):
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
            content="def get_name(self):\n    return self._name"
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
            content="def set_name(self, name):\n    self._name = name"
        )
        
        assert merger.should_merge(getter, setter)
    
    def test_should_not_merge_different_files(self):
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
            content="def func1():\n    pass"
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
            content="def func2():\n    pass"
        )
        
        assert not merger.should_merge(chunk1, chunk2)
    
    def test_should_not_merge_large_chunks(self):
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
            content="def func1():\n    # Line 2\n    # Line 3\n    # Line 4\n    # Line 5\n    pass"
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
            content="def func2():\n    # Line 2\n    # Line 3\n    # Line 4\n    # Line 5\n    pass"
        )
        
        assert not merger.should_merge(chunk1, chunk2)
    
    def test_merge_chunks_basic(self):
        """Test basic chunk merging."""
        config = MergeConfig(
            merge_getters_setters=True,
            merge_small_methods=True,
            small_method_threshold=5
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
            content="def get_name(self):\n    return self._name"
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
            content="def set_name(self, name):\n    self._name = name"
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
            content="def long_method(self):\n    # Many lines of code\n    pass"
        )
        
        chunks = [getter, setter, other]
        merged = merger.merge_chunks(chunks)
        
        # Should merge getter and setter, keep other separate
        assert len(merged) == 2
        
        # Find the merged chunk
        merged_chunk = None
        for chunk in merged:
            if "get_name" in chunk.content and "set_name" in chunk.content:
                merged_chunk = chunk
                break
        
        assert merged_chunk is not None
        assert merged_chunk.start_line == 10
        assert merged_chunk.end_line == 16
        assert merged_chunk.node_type in ["method_definition", "merged_chunk"]
    
    def test_merge_overloaded_functions(self):
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
            content="public int add(int a, int b) {\n    return a + b;\n}"
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
            content="public double add(double a, double b) {\n    return a + b;\n}"
        )
        
        chunks = [func1, func2]
        merged = merger.merge_chunks(chunks)
        
        assert len(merged) == 1
        assert "int add" in merged[0].content
        assert "double add" in merged[0].content
    
    def test_get_merge_reason(self):
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
            content="def get_name(self):\n    return self._name"
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
            content="def set_name(self, name):\n    self._name = name"
        )
        
        reason = merger.get_merge_reason(getter, setter)
        assert reason is not None
        assert "getter/setter pair" in reason
        assert "cohesion score:" in reason
    
    def test_language_specific_merging(self):
        """Test language-specific merging rules."""
        config = MergeConfig()
        merger = TreeSitterSemanticMerger(config)
        
        # Python property methods
        property_getter = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=13,
            byte_start=100,
            byte_end=180,
            parent_context="class_definition:Person",
            content="@property\ndef name(self):\n    return self._name"
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
            content="@name.setter\ndef name(self, value):\n    self._name = value"
        )
        
        assert merger.should_merge(property_getter, property_setter)
        
        # JavaScript event handlers
        handler1 = CodeChunk(
            language="javascript",
            file_path="/test.js",
            node_type="function_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Form",
            content="onClick(e) {\n    e.preventDefault();\n}"
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
            content="onSubmit(e) {\n    this.submitForm();\n}"
        )
        
        assert merger.should_merge(handler1, handler2)


class TestMergeConfig:
    """Test merge configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = MergeConfig()
        
        assert config.merge_getters_setters is True
        assert config.merge_overloaded_functions is True
        assert config.merge_small_methods is True
        assert config.merge_interface_implementations is False
        assert config.small_method_threshold == 10
        assert config.max_merged_size == 100
        assert config.cohesion_threshold == 0.6
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = MergeConfig(
            merge_getters_setters=False,
            small_method_threshold=20,
            cohesion_threshold=0.8
        )
        
        assert config.merge_getters_setters is False
        assert config.small_method_threshold == 20
        assert config.cohesion_threshold == 0.8
    
    def test_language_specific_config(self):
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
    
    def test_merge_empty_chunks(self):
        """Test handling of empty chunks."""
        merger = TreeSitterSemanticMerger()
        
        # Test with empty list
        assert merger.merge_chunks([]) == []
        
        # Test with chunks having empty content
        chunk = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=1,
            byte_start=0,
            byte_end=0,
            parent_context="",
            content=""
        )
        
        result = merger.merge_chunks([chunk])
        assert len(result) == 1
        assert result[0].content == ""
    
    def test_merge_at_size_boundary(self):
        """Test merging when chunks are exactly at size limit."""
        config = MergeConfig(max_merged_size=10)
        merger = TreeSitterSemanticMerger(config)
        
        # Two 5-line chunks should merge (total 10 lines = limit)
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="class_definition:Test",
            content="def get_x(self):\n    # Line 2\n    # Line 3\n    # Line 4\n    return self.x"
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
            content="def set_x(self, x):\n    # Line 2\n    # Line 3\n    # Line 4\n    self.x = x"
        )
        
        # Should merge since total is exactly at limit
        assert merger.should_merge(chunk1, chunk2)
        
        # But if one chunk is 6 lines, should not merge (total 11 > limit)
        chunk3 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=13,
            end_line=18,
            byte_start=220,
            byte_end=320,
            parent_context="class_definition:Test",
            content="def get_y(self):\n    # Line 2\n    # Line 3\n    # Line 4\n    # Line 5\n    return self.y"
        )
        
        assert not merger.should_merge(chunk1, chunk3)
    
    def test_complex_merge_groups(self):
        """Test merging multiple related chunks in complex scenarios."""
        config = MergeConfig(
            merge_getters_setters=True,
            merge_small_methods=True,
            small_method_threshold=5
        )
        merger = TreeSitterSemanticMerger(config)
        
        # Create a complex scenario with multiple getters/setters
        get_x = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Point",
            content="def get_x(self):\n    return self._x"
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
            content="def set_x(self, x):\n    self._x = x"
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
            content="def get_y(self):\n    return self._y"
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
            content="def set_y(self, y):\n    self._y = y"
        )
        
        # Small utility method that should merge with nearby methods
        validate = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=26,
            end_line=28,
            byte_start=340,
            byte_end=390,
            parent_context="class_definition:Point",
            content="def validate(self):\n    return self._x >= 0 and self._y >= 0"
        )
        
        chunks = [get_x, set_x, get_y, set_y, validate]
        merged = merger.merge_chunks(chunks)
        
        # Should result in fewer chunks due to merging
        assert len(merged) < len(chunks)
        
        # Check that getter/setter pairs are merged
        merged_contents = [chunk.content for chunk in merged]
        assert any("get_x" in content and "set_x" in content for content in merged_contents)
        assert any("get_y" in content and "set_y" in content for content in merged_contents)
    
    def test_cohesion_score_edge_cases(self):
        """Test cohesion score calculation for edge cases."""
        analyzer = TreeSitterRelationshipAnalyzer()
        
        # Test with chunks having no references or dependencies
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=30,
            parent_context="",
            content="def func1():\n    pass",
            references=[],
            dependencies=[]
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
            content="def func2():\n    pass",
            references=[],
            dependencies=[]
        )
        
        score = analyzer.calculate_cohesion_score(chunk1, chunk2)
        # Should still have some score due to same file and proximity
        assert 0 < score < 0.5
        
        # Test with many shared references
        chunk3 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=15,
            byte_start=100,
            byte_end=200,
            parent_context="class_definition:DataProcessor",
            content="def process(self):\n    # processing logic",
            references=["self", "data", "config", "logger", "cache"],
            dependencies=["numpy", "pandas"]
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
            content="def validate(self):\n    # validation logic",
            references=["self", "data", "config", "logger", "validator"],
            dependencies=["numpy", "pandas", "validators"]
        )
        
        score2 = analyzer.calculate_cohesion_score(chunk3, chunk4)
        # Should have high score due to same class, proximity, and shared refs/deps
        assert score2 > 0.7
    
    def test_ruby_getter_setter_merging(self):
        """Test Ruby-specific getter/setter patterns."""
        analyzer = TreeSitterRelationshipAnalyzer()
        
        # Ruby attr_reader/attr_writer style
        getter = CodeChunk(
            language="ruby",
            file_path="/test.rb",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="def name\n  @name\nend"
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
            content="def name=(value)\n  @name = value\nend"
        )
        
        # Ruby doesn't follow the get_/set_ pattern, but we can enhance the analyzer
        # For now, test that they're at least in the same class
        assert analyzer._are_in_same_class(getter, setter)
    
    def test_typescript_interface_implementation(self):
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
            content="interface IUserService {\n  getUser(id: string): User;\n  saveUser(user: User): void;\n}"
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
            content="class UserService implements IUserService {\n  getUser(id: string): User { /* ... */ }\n  saveUser(user: User): void { /* ... */ }\n}"
        )
        
        chunks = [interface, implementation]
        relationships = analyzer.find_interface_implementations(chunks)
        
        assert interface.chunk_id in relationships
        assert implementation.chunk_id in relationships[interface.chunk_id]
    
    def test_merge_with_mixed_languages(self):
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
            content="def hello():\n    print('Hello')"
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
            content="function hello() {\n    console.log('Hello');\n}"
        )
        
        # Even with same function name and structure, different languages shouldn't merge
        assert not merger.should_merge(python_chunk, javascript_chunk)
        
        # Test merge_chunks with mixed languages
        result = merger.merge_chunks([python_chunk, javascript_chunk])
        assert len(result) == 2
        assert result[0].language != result[1].language
    
    def test_constructor_overloading(self):
        """Test handling of overloaded constructors."""
        analyzer = TreeSitterRelationshipAnalyzer()
        config = MergeConfig(merge_overloaded_functions=True)
        merger = TreeSitterSemanticMerger(config)
        
        constructor1 = CodeChunk(
            language="java",
            file_path="/Person.java",
            node_type="constructor",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:Person",
            content="public Person() {\n    this.name = \"Unknown\";\n}"
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
            content="public Person(String name) {\n    this.name = name;\n}"
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
            content="public Person(String name, int age) {\n    this.name = name;\n    this.age = age;\n}"
        )
        
        chunks = [constructor1, constructor2, constructor3]
        groups = analyzer.find_overloaded_functions(chunks)
        
        # All constructors should be in one group
        assert len(groups) == 1
        assert len(groups[0]) == 3
        
        # Test merging based on Java config (constructors usually not merged)
        java_config = MergeConfig()
        java_config.language_configs["java"]["merge_constructors"] = True
        merger_java = TreeSitterSemanticMerger(java_config)
        
        merged = merger_java.merge_chunks(chunks)
        # With merge_constructors=True, should merge
        assert len(merged) == 1
    
    def test_python_decorator_methods(self):
        """Test Python decorator method merging."""
        config = MergeConfig()
        merger = TreeSitterSemanticMerger(config)
        
        # Test @staticmethod and @classmethod merging
        static_method = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=13,
            byte_start=100,
            byte_end=180,
            parent_context="class_definition:Utils",
            content="@staticmethod\ndef validate_email(email):\n    return '@' in email"
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
            content="@classmethod\ndef from_string(cls, string):\n    return cls(string)"
        )
        
        # Small related methods in same class should merge
        assert merger.should_merge(static_method, class_method)
    
    def test_large_chunk_groups(self):
        """Test handling of large groups of related chunks."""
        config = MergeConfig(
            merge_overloaded_functions=True,
            max_merged_size=200  # Larger limit for this test
        )
        merger = TreeSitterSemanticMerger(config)
        
        # Create 5 overloaded methods
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
                content=f"public int calculate({', '.join(['int a' + str(j) for j in range(i+1)])}) {{\n    return sum;\n}}"
            )
            overloaded_chunks.append(chunk)
        
        # Also add unrelated method
        unrelated = CodeChunk(
            language="java",
            file_path="/Calculator.java",
            node_type="method_definition",
            start_line=40,
            end_line=43,
            byte_start=600,
            byte_end=690,
            parent_context="class_definition:Calculator",
            content="public void reset() {\n    this.result = 0;\n}"
        )
        
        all_chunks = overloaded_chunks + [unrelated]
        merged = merger.merge_chunks(all_chunks)
        
        # Should merge all overloaded methods into one, keep unrelated separate
        assert len(merged) == 2
        
        # Find the merged chunk
        merged_chunk = next(c for c in merged if "calculate" in c.content)
        assert merged_chunk.start_line == 10
        assert merged_chunk.end_line == 33  # Last overloaded method end line
    
    def test_recursive_merge_groups(self):
        """Test that merge groups are built correctly with transitive relationships."""
        config = MergeConfig(
            merge_small_methods=True,
            small_method_threshold=10,
            cohesion_threshold=0.5
        )
        merger = TreeSitterSemanticMerger(config)
        
        # Create a chain of related methods A-B-C where A relates to B, B to C
        # but A doesn't directly relate to C
        method_a = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:DataHandler",
            content="def validate_input(self):\n    return True",
            references=["self", "input_data"],
            dependencies=[]
        )
        
        method_b = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,  # Adjacent to A
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:DataHandler",
            content="def clean_input(self):\n    return cleaned",
            references=["self", "input_data", "cleaned"],
            dependencies=[]
        )
        
        method_c = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=18,  # Adjacent to B
            end_line=20,
            byte_start=220,
            byte_end=270,
            parent_context="class_definition:DataHandler",
            content="def process_cleaned(self):\n    return result",
            references=["self", "cleaned", "result"],
            dependencies=[]
        )
        
        chunks = [method_a, method_b, method_c]
        merged = merger.merge_chunks(chunks)
        
        # All three should be merged due to transitive relationships
        assert len(merged) == 1
        assert all(method in merged[0].content 
                  for method in ["validate_input", "clean_input", "process_cleaned"])
    
    def test_javascript_class_methods(self):
        """Test JavaScript class method merging patterns."""
        # Use config that doesn't merge small methods to test specific patterns
        config = MergeConfig(
            merge_getters_setters=True,
            merge_small_methods=False  # Disable to test getter/setter behavior only
        )
        merger = TreeSitterSemanticMerger(config)
        
        # Modern JS class syntax
        constructor = CodeChunk(
            language="javascript",
            file_path="/user.js",
            node_type="method_definition",
            start_line=5,
            end_line=8,
            byte_start=50,
            byte_end=120,
            parent_context="class_definition:User",
            content="constructor(name) {\n    this.name = name;\n    this.id = null;\n}"
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
            content="get fullName() {\n    return this.name;\n}"
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
            content="set fullName(value) {\n    this.name = value;\n}"
        )
        
        # Getter and setter should merge (they're event handlers)
        assert merger.should_merge(getter, setter)
        
        # Constructor should not merge with getter/setter when small methods merging is disabled
        assert not merger.should_merge(constructor, getter)
    
    def test_go_method_receiver_patterns(self):
        """Test Go method patterns with receivers."""
        analyzer = TreeSitterRelationshipAnalyzer()
        
        # Go methods with pointer receivers
        method1 = CodeChunk(
            language="go",
            file_path="/user.go",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="type:User",
            content="func (u *User) GetName() string {\n    return u.name\n}"
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
            content="func (u *User) SetName(name string) {\n    u.name = name\n}"
        )
        
        # Should recognize as getter/setter pair
        pairs = analyzer.find_getter_setter_pairs([method1, method2])
        assert len(pairs) == 1
    
    def test_merge_preserves_metadata(self):
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
            content="def add(self, a, b):\n    return a + b",
            references=["self", "a", "b"],
            dependencies=["math"]
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
            content="def subtract(self, a, b):\n    return a - b",
            references=["self", "a", "b", "c"],
            dependencies=["math", "numpy"]
        )
        
        merged_chunks = merger.merge_chunks([chunk1, chunk2])
        assert len(merged_chunks) == 1
        
        merged = merged_chunks[0]
        # Check metadata preservation
        assert merged.language == "python"
        assert merged.file_path == "/test.py"
        assert merged.parent_context == "class_definition:Calculator"
        
        # Check combined references and dependencies
        assert "self" in merged.references
        assert "a" in merged.references
        assert "b" in merged.references
        assert "c" in merged.references  # From chunk2
        assert "math" in merged.dependencies
        assert "numpy" in merged.dependencies  # From chunk2
    
    def test_csharp_property_patterns(self):
        """Test C# property getter/setter patterns."""
        analyzer = TreeSitterRelationshipAnalyzer()
        
        # C# auto-property style might not be separate chunks, but explicit properties
        getter = CodeChunk(
            language="csharp",
            file_path="/User.cs",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:User",
            content="public string GetName() {\n    return _name;\n}"
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
            content="public void SetName(string value) {\n    _name = value;\n}"
        )
        
        pairs = analyzer.find_getter_setter_pairs([getter, setter])
        assert len(pairs) == 1
        assert pairs[0] == (getter, setter)
    
    def test_performance_caching(self):
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
            content="def func1():\n    pass"
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
            content="def func2():\n    pass"
        )
        
        # First call should compute
        result1 = merger.should_merge(chunk1, chunk2)
        
        # Subsequent calls should use cache (we can't directly test this without
        # accessing private attributes, but we can verify consistent results)
        result2 = merger.should_merge(chunk1, chunk2)
        result3 = merger.should_merge(chunk2, chunk1)  # Different order
        
        assert result1 == result2
        # Note: The implementation might not cache reverse order, but results should be consistent
    
    def test_cohesion_score_caps_at_one(self):
        """Test that cohesion score never exceeds 1.0."""
        analyzer = TreeSitterRelationshipAnalyzer()
        
        # Create chunks that have many reasons for high cohesion
        chunk1 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=10,
            end_line=12,
            byte_start=100,
            byte_end=150,
            parent_context="class_definition:DataProcessor",
            content="def get_data(self):\n    return self._data",
            references=["self", "data", "cache", "config", "logger"],
            dependencies=["numpy", "pandas", "sklearn"]
        )
        
        chunk2 = CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="method_definition",
            start_line=14,  # Very close
            end_line=16,
            byte_start=160,
            byte_end=210,
            parent_context="class_definition:DataProcessor",  # Same class
            content="def set_data(self, data):\n    self._data = data",
            references=["self", "data", "cache", "config", "logger"],  # Same refs
            dependencies=["numpy", "pandas", "sklearn"]  # Same deps
        )
        
        score = analyzer.calculate_cohesion_score(chunk1, chunk2)
        assert score <= 1.0
        assert score > 0.9  # Should be very high but not exceed 1.0
"""Comprehensive tests for chunk hierarchy building and navigation."""
import pytest

from chunker.core import chunk_text
from chunker.hierarchy.builder import ChunkHierarchyBuilder
from chunker.hierarchy.navigator import HierarchyNavigator
from chunker.types import CodeChunk


class TestChunkHierarchyBuilder:
    """Test the ChunkHierarchyBuilder class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = ChunkHierarchyBuilder()
        self.chunks = self._create_test_chunks()

    @classmethod
    def _create_test_chunks(cls) -> list[CodeChunk]:
        """Create a test hierarchy of chunks.

        Structure:
        - module (root)
          - class TestClass
            - method test_method1
            - method test_method2
          - function helper_func
        - function standalone_func (root)
        """
        module_chunk = CodeChunk(language="python", file_path="test.py",
            node_type="module", start_line=1, end_line=20, byte_start=0,
            byte_end=500, parent_context="", content="# module content",
            chunk_id="module_1", parent_chunk_id=None)
        class_chunk = CodeChunk(language="python", file_path="test.py",
            node_type="class_definition", start_line=3, end_line=15,
            byte_start=50, byte_end=400, parent_context="module", content="class TestClass:", chunk_id="class_1", parent_chunk_id="module_1")
        method1_chunk = CodeChunk(language="python", file_path="test.py",
            node_type="function_definition", start_line=5, end_line=8,
            byte_start=100, byte_end=200, parent_context="class_definition",
            content="def test_method1(self):", chunk_id="method_1",
            parent_chunk_id="class_1")
        method2_chunk = CodeChunk(language="python", file_path="test.py",
            node_type="function_definition", start_line=10, end_line=13,
            byte_start=250, byte_end=350, parent_context="class_definition",
            content="def test_method2(self):", chunk_id="method_2",
            parent_chunk_id="class_1")
        helper_chunk = CodeChunk(language="python", file_path="test.py",
            node_type="function_definition", start_line=17, end_line=19,
            byte_start=420, byte_end=480, parent_context="module", content="def helper_func():", chunk_id="helper_1", parent_chunk_id="module_1")
        standalone_chunk = CodeChunk(language="python", file_path="test.py",
            node_type="function_definition", start_line=22, end_line=25,
            byte_start=520, byte_end=600, parent_context="", content="def standalone_func():", chunk_id="standalone_1",
            parent_chunk_id=None)
        return [module_chunk, class_chunk, method1_chunk, method2_chunk,
            helper_chunk, standalone_chunk]

    def test_build_hierarchy_basic(self):
        """Test building a basic hierarchy."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        assert len(hierarchy.root_chunks) == 2
        assert "module_1" in hierarchy.root_chunks
        assert "standalone_1" in hierarchy.root_chunks
        assert hierarchy.parent_map["class_1"] == "module_1"
        assert hierarchy.parent_map["method_1"] == "class_1"
        assert hierarchy.parent_map["method_2"] == "class_1"
        assert hierarchy.parent_map["helper_1"] == "module_1"
        assert "module_1" not in hierarchy.parent_map
        assert "standalone_1" not in hierarchy.parent_map
        assert set(hierarchy.children_map["module_1"]) == {"class_1",
            "helper_1"}
        assert set(hierarchy.children_map["class_1"]) == {"method_1",
            "method_2"}
        assert "method_1" not in hierarchy.children_map
        assert "standalone_1" not in hierarchy.children_map

    def test_build_hierarchy_empty(self):
        """Test building hierarchy with empty chunk list."""
        hierarchy = self.builder.build_hierarchy([])
        assert hierarchy.root_chunks == []
        assert hierarchy.parent_map == {}
        assert hierarchy.children_map == {}
        assert hierarchy.chunk_map == {}

    def test_build_hierarchy_orphaned_chunks(self):
        """Test handling chunks with missing parents."""
        chunks = [CodeChunk(language="python", file_path="test.py",
            node_type="function_definition", start_line=1, end_line=3,
            byte_start=0, byte_end=50, parent_context="", content="def func():", chunk_id="func_1", parent_chunk_id="missing_parent"),
            ]
        hierarchy = self.builder.build_hierarchy(chunks)
        assert hierarchy.root_chunks == ["func_1"]
        assert hierarchy.parent_map == {"func_1": "missing_parent"}

    def test_find_common_ancestor_same_chunk(self):
        """Test finding common ancestor when both chunks are the same."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        method1 = self.chunks[2]
        ancestor = self.builder.find_common_ancestor(method1, method1,
            hierarchy)
        assert ancestor == "method_1"

    def test_find_common_ancestor_siblings(self):
        """Test finding common ancestor of sibling chunks."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        method1 = self.chunks[2]
        method2 = self.chunks[3]
        ancestor = self.builder.find_common_ancestor(method1, method2,
            hierarchy)
        assert ancestor == "class_1"

    def test_find_common_ancestor_parent_child(self):
        """Test finding common ancestor of parent-child chunks."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        class_chunk = self.chunks[1]
        method1 = self.chunks[2]
        ancestor = self.builder.find_common_ancestor(class_chunk, method1,
            hierarchy)
        assert ancestor == "class_1"

    def test_find_common_ancestor_no_common(self):
        """Test finding common ancestor of chunks in different trees."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        method1 = self.chunks[2]
        standalone = self.chunks[5]
        ancestor = self.builder.find_common_ancestor(method1, standalone,
            hierarchy)
        assert ancestor is None

    def test_validate_hierarchy_valid(self):
        """Test validation of a valid hierarchy."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        assert self.builder.validate_hierarchy(hierarchy) is True

    def test_validate_hierarchy_cycle(self):
        """Test detection of cycles in hierarchy."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        hierarchy.parent_map["module_1"] = "class_1"
        with pytest.raises(ValueError, match="Cycle detected"):
            self.builder.validate_hierarchy(hierarchy)

    def test_validate_hierarchy_inconsistent_maps(self):
        """Test detection of inconsistent parent/children maps."""
        hierarchy = self.builder.build_hierarchy(self.chunks)
        hierarchy.children_map["class_1"].remove("method_1")
        with pytest.raises(ValueError, match="not in parent"):
            self.builder.validate_hierarchy(hierarchy)

    def test_chunk_ordering(self):
        """Test that chunks are ordered by start line."""
        chunks = list(reversed(self.chunks))
        hierarchy = self.builder.build_hierarchy(chunks)
        assert hierarchy.root_chunks[0] == "module_1"
        assert hierarchy.root_chunks[1] == "standalone_1"
        assert hierarchy.children_map["class_1"][0] == "method_1"
        assert hierarchy.children_map["class_1"][1] == "method_2"


class TestHierarchyNavigator:
    """Test the HierarchyNavigator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.navigator = HierarchyNavigator()
        self.builder = ChunkHierarchyBuilder()
        self.chunks = self._create_test_chunks()
        self.hierarchy = self.builder.build_hierarchy(self.chunks)

    @classmethod
    def _create_test_chunks(cls) -> list[CodeChunk]:
        """Create the same test hierarchy as builder tests."""
        return TestChunkHierarchyBuilder()._create_test_chunks()

    def test_get_children(self):
        """Test getting direct children of a chunk."""
        children = self.navigator.get_children("class_1", self.hierarchy)
        assert len(children) == 2
        assert children[0].chunk_id == "method_1"
        assert children[1].chunk_id == "method_2"
        children = self.navigator.get_children("method_1", self.hierarchy)
        assert children == []
        children = self.navigator.get_children("nonexistent", self.hierarchy)
        assert children == []

    def test_get_descendants(self):
        """Test getting all descendants of a chunk."""
        descendants = self.navigator.get_descendants("module_1", self.hierarchy,
            )
        assert len(descendants) == 4
        descendant_ids = {d.chunk_id for d in descendants}
        assert descendant_ids == {"class_1", "method_1", "method_2", "helper_1",
            }
        descendants = self.navigator.get_descendants("class_1", self.hierarchy)
        assert len(descendants) == 2
        assert descendants[0].chunk_id == "method_1"
        assert descendants[1].chunk_id == "method_2"
        descendants = self.navigator.get_descendants("method_1", self.hierarchy,
            )
        assert descendants == []

    def test_get_ancestors(self):
        """Test getting all ancestors of a chunk."""
        ancestors = self.navigator.get_ancestors("method_1", self.hierarchy)
        assert len(ancestors) == 2
        assert ancestors[0].chunk_id == "class_1"
        assert ancestors[1].chunk_id == "module_1"
        ancestors = self.navigator.get_ancestors("module_1", self.hierarchy)
        assert ancestors == []

    def test_get_siblings(self):
        """Test getting sibling chunks."""
        siblings = self.navigator.get_siblings("method_1", self.hierarchy)
        assert len(siblings) == 1
        assert siblings[0].chunk_id == "method_2"
        siblings = self.navigator.get_siblings("class_1", self.hierarchy)
        assert len(siblings) == 1
        assert siblings[0].chunk_id == "helper_1"
        siblings = self.navigator.get_siblings("module_1", self.hierarchy)
        assert len(siblings) == 1
        assert siblings[0].chunk_id == "standalone_1"

    def test_filter_by_depth(self):
        """Test filtering chunks by depth."""
        chunks = self.navigator.filter_by_depth(self.hierarchy, min_depth=0,
            max_depth=0)
        assert len(chunks) == 2
        chunk_ids = {c.chunk_id for c in chunks}
        assert chunk_ids == {"module_1", "standalone_1"}
        chunks = self.navigator.filter_by_depth(self.hierarchy, min_depth=1,
            max_depth=1)
        assert len(chunks) == 2
        chunk_ids = {c.chunk_id for c in chunks}
        assert chunk_ids == {"class_1", "helper_1"}
        chunks = self.navigator.filter_by_depth(self.hierarchy, min_depth=2,
            max_depth=2)
        assert len(chunks) == 2
        chunk_ids = {c.chunk_id for c in chunks}
        assert chunk_ids == {"method_1", "method_2"}
        chunks = self.navigator.filter_by_depth(self.hierarchy, min_depth=1)
        assert len(chunks) == 4
        chunks = self.navigator.filter_by_depth(self.hierarchy)
        assert len(chunks) == 6

    def test_get_depth(self):
        """Test getting depth of chunks."""
        assert self.hierarchy.get_depth("module_1") == 0
        assert self.hierarchy.get_depth("standalone_1") == 0
        assert self.hierarchy.get_depth("class_1") == 1
        assert self.hierarchy.get_depth("helper_1") == 1
        assert self.hierarchy.get_depth("method_1") == 2
        assert self.hierarchy.get_depth("method_2") == 2

    def test_get_subtree(self):
        """Test extracting a subtree."""
        subtree = self.navigator.get_subtree("class_1", self.hierarchy)
        assert subtree.root_chunks == ["class_1"]
        assert len(subtree.chunk_map) == 3
        assert set(subtree.chunk_map.keys()) == {"class_1", "method_1",
            "method_2"}
        assert subtree.children_map["class_1"] == ["method_1", "method_2"]
        assert "method_1" in subtree.parent_map
        assert subtree.parent_map["method_1"] == "class_1"
        subtree = self.navigator.get_subtree("method_1", self.hierarchy)
        assert subtree.root_chunks == ["method_1"]
        assert len(subtree.chunk_map) == 1
        assert subtree.parent_map == {}
        assert subtree.children_map == {}
        subtree = self.navigator.get_subtree("nonexistent", self.hierarchy)
        assert subtree.root_chunks == []
        assert subtree.chunk_map == {}

    def test_get_level_order_traversal(self):
        """Test level-order traversal of hierarchy."""
        levels = self.navigator.get_level_order_traversal(self.hierarchy)
        assert len(levels) == 3
        assert len(levels[0]) == 2
        level0_ids = {c.chunk_id for c in levels[0]}
        assert level0_ids == {"module_1", "standalone_1"}
        assert len(levels[1]) == 2
        level1_ids = {c.chunk_id for c in levels[1]}
        assert level1_ids == {"class_1", "helper_1"}
        assert len(levels[2]) == 2
        level2_ids = {c.chunk_id for c in levels[2]}
        assert level2_ids == {"method_1", "method_2"}

    def test_find_chunks_by_type(self):
        """Test finding chunks by node type."""
        functions = self.navigator.find_chunks_by_type("function_definition",
            self.hierarchy)
        assert len(functions) == 4
        func_ids = {f.chunk_id for f in functions}
        assert func_ids == {"method_1", "method_2", "helper_1", "standalone_1"}
        classes = self.navigator.find_chunks_by_type("class_definition",
            self.hierarchy)
        assert len(classes) == 1
        assert classes[0].chunk_id == "class_1"
        functions = self.navigator.find_chunks_by_type("function_definition",
            self.hierarchy, subtree_root="class_1")
        assert len(functions) == 2
        func_ids = {f.chunk_id for f in functions}
        assert func_ids == {"method_1", "method_2"}
        results = self.navigator.find_chunks_by_type("nonexistent_type",
            self.hierarchy)
        assert results == []


class TestHierarchyIntegration:
    """Integration tests using real Tree-sitter parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = ChunkHierarchyBuilder()
        self.navigator = HierarchyNavigator()

    def test_python_code_hierarchy(self):
        """Test hierarchy building with real Python code."""
        python_code = """
class Calculator:
    ""\"A simple calculator class.""\"

    def __init__(self):
        self.result = 0

    def add(self, x, y):
        ""\"Add two numbers.""\"
        return x + y

    def multiply(self, x, y):
        ""\"Multiply two numbers.""\"
        return x * y

    class NestedClass:
        def nested_method(self):
            pass

def helper_function():
    ""\"A helper function.""\"
    return 42

async def async_function():
    ""\"An async function.""\"
    pass
"""
        chunks = chunk_text(python_code, "python", "calculator.py")
        hierarchy = self.builder.build_hierarchy(chunks)
        assert len(hierarchy.root_chunks) >= 3
        calc_chunks = self.navigator.find_chunks_by_type("class_definition",
            hierarchy)
        calc_chunk = next((c for c in calc_chunks if "Calculator" in c.
            content), None)
        assert calc_chunk is not None
        calc_children = self.navigator.get_children(calc_chunk.chunk_id,
            hierarchy)
        calc_child_types = {c.node_type for c in calc_children}
        assert "function_definition" in calc_child_types
        depth_0 = self.navigator.filter_by_depth(hierarchy, 0, 0)
        depth_1 = self.navigator.filter_by_depth(hierarchy, 1, 1)
        assert len(depth_0) > 0
        assert len(depth_1) > 0

    def test_javascript_code_hierarchy(self):
        """Test hierarchy building with JavaScript code."""
        js_code = """
class Component {
    constructor() {
        this.state = {};
    }

    render() {
        return null;
    }

    static defaultProps = {
        name: "Component"
    };
}

function processData(data) {
    return data.map(item => {
        return item * 2;
    });
}

const arrowFunc = () => {
    console.log("Hello");
};
"""
        chunks = chunk_text(js_code, "javascript", "component.js")
        hierarchy = self.builder.build_hierarchy(chunks)
        assert len(hierarchy.chunk_map) > 0
        root_funcs = [hierarchy.chunk_map[cid] for cid in hierarchy.
            root_chunks if cid in hierarchy.chunk_map and hierarchy.
            chunk_map[cid].node_type in {"function_declaration",
            "arrow_function"}]
        assert len(root_funcs) >= 1

    def test_complex_nesting(self):
        """Test deeply nested structures."""
        chunks = []
        for i in range(5):
            chunk = CodeChunk(language="python", file_path="nested.py",
                node_type="class_definition" if i % 2 == 0 else
                "function_definition", start_line=i * 10 + 1, end_line=(i +
                1) * 10, byte_start=i * 100, byte_end=(i + 1) * 100,
                parent_context="", content=f"level_{i}", chunk_id=f"chunk_{i}", parent_chunk_id=f"chunk_{i - 1}" if i > 0 else
                None)
            chunks.append(chunk)
        hierarchy = self.builder.build_hierarchy(chunks)
        assert hierarchy.get_depth("chunk_0") == 0
        assert hierarchy.get_depth("chunk_4") == 4
        ancestors = self.navigator.get_ancestors("chunk_4", hierarchy)
        assert len(ancestors) == 4
        assert ancestors[0].chunk_id == "chunk_3"
        assert ancestors[-1].chunk_id == "chunk_0"
        subtree = self.navigator.get_subtree("chunk_2", hierarchy)
        assert len(subtree.chunk_map) == 3
        assert subtree.root_chunks == ["chunk_2"]

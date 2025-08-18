"""Test enhanced base metadata extractor for Phase 1.5."""

import pytest
from typing import Any
from tree_sitter import Node
from chunker.metadata.extractor import BaseMetadataExtractor
from chunker.parser import get_parser


class SimpleMetadataExtractor(BaseMetadataExtractor):
    """Simple concrete implementation for testing."""
    
    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        return []
    
    def extract_exports(self, node: Node, source: bytes) -> list[str]:
        return []
    
    def extract_dependencies(self, node: Node, source: bytes) -> list[str]:
        return []
    
    def extract_signature(self, node: Node, source: bytes) -> dict[str, Any] | None:
        return None
    
    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        return None


class TestEnhancedBaseExtractor:
    """Test the enhanced base metadata extractor."""

    def test_python_function_calls(self):
        """Test Python function call extraction."""
        code = """
def test():
    print("hello")
    len("test")
    obj.method()
"""
        extractor = SimpleMetadataExtractor("python")
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        names = [call["name"] for call in calls]
        
        assert "print" in names
        assert "len" in names
        assert "method" in names
        
        # Verify spans
        for call in calls:
            assert call["start"] < call["end"]
            assert call["function_start"] <= call["function_end"]

    def test_javascript_method_calls(self):
        """Test JavaScript method call extraction."""
        code = """
function test() {
    console.log("hello");
    "test".length;
    obj.method();
}
"""
        extractor = SimpleMetadataExtractor("javascript")
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        names = [call["name"] for call in calls]
        
        assert "log" in names
        # Note: "length" might not be detected as it's property access, not a call
        assert "method" in names

    def test_rust_method_calls(self):
        """Test Rust method call extraction."""
        code = """
fn test() {
    println!("hello");
    "test".len();
    obj.method();
}
"""
        extractor = SimpleMetadataExtractor("rust")
        parser = get_parser("rust")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        names = [call["name"] for call in calls]
        
        assert "println" in names
        assert "len" in names
        assert "method" in names

    def test_go_method_calls(self):
        """Test Go method call extraction."""
        code = """
func test() {
    fmt.Println("hello")
    obj.Method()
}
"""
        extractor = SimpleMetadataExtractor("go")
        parser = get_parser("go")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        names = [call["name"] for call in calls]
        
        assert "Println" in names
        assert "Method" in names

    def test_c_function_calls(self):
        """Test C function call extraction."""
        code = """
void test() {
    printf("hello");
    strlen("test");
    obj->method();
}
"""
        extractor = SimpleMetadataExtractor("c")
        parser = get_parser("c")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        names = [call["name"] for call in calls]
        
        assert "printf" in names
        assert "strlen" in names
        # Note: obj->method might be filtered out in base implementation

    def test_cpp_method_calls(self):
        """Test C++ method call extraction."""
        code = """
void test() {
    std::cout << "hello";
    obj.method();
    Class::staticMethod();
}
"""
        extractor = SimpleMetadataExtractor("cpp")
        parser = get_parser("cpp")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        names = [call["name"] for call in calls]
        
        # Note: << operator might not be detected as a call
        assert "method" in names
        assert "staticMethod" in names


class TestCallSpanAccuracy:
    """Test accuracy of call span extraction."""

    def test_span_boundaries(self):
        """Test that span boundaries are accurate."""
        code = """print("hello")"""
        
        extractor = SimpleMetadataExtractor("python")
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        assert len(calls) == 1
        
        call = calls[0]
        assert call["name"] == "print"
        
        # Extract actual text using spans
        full_call = code[call["start"]:call["end"]]
        func_name = code[call["function_start"]:call["function_end"]]
        
        assert full_call == 'print("hello")'
        assert func_name == "print"

    def test_method_call_spans(self):
        """Test method call span extraction."""
        code = """obj.method("arg")"""
        
        extractor = SimpleMetadataExtractor("python")
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        assert len(calls) == 1
        
        call = calls[0]
        assert call["name"] == "method"
        
        # Extract actual text using spans
        full_call = code[call["start"]:call["end"]]
        assert full_call == 'obj.method("arg")'

    def test_nested_call_spans(self):
        """Test nested function call spans."""
        code = """len(str(123))"""
        
        extractor = SimpleMetadataExtractor("python")
        parser = get_parser("python")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        names = [call["name"] for call in calls]
        
        assert "len" in names
        assert "str" in names
        
        # Verify each call has valid spans
        for call in calls:
            assert call["start"] < call["end"]
            full_call = code[call["start"]:call["end"]]
            assert call["name"] in full_call
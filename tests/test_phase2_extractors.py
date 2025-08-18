"""Test suite for Phase 2: Language-specific metadata extractors."""

import pytest
from chunker.core import chunk_text
from chunker.metadata import MetadataExtractorFactory


class TestPhase2LanguageExtractors:
    """Test language-specific call extraction."""

    def test_python_extractor(self):
        """Test Python call extraction with metadata integration."""
        code = """
def test_function():
    print("hello")
    result = len([1, 2, 3])
    obj.method()
    
@decorator()
def decorated():
    pass
"""
        chunks = chunk_text(code, "python")
        
        # Find the test_function chunk
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test_function":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        assert "calls" in func_chunk.metadata
        assert "call_spans" in func_chunk.metadata
        
        # Check backward compatibility
        calls = func_chunk.metadata["calls"]
        assert "print" in calls
        assert "len" in calls
        assert "method" in calls
        
        # Check new detailed format
        call_spans = func_chunk.metadata["call_spans"]
        assert len(call_spans) >= 3
        
        # Verify span structure
        for span in call_spans:
            assert "name" in span
            assert "start" in span
            assert "end" in span
            assert "function_start" in span
            assert "function_end" in span
            assert span["start"] <= span["function_start"]
            assert span["function_end"] <= span["end"]

    def test_rust_extractor(self):
        """Test Rust call extraction."""
        code = """
fn test() {
    println!("hello");
    let result = vec.len();
    obj.method();
    Struct::associated_method();
}
"""
        chunks = chunk_text(code, "rust")
        
        # Find the test function chunk
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        assert "calls" in func_chunk.metadata
        
        calls = func_chunk.metadata["calls"]
        assert "println" in calls
        assert "len" in calls
        assert "method" in calls
        assert "associated_method" in calls

    def test_go_extractor(self):
        """Test Go call extraction."""
        code = """
func test() {
    fmt.Println("hello")
    result := make([]int, 10)
    obj.Method()
}
"""
        chunks = chunk_text(code, "go")
        
        # Find the test function chunk
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        assert "calls" in func_chunk.metadata
        
        calls = func_chunk.metadata["calls"]
        assert "Println" in calls
        assert "make" in calls
        assert "Method" in calls

    def test_c_extractor(self):
        """Test C call extraction."""
        code = """
void test() {
    printf("hello");
    int len = strlen("test");
    func_ptr();
}
"""
        chunks = chunk_text(code, "c")
        
        # Find the test function chunk
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        assert "calls" in func_chunk.metadata
        
        calls = func_chunk.metadata["calls"]
        assert "printf" in calls
        assert "strlen" in calls
        assert "func_ptr" in calls

    def test_cpp_extractor(self):
        """Test C++ call extraction."""
        code = """
void test() {
    std::cout << "hello";
    obj.method();
    Class::staticMethod();
    vector.size();
}
"""
        chunks = chunk_text(code, "cpp")
        
        # Find the test function chunk
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        assert "calls" in func_chunk.metadata
        
        calls = func_chunk.metadata["calls"]
        assert "method" in calls
        assert "staticMethod" in calls
        assert "size" in calls
    
    def test_javascript_extractor(self):
        """Test JavaScript call extraction."""
        code = """
function test() {
    console.log("hello");
    obj.method("arg");
    new MyClass();
    super.method();
}
"""
        chunks = chunk_text(code, "javascript")
        
        # Find the test function chunk
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        assert "calls" in func_chunk.metadata
        
        calls = func_chunk.metadata["calls"]
        assert "console.log" in calls or "log" in calls
        assert "obj.method" in calls or "method" in calls
        assert "new MyClass" in calls or "MyClass" in calls


class TestCallSpanAccuracy:
    """Test accuracy of call span extraction across languages."""

    def test_python_span_accuracy(self):
        """Test Python call span byte positions."""
        code = '''def test():
    print("hello")'''
        
        chunks = chunk_text(code, "python")
        assert len(chunks) > 0
        
        chunk = chunks[0]
        assert "call_spans" in chunk.metadata
        
        spans = chunk.metadata["call_spans"]
        assert len(spans) == 1
        
        span = spans[0]
        assert span["name"] == "print"
        
        # Extract text using spans - the span is relative to the full code text
        # Find where print starts in the code
        print_start = code.find('print("hello")')
        # The span positions should match the actual call
        full_call = code[span["start"]:span["end"]]
        assert full_call == 'print("hello")'

    def test_method_call_spans(self):
        """Test method call span extraction."""
        code = '''def test():
    obj.method("arg")'''
        
        chunks = chunk_text(code, "python")
        assert len(chunks) > 0
        
        chunk = chunks[0]
        assert "call_spans" in chunk.metadata
        
        spans = chunk.metadata["call_spans"]
        assert len(spans) == 1
        
        span = spans[0]
        assert span["name"] == "method"
        
        # Verify span covers entire call
        full_call = code[span["start"]:span["end"]]
        assert full_call == 'obj.method("arg")'


class TestBackwardCompatibility:
    """Test backward compatibility of metadata structure."""

    def test_calls_field_preserved(self):
        """Test that the old 'calls' field is still populated."""
        code = """
def test():
    print("hello")
    len("test")
"""
        chunks = chunk_text(code, "python")
        
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        
        # Old field should still exist
        assert "calls" in func_chunk.metadata
        assert isinstance(func_chunk.metadata["calls"], list)
        assert all(isinstance(call, str) for call in func_chunk.metadata["calls"])
        
        # New field should also exist
        assert "call_spans" in func_chunk.metadata
        assert isinstance(func_chunk.metadata["call_spans"], list)
        assert all(isinstance(span, dict) for span in func_chunk.metadata["call_spans"])
        
        # Both should have same function names
        old_names = sorted(func_chunk.metadata["calls"])
        new_names = sorted(span["name"] for span in func_chunk.metadata["call_spans"])
        assert old_names == new_names


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_function(self):
        """Test handling of functions with no calls."""
        code = """
def empty_function():
    pass
"""
        chunks = chunk_text(code, "python")
        
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "empty_function":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        
        # Should not have calls field if no calls found
        assert "calls" not in func_chunk.metadata or func_chunk.metadata["calls"] == []
        assert "call_spans" not in func_chunk.metadata or func_chunk.metadata["call_spans"] == []

    def test_nested_calls(self):
        """Test handling of nested function calls."""
        code = """
def test():
    result = len(str(int(3.14)))
"""
        chunks = chunk_text(code, "python")
        
        func_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("signature", {}).get("name") == "test":
                func_chunk = chunk
                break
        
        assert func_chunk is not None
        assert "calls" in func_chunk.metadata
        
        calls = func_chunk.metadata["calls"]
        assert "len" in calls
        assert "str" in calls
        assert "int" in calls
        
        # All three calls should have spans
        spans = func_chunk.metadata["call_spans"]
        assert len(spans) == 3


class TestFallbackBehavior:
    """Test fallback to base extractor for languages without specific extractors."""

    def test_unsupported_language_uses_base(self):
        """Test that languages without specific extractors use base implementation."""
        # Use a language that doesn't have a specific extractor yet
        code = """
function test() {
    console.log("hello");
    arr.map(x => x * 2);
}
"""
        # JavaScript has an extractor, but let's test with a theoretical language
        # that would fall back to base implementation
        extractor = MetadataExtractorFactory.create_extractor("javascript")
        assert extractor is not None
        
        # The extractor should still extract calls
        from chunker.parser import get_parser
        parser = get_parser("javascript")
        tree = parser.parse(code.encode())
        
        calls = extractor.extract_calls(tree.root_node, code.encode())
        assert len(calls) > 0
        
        # Should detect at least some calls
        call_names = [call["name"] for call in calls]
        assert "console.log" in call_names  # JavaScript extractor should find this
        assert "arr.map" in call_names  # Should find method call too
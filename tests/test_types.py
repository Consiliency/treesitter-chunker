"""Comprehensive tests for the type system."""
import pytest
import json
import hashlib
from dataclasses import asdict, fields, replace
from typing import get_type_hints

from chunker.types import CodeChunk


class TestCodeChunkBasics:
    """Test basic CodeChunk functionality."""
    
    def test_dataclass_fields(self):
        """Test that CodeChunk has all expected fields."""
        field_names = {f.name for f in fields(CodeChunk)}
        expected_fields = {
            'language', 'file_path', 'node_type', 'start_line', 'end_line',
            'byte_start', 'byte_end', 'parent_context', 'content', 
            'chunk_id', 'parent_chunk_id', 'references', 'dependencies'
        }
        assert field_names == expected_fields
    
    def test_field_types(self):
        """Test that fields have correct type annotations."""
        type_hints = get_type_hints(CodeChunk)
        
        # Required string fields
        for field in ['language', 'file_path', 'node_type', 'parent_context', 'content']:
            assert type_hints[field] == str
        
        # Required int fields
        for field in ['start_line', 'end_line', 'byte_start', 'byte_end']:
            assert type_hints[field] == int
        
        # Optional fields
        assert type_hints['chunk_id'] == str
        assert type_hints['parent_chunk_id'] == str | None
        assert type_hints['references'] == list[str]
        assert type_hints['dependencies'] == list[str]
    
    def test_create_minimal_chunk(self):
        """Test creating a chunk with minimal required fields."""
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test():\n    pass"
        )
        
        assert chunk.language == "python"
        assert chunk.file_path == "/test/file.py"
        assert chunk.node_type == "function"
        assert chunk.start_line == 1
        assert chunk.end_line == 5
        assert chunk.byte_start == 0
        assert chunk.byte_end == 100
        assert chunk.parent_context == "module"
        assert chunk.content == "def test():\n    pass"
        
        # Check defaults
        assert chunk.chunk_id != ""  # Should be auto-generated
        assert chunk.parent_chunk_id is None
        assert chunk.references == []
        assert chunk.dependencies == []
    
    def test_create_full_chunk(self):
        """Test creating a chunk with all fields specified."""
        chunk = CodeChunk(
            language="javascript",
            file_path="/app/main.js",
            node_type="class",
            start_line=10,
            end_line=20,
            byte_start=150,
            byte_end=400,
            parent_context="module",
            content="class MyClass { }",
            chunk_id="custom_id_123",
            parent_chunk_id="parent_456",
            references=["ref1", "ref2"],
            dependencies=["dep1", "dep2", "dep3"]
        )
        
        assert chunk.chunk_id == "custom_id_123"
        assert chunk.parent_chunk_id == "parent_456"
        assert chunk.references == ["ref1", "ref2"]
        assert chunk.dependencies == ["dep1", "dep2", "dep3"]


class TestChunkIdGeneration:
    """Test chunk ID generation functionality."""
    
    def test_generate_id_method(self):
        """Test the generate_id method."""
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test():\n    pass"
        )
        
        generated_id = chunk.generate_id()
        
        # Should be 16 characters (hex)
        assert len(generated_id) == 16
        assert all(c in '0123456789abcdef' for c in generated_id)
        
        # Should be deterministic
        assert chunk.generate_id() == generated_id
    
    def test_auto_id_generation_on_init(self):
        """Test that chunk_id is auto-generated when not provided."""
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test():\n    pass"
        )
        
        assert chunk.chunk_id != ""
        assert len(chunk.chunk_id) == 16
        assert chunk.chunk_id == chunk.generate_id()
    
    def test_custom_id_not_overwritten(self):
        """Test that custom chunk_id is not overwritten."""
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test():\n    pass",
            chunk_id="my_custom_id"
        )
        
        assert chunk.chunk_id == "my_custom_id"
        assert chunk.chunk_id != chunk.generate_id()
    
    def test_id_generation_uniqueness(self):
        """Test that different chunks generate different IDs."""
        chunk1 = CodeChunk(
            language="python",
            file_path="/test/file1.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test1():\n    pass"
        )
        
        chunk2 = CodeChunk(
            language="python",
            file_path="/test/file2.py",  # Different file
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test1():\n    pass"
        )
        
        chunk3 = CodeChunk(
            language="python",
            file_path="/test/file1.py",
            node_type="function",
            start_line=10,  # Different line
            end_line=15,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test1():\n    pass"
        )
        
        chunk4 = CodeChunk(
            language="python",
            file_path="/test/file1.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test2():\n    pass"  # Different content
        )
        
        # All should have different IDs
        ids = {chunk1.chunk_id, chunk2.chunk_id, chunk3.chunk_id, chunk4.chunk_id}
        assert len(ids) == 4
    
    def test_id_generation_consistency(self):
        """Test that ID generation is consistent for same data."""
        # Create two identical chunks
        chunk1 = CodeChunk(
            language="rust",
            file_path="/src/main.rs",
            node_type="function",
            start_line=42,
            end_line=50,
            byte_start=1000,
            byte_end=1500,
            parent_context="impl",
            content="fn process() -> Result<()> { Ok(()) }"
        )
        
        chunk2 = CodeChunk(
            language="rust",
            file_path="/src/main.rs",
            node_type="function",
            start_line=42,
            end_line=50,
            byte_start=1000,
            byte_end=1500,
            parent_context="impl",
            content="fn process() -> Result<()> { Ok(()) }"
        )
        
        # Should generate the same ID
        assert chunk1.chunk_id == chunk2.chunk_id


class TestDataclassSerialization:
    """Test dataclass serialization and deserialization."""
    
    def test_asdict_conversion(self):
        """Test converting CodeChunk to dictionary using asdict."""
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test():\n    pass",
            chunk_id="test_id",
            parent_chunk_id="parent_id",
            references=["ref1"],
            dependencies=["dep1", "dep2"]
        )
        
        chunk_dict = asdict(chunk)
        
        assert isinstance(chunk_dict, dict)
        assert chunk_dict['language'] == "python"
        assert chunk_dict['file_path'] == "/test/file.py"
        assert chunk_dict['node_type'] == "function"
        assert chunk_dict['start_line'] == 1
        assert chunk_dict['end_line'] == 5
        assert chunk_dict['byte_start'] == 0
        assert chunk_dict['byte_end'] == 100
        assert chunk_dict['parent_context'] == "module"
        assert chunk_dict['content'] == "def test():\n    pass"
        assert chunk_dict['chunk_id'] == "test_id"
        assert chunk_dict['parent_chunk_id'] == "parent_id"
        assert chunk_dict['references'] == ["ref1"]
        assert chunk_dict['dependencies'] == ["dep1", "dep2"]
    
    def test_create_from_dict(self):
        """Test creating CodeChunk from dictionary."""
        chunk_dict = {
            'language': 'javascript',
            'file_path': '/app/index.js',
            'node_type': 'function',
            'start_line': 10,
            'end_line': 20,
            'byte_start': 200,
            'byte_end': 400,
            'parent_context': 'module',
            'content': 'function main() { }',
            'chunk_id': 'js_chunk_1',
            'parent_chunk_id': None,
            'references': ['React', 'useState'],
            'dependencies': ['react', 'lodash']
        }
        
        chunk = CodeChunk(**chunk_dict)
        
        assert chunk.language == 'javascript'
        assert chunk.file_path == '/app/index.js'
        assert chunk.node_type == 'function'
        assert chunk.start_line == 10
        assert chunk.end_line == 20
        assert chunk.byte_start == 200
        assert chunk.byte_end == 400
        assert chunk.parent_context == 'module'
        assert chunk.content == 'function main() { }'
        assert chunk.chunk_id == 'js_chunk_1'
        assert chunk.parent_chunk_id is None
        assert chunk.references == ['React', 'useState']
        assert chunk.dependencies == ['react', 'lodash']
    
    def test_roundtrip_serialization(self):
        """Test that chunk survives dict roundtrip."""
        original = CodeChunk(
            language="c++",
            file_path="/src/main.cpp",
            node_type="class",
            start_line=100,
            end_line=200,
            byte_start=2000,
            byte_end=5000,
            parent_context="namespace",
            content="class Engine { };",
            chunk_id="cpp_class_1",
            parent_chunk_id="namespace_1",
            references=["std::vector", "std::string"],
            dependencies=["iostream", "vector", "string"]
        )
        
        # Convert to dict and back
        chunk_dict = asdict(original)
        reconstructed = CodeChunk(**chunk_dict)
        
        # All fields should match
        assert reconstructed.language == original.language
        assert reconstructed.file_path == original.file_path
        assert reconstructed.node_type == original.node_type
        assert reconstructed.start_line == original.start_line
        assert reconstructed.end_line == original.end_line
        assert reconstructed.byte_start == original.byte_start
        assert reconstructed.byte_end == original.byte_end
        assert reconstructed.parent_context == original.parent_context
        assert reconstructed.content == original.content
        assert reconstructed.chunk_id == original.chunk_id
        assert reconstructed.parent_chunk_id == original.parent_chunk_id
        assert reconstructed.references == original.references
        assert reconstructed.dependencies == original.dependencies
    
    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        chunk = CodeChunk(
            language="rust",
            file_path="/src/lib.rs",
            node_type="function",
            start_line=50,
            end_line=60,
            byte_start=1000,
            byte_end=1200,
            parent_context="impl",
            content="pub fn new() -> Self { }",
            chunk_id="rust_fn_1",
            parent_chunk_id=None,
            references=["Self"],
            dependencies=[]
        )
        
        # Serialize to JSON
        json_str = json.dumps(asdict(chunk), indent=2)
        assert isinstance(json_str, str)
        
        # Deserialize from JSON
        chunk_dict = json.loads(json_str)
        reconstructed = CodeChunk(**chunk_dict)
        
        assert reconstructed.language == chunk.language
        assert reconstructed.content == chunk.content
        assert reconstructed.chunk_id == chunk.chunk_id
        assert reconstructed.parent_chunk_id == chunk.parent_chunk_id
        assert reconstructed.references == chunk.references
        assert reconstructed.dependencies == chunk.dependencies


class TestFieldValidation:
    """Test field validation and edge cases."""
    
    def test_empty_strings(self):
        """Test behavior with empty strings."""
        # Empty content should be allowed
        chunk = CodeChunk(
            language="python",
            file_path="/test/empty.py",
            node_type="module",
            start_line=1,
            end_line=1,
            byte_start=0,
            byte_end=0,
            parent_context="",  # Empty parent context
            content=""  # Empty content
        )
        
        assert chunk.parent_context == ""
        assert chunk.content == ""
        # Should still generate an ID
        assert chunk.chunk_id != ""
    
    def test_line_number_edge_cases(self):
        """Test edge cases for line numbers."""
        # Single line chunk
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="statement",
            start_line=42,
            end_line=42,  # Same as start
            byte_start=100,
            byte_end=120,
            parent_context="function",
            content="return True"
        )
        
        assert chunk.start_line == chunk.end_line == 42
    
    def test_byte_position_edge_cases(self):
        """Test edge cases for byte positions."""
        # Zero-length chunk (theoretical edge case)
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="comment",
            start_line=1,
            end_line=1,
            byte_start=50,
            byte_end=50,  # Same as start
            parent_context="module",
            content=""
        )
        
        assert chunk.byte_start == chunk.byte_end == 50
    
    def test_special_characters_in_content(self):
        """Test handling of special characters in content."""
        special_content = '''def test():
    print("Hello\\nWorld")  # Newline
    path = "C:\\\\Users\\\\test"  # Backslashes
    unicode = "Hello 世界 🌍"  # Unicode
    '''
        
        chunk = CodeChunk(
            language="python",
            file_path="/test/special.py",
            node_type="function",
            start_line=1,
            end_line=4,
            byte_start=0,
            byte_end=len(special_content.encode()),
            parent_context="module",
            content=special_content
        )
        
        # Content should be preserved exactly
        assert chunk.content == special_content
        
        # Should serialize/deserialize correctly
        chunk_dict = asdict(chunk)
        reconstructed = CodeChunk(**chunk_dict)
        assert reconstructed.content == special_content
    
    def test_none_parent_chunk_id(self):
        """Test None value for parent_chunk_id."""
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="module",
            start_line=1,
            end_line=100,
            byte_start=0,
            byte_end=2000,
            parent_context="",
            content="# module content",
            parent_chunk_id=None  # Explicitly None
        )
        
        assert chunk.parent_chunk_id is None
        
        # Should serialize correctly
        chunk_dict = asdict(chunk)
        assert chunk_dict['parent_chunk_id'] is None
    
    def test_empty_lists(self):
        """Test empty lists for references and dependencies."""
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass",
            references=[],
            dependencies=[]
        )
        
        assert chunk.references == []
        assert chunk.dependencies == []
        
        # Lists should remain empty after serialization
        chunk_dict = asdict(chunk)
        assert chunk_dict['references'] == []
        assert chunk_dict['dependencies'] == []


class TestDataclassFeatures:
    """Test dataclass-specific features."""
    
    def test_equality(self):
        """Test CodeChunk equality comparison."""
        chunk1 = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass"
        )
        
        chunk2 = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass"
        )
        
        # Should be equal (same auto-generated IDs)
        assert chunk1 == chunk2
        assert chunk1.chunk_id == chunk2.chunk_id
        
        # Different content should make them unequal
        chunk3 = replace(chunk1, content="def test2(): pass")
        assert chunk1 != chunk3
    
    def test_replace(self):
        """Test using dataclasses.replace."""
        original = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass",
            chunk_id="original_id"
        )
        
        # Replace some fields
        modified = replace(
            original,
            start_line=10,
            end_line=15,
            content="def modified(): pass"
        )
        
        # Check modified fields
        assert modified.start_line == 10
        assert modified.end_line == 15
        assert modified.content == "def modified(): pass"
        
        # Check unmodified fields
        assert modified.language == original.language
        assert modified.file_path == original.file_path
        assert modified.node_type == original.node_type
        assert modified.chunk_id == original.chunk_id  # Keeps original ID
    
    def test_field_defaults(self):
        """Test field default values."""
        # Create chunk with minimal fields
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass"
        )
        
        # Check defaults
        assert chunk.chunk_id != ""  # Auto-generated
        assert chunk.parent_chunk_id is None
        assert chunk.references == []
        assert chunk.dependencies == []
        
        # Verify these are mutable lists (not shared)
        chunk.references.append("ref1")
        chunk.dependencies.extend(["dep1", "dep2"])
        
        # Create another chunk to verify lists aren't shared
        chunk2 = CodeChunk(
            language="python",
            file_path="/test/file2.py",
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test2(): pass"
        )
        
        assert chunk2.references == []  # Should be empty
        assert chunk2.dependencies == []  # Should be empty


class TestTypeCompatibility:
    """Test type compatibility and coercion."""
    
    def test_accept_path_like_objects(self):
        """Test that file_path can accept path-like strings."""
        from pathlib import Path
        
        # Should accept string representation of Path
        path = Path("/test/file.py")
        chunk = CodeChunk(
            language="python",
            file_path=str(path),  # Convert to string
            node_type="function",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass"
        )
        
        assert chunk.file_path == "/test/file.py"
    
    def test_type_flexibility(self):
        """Test that dataclasses don't enforce runtime type checking."""
        # Python dataclasses don't enforce types at runtime
        # This is actually valid (though not recommended)
        chunk = CodeChunk(
            language="python",
            file_path="/test/file.py",
            node_type="function",
            start_line="1",  # String instead of int - allowed but not recommended
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass"
        )
        
        # The chunk is created, but with wrong type
        assert chunk.start_line == "1"  # It's a string, not int
        assert chunk.end_line == 5  # This is still int
        
        # However, operations expecting int will fail
        with pytest.raises(TypeError):
            # This will fail because "1" + 1 is invalid
            _ = chunk.start_line + 1


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    def test_nested_function_chunks(self):
        """Test representing nested functions."""
        # Outer function
        outer = CodeChunk(
            language="python",
            file_path="/app/utils.py",
            node_type="function",
            start_line=10,
            end_line=20,
            byte_start=150,
            byte_end=400,
            parent_context="module",
            content="def outer():\n    def inner():\n        pass",
            chunk_id="outer_func"
        )
        
        # Inner function
        inner = CodeChunk(
            language="python",
            file_path="/app/utils.py",
            node_type="function",
            start_line=11,
            end_line=12,
            byte_start=180,
            byte_end=220,
            parent_context="function:outer",
            content="def inner():\n        pass",
            parent_chunk_id="outer_func"
        )
        
        assert inner.parent_chunk_id == outer.chunk_id
        assert "outer" in inner.parent_context
    
    def test_class_with_methods(self):
        """Test representing a class with multiple methods."""
        # Class chunk
        class_chunk = CodeChunk(
            language="python",
            file_path="/app/models.py",
            node_type="class",
            start_line=50,
            end_line=100,
            byte_start=1000,
            byte_end=3000,
            parent_context="module",
            content="class User:\n    ...",
            chunk_id="user_class"
        )
        
        # Method chunks
        init_method = CodeChunk(
            language="python",
            file_path="/app/models.py",
            node_type="function",
            start_line=52,
            end_line=55,
            byte_start=1050,
            byte_end=1200,
            parent_context="class:User",
            content="def __init__(self, name):\n    self.name = name",
            parent_chunk_id="user_class",
            references=["self"]
        )
        
        str_method = CodeChunk(
            language="python",
            file_path="/app/models.py",
            node_type="function",
            start_line=57,
            end_line=59,
            byte_start=1250,
            byte_end=1350,
            parent_context="class:User",
            content="def __str__(self):\n    return self.name",
            parent_chunk_id="user_class",
            references=["self"],
            dependencies=["__init__"]
        )
        
        # Verify relationships
        assert init_method.parent_chunk_id == class_chunk.chunk_id
        assert str_method.parent_chunk_id == class_chunk.chunk_id
        assert "__init__" in str_method.dependencies
    
    def test_module_with_imports(self):
        """Test representing a module with imports and dependencies."""
        chunk = CodeChunk(
            language="python",
            file_path="/app/main.py",
            node_type="module",
            start_line=1,
            end_line=200,
            byte_start=0,
            byte_end=5000,
            parent_context="",
            content="import os\nimport sys\nfrom typing import List\n...",
            dependencies=["os", "sys", "typing"],
            references=["List"]
        )
        
        assert "os" in chunk.dependencies
        assert "sys" in chunk.dependencies
        assert "typing" in chunk.dependencies
        assert "List" in chunk.references
    
    def test_javascript_arrow_function(self):
        """Test representing JavaScript arrow functions."""
        chunk = CodeChunk(
            language="javascript",
            file_path="/app/handlers.js",
            node_type="arrow_function",
            start_line=25,
            end_line=30,
            byte_start=500,
            byte_end=650,
            parent_context="module",
            content="const handleClick = (event) => {\n  console.log(event);\n}",
            chunk_id="handle_click",
            references=["console", "event"]
        )
        
        assert chunk.node_type == "arrow_function"
        assert "console" in chunk.references
        assert "event" in chunk.references


class TestLargeScaleData:
    """Test handling of large-scale data."""
    
    def test_large_content(self):
        """Test chunk with large content."""
        # Create a large content string (10KB)
        large_content = "x" * 10_000
        
        chunk = CodeChunk(
            language="text",
            file_path="/test/large.txt",
            node_type="file",
            start_line=1,
            end_line=1000,
            byte_start=0,
            byte_end=10_000,
            parent_context="",
            content=large_content
        )
        
        assert len(chunk.content) == 10_000
        
        # Should serialize correctly
        chunk_dict = asdict(chunk)
        assert len(chunk_dict['content']) == 10_000
        
        # JSON serialization should work
        json_str = json.dumps(chunk_dict)
        assert large_content in json_str
    
    def test_many_dependencies(self):
        """Test chunk with many dependencies and references."""
        # Create lists with many items
        deps = [f"dependency_{i}" for i in range(100)]
        refs = [f"reference_{i}" for i in range(100)]
        
        chunk = CodeChunk(
            language="python",
            file_path="/test/complex.py",
            node_type="module",
            start_line=1,
            end_line=5000,
            byte_start=0,
            byte_end=100_000,
            parent_context="",
            content="# Complex module",
            dependencies=deps,
            references=refs
        )
        
        assert len(chunk.dependencies) == 100
        assert len(chunk.references) == 100
        assert chunk.dependencies[50] == "dependency_50"
        assert chunk.references[75] == "reference_75"
    
    def test_batch_creation_performance(self):
        """Test creating many chunks efficiently."""
        # Create 1000 chunks
        chunks = []
        for i in range(1000):
            chunk = CodeChunk(
                language="python",
                file_path=f"/test/file_{i}.py",
                node_type="function",
                start_line=i * 10,
                end_line=i * 10 + 5,
                byte_start=i * 100,
                byte_end=i * 100 + 50,
                parent_context="module",
                content=f"def function_{i}(): pass"
            )
            chunks.append(chunk)
        
        assert len(chunks) == 1000
        # All should have unique IDs
        ids = {c.chunk_id for c in chunks}
        assert len(ids) == 1000
        
        # Test serialization of all chunks
        all_dicts = [asdict(c) for c in chunks]
        assert len(all_dicts) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
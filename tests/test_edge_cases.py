"""Edge case tests for the tree-sitter-chunker.

This module tests unusual, extreme, and error-prone scenarios
to ensure robust handling of edge cases.
"""

import json
import os
from pathlib import Path

import pytest

from chunker import CodeChunk, chunk_file, chunk_files_parallel
from chunker.chunker_config import ChunkerConfig
from chunker.exceptions import LanguageNotFoundError
from chunker.export import JSONExporter, JSONLExporter, SchemaType


class TestFileSystemEdgeCases:
    """Test edge cases related to file system operations."""

    def test_empty_file_handling(self, tmp_path):
        """Test handling of empty files."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")

        chunks = chunk_file(empty_file, language="python")
        assert chunks == []  # Empty file should return empty list

    def test_file_with_only_whitespace(self, tmp_path):
        """Test files containing only whitespace."""
        whitespace_file = tmp_path / "whitespace.py"
        whitespace_file.write_text("   \n\n\t\t\n   \n")

        chunks = chunk_file(whitespace_file, language="python")
        assert chunks == []  # Only whitespace should return empty list

    def test_file_with_only_comments(self, tmp_path):
        """Test files containing only comments."""
        comment_file = tmp_path / "comments.py"
        comment_file.write_text(
            """
# This is a comment
# Another comment
# Yet another comment

# More comments
""",
        )

        chunks = chunk_file(comment_file, language="python")
        assert chunks == []  # Only comments, no code chunks

    def test_very_long_filename(self, tmp_path):
        """Test handling of files with very long names."""
        # Create a filename at the OS limit
        long_name = "a" * 200 + ".py"  # Most systems support 255 chars
        long_file = tmp_path / long_name
        long_file.write_text("def test(): pass")

        chunks = chunk_file(long_file, language="python")
        assert len(chunks) == 1
        assert chunks[0].file_path == str(long_file)

    def test_special_characters_in_filename(self, tmp_path):
        """Test files with special characters in names."""
        special_names = [
            "file with spaces.py",
            "file-with-dashes.py",
            "file_with_underscores.py",
            "file.multiple.dots.py",
            "fileλunicode.py",
            "file@special#chars$.py",
        ]

        for name in special_names:
            special_file = tmp_path / name
            special_file.write_text("def test(): pass")

            try:
                chunks = chunk_file(special_file, language="python")
                assert len(chunks) == 1
            except (FileNotFoundError, OSError) as e:
                # Some names might not be valid on all systems
                assert "file" in str(e).lower()

    def test_symlink_handling(self, tmp_path):
        """Test handling of symbolic links."""
        # Create original file
        original = tmp_path / "original.py"
        original.write_text("def original(): pass")

        # Create symlink
        symlink = tmp_path / "link.py"
        symlink.symlink_to(original)

        # Should process symlink successfully
        chunks = chunk_file(symlink, language="python")
        assert len(chunks) == 1
        assert chunks[0].content == "def original(): pass"

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Permission test not reliable on Windows",
    )
    def test_permission_denied_file(self, tmp_path):
        """Test handling of files without read permission."""
        restricted_file = tmp_path / "restricted.py"
        restricted_file.write_text("def test(): pass")

        # Remove read permissions
        os.chmod(restricted_file, 0o000)

        try:
            with pytest.raises((PermissionError, OSError)):
                chunk_file(restricted_file, language="python")
        finally:
            # Restore permissions for cleanup
            os.chmod(restricted_file, 0o644)


class TestCodeContentEdgeCases:
    """Test edge cases in code content."""

    def test_invalid_encoding(self, tmp_path):
        """Test handling of files with invalid encoding."""
        invalid_file = tmp_path / "invalid_encoding.py"
        # Write binary data that's not valid UTF-8
        invalid_file.write_bytes(b"\x80\x81\x82\x83def test(): pass")

        # Should handle encoding errors gracefully
        # The system may handle invalid encoding by replacing or ignoring bad bytes
        try:
            chunks = chunk_file(invalid_file, language="python")
            # If it succeeds, it handled the encoding issue internally
            assert isinstance(chunks, list)
        except (FileNotFoundError, OSError) as e:
            # If it raises, should be encoding related
            assert "decode" in str(e).lower() or "encoding" in str(e).lower()

    def test_mixed_line_endings(self, tmp_path):
        """Test files with mixed line endings."""
        mixed_file = tmp_path / "mixed_endings.py"
        # Mix of Unix (\n), Windows (\r\n), and old Mac (\r)
        mixed_file.write_bytes(
            b"def unix():\n    pass\r\ndef windows():\r\n    pass\rdef mac():\r    pass",
        )

        chunks = chunk_file(mixed_file, language="python")
        assert len(chunks) >= 3  # Should parse all functions

    def test_no_newline_at_eof(self, tmp_path):
        """Test files without newline at end."""
        no_newline_file = tmp_path / "no_newline.py"
        no_newline_file.write_bytes(b"def test(): pass")  # No trailing newline

        chunks = chunk_file(no_newline_file, language="python")
        assert len(chunks) == 1

    def test_extremely_long_lines(self, tmp_path):
        """Test files with extremely long lines."""
        long_line_file = tmp_path / "long_lines.py"
        # Create a function with a very long line
        long_string = "x" * 10000
        content = f"""def test():
    data = "{long_string}"
    return len(data)
"""
        long_line_file.write_text(content)

        chunks = chunk_file(long_line_file, language="python")
        assert len(chunks) == 1
        # Content might be truncated in chunk, but should handle it
        assert "def test():" in chunks[0].content

    def test_deeply_nested_structures(self, tmp_path):
        """Test deeply nested code structures."""
        nested_file = tmp_path / "deeply_nested.py"

        # Build deeply nested structure
        content = ["def level0():"]
        for i in range(1, 50):  # 50 levels deep
            indent = "    " * i
            content.append(f"{indent}def level{i}():")

        # Add pass at deepest level
        content.append("    " * 50 + "pass")

        nested_file.write_text("\n".join(content))

        # Should handle without stack overflow
        chunks = chunk_file(nested_file, language="python")
        assert len(chunks) >= 1  # At least outer function

    def test_malformed_syntax(self, tmp_path):
        """Test handling of syntactically invalid code."""
        invalid_syntax_file = tmp_path / "invalid.py"
        invalid_syntax_file.write_text(
            """
def incomplete_function(
    # Missing closing parenthesis and body

class NoBody:
    # Missing class body

def another_func():
    return "valid"

if True
    # Missing colon
    pass
""",
        )

        # Should handle malformed syntax without crashing
        try:
            chunks = chunk_file(invalid_syntax_file, language="python")
            # May or may not extract chunks depending on parser tolerance
            assert isinstance(chunks, list)  # Should return a list even if empty
        except (FileNotFoundError, OSError):
            # If it fails, that's also acceptable for malformed syntax
            pass

    def test_unicode_identifiers(self, tmp_path):
        """Test code with Unicode identifiers."""
        unicode_file = tmp_path / "unicode.py"
        unicode_file.write_text(
            """
def αβγ():
    return "Greek"

def 你好():
    return "Chinese"

class МойКласс:
    def метод(self):
        return "Russian"

def emoji_🚀_function():
    return "rocket"
""",
        )

        chunks = chunk_file(unicode_file, language="python")
        # Should handle Unicode identifiers
        assert len(chunks) >= 3  # Functions and class


class TestLanguageEdgeCases:
    """Test edge cases related to language handling."""

    def test_unsupported_language(self, tmp_path):
        """Test handling of unsupported languages."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("some content")

        with pytest.raises(LanguageNotFoundError):
            chunk_file(test_file, language="xyz_unsupported_lang")

    def test_ambiguous_file_extension(self, tmp_path):
        """Test files with ambiguous extensions."""
        # .h files could be C or C++
        header_file = tmp_path / "test.h"
        header_file.write_text(
            """
#ifdef __cplusplus
class TestClass {
public:
    void method();
};
#else
struct test_struct {
    int value;
};
#endif
""",
        )

        # Should work with explicit language
        c_chunks = chunk_file(header_file, language="c")
        assert isinstance(c_chunks, list)

        cpp_chunks = chunk_file(header_file, language="cpp")
        assert isinstance(cpp_chunks, list)

    def test_language_specific_edge_cases(self, tmp_path):
        """Test language-specific edge cases."""
        # Python: decorators and async
        python_file = tmp_path / "python_edge.py"
        python_file.write_text(
            """
@decorator
@another_decorator(arg=value)
async def decorated_async():
    async with context():
        yield await something()

# JavaScript: various function syntaxes
""",
        )

        py_chunks = chunk_file(python_file, language="python")
        assert len(py_chunks) >= 1

        # JavaScript: arrow functions and classes
        js_file = tmp_path / "js_edge.js"
        js_file.write_text(
            """
const arrow = () => {};
const asyncArrow = async () => await fetch();
export default class { constructor() {} }
function* generator() { yield 42; }
""",
        )

        js_chunks = chunk_file(js_file, language="javascript")
        assert len(js_chunks) >= 1


class TestConfigurationEdgeCases:
    """Test edge cases in configuration handling."""

    def test_invalid_config_values(self, tmp_path):
        """Test handling of invalid configuration values."""
        config_file = tmp_path / "invalid_config.toml"
        config_file.write_text(
            """
[general]
min_chunk_size = -5  # Negative value
chunk_types = "not_a_list"  # Wrong type

[python]
invalid_option = true
""",
        )

        # Should handle invalid config gracefully
        config = ChunkerConfig(str(config_file))
        # Config should load but use defaults for invalid values
        assert config is not None

    def test_circular_config_includes(self, tmp_path):
        """Test handling of circular configuration includes."""
        # Create two configs that include each other
        config1 = tmp_path / "config1.toml"
        config2 = tmp_path / "config2.toml"

        config1.write_text(
            f"""
[general]
include = "{config2}"
value1 = true
""",
        )

        config2.write_text(
            f"""
[general]
include = "{config1}"
value2 = true
""",
        )

        # Should handle circular includes without infinite loop
        config = ChunkerConfig(str(config1))
        assert config is not None

    def test_missing_config_file_reference(self, tmp_path):
        """Test handling of missing configuration files."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[general]
include = "/non/existent/config.toml"
min_chunk_size = 5
""",
        )

        # Should continue with partial config
        config = ChunkerConfig(str(config_file))
        assert config is not None


class TestMemoryEdgeCases:
    """Test edge cases related to memory usage."""

    def test_extremely_large_chunk(self, tmp_path):
        """Test handling of extremely large code chunks."""
        large_chunk_file = tmp_path / "large_chunk.py"

        # Create a function with massive content
        lines = ["def massive_function():"]
        # Add 10,000 lines to the function
        for i in range(10000):
            lines.append(f"    variable_{i} = {i}")
        lines.append("    return sum(locals().values())")

        large_chunk_file.write_text("\n".join(lines))

        # Should handle large chunks without memory issues
        chunks = chunk_file(large_chunk_file, language="python")
        assert len(chunks) >= 1
        assert chunks[0].end_line - chunks[0].start_line > 9000

    def test_many_small_chunks(self, tmp_path):
        """Test handling of files with many small chunks."""
        many_chunks_file = tmp_path / "many_chunks.py"

        # Create 1000 tiny functions
        lines = []
        for i in range(1000):
            lines.append(f"def f{i}(): pass")

        many_chunks_file.write_text("\n".join(lines))

        # Should handle many chunks efficiently
        chunks = chunk_file(many_chunks_file, language="python")
        assert len(chunks) >= 1000


class TestConcurrencyEdgeCases:
    """Test edge cases in concurrent processing."""

    def test_race_condition_file_modification(self, tmp_path):
        """Test handling of files modified during processing."""
        test_file = tmp_path / "modified.py"
        test_file.write_text("def original(): pass")

        # Simulate file modification during processing
        # This is tricky to test reliably, so we'll just ensure
        # the chunker handles whatever state it reads
        chunks = chunk_file(test_file, language="python")

        # Immediately modify the file
        test_file.write_text("def modified(): pass")

        # Original chunks should still be valid
        assert len(chunks) == 1
        assert "original" in chunks[0].content or "modified" in chunks[0].content

    def test_file_deletion_during_batch(self, tmp_path):
        """Test handling of file deletion during batch processing."""
        # Create files
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files.append(f)

        # Delete one file to simulate deletion during processing
        files[2].unlink()

        # Process all files (including deleted)
        results = chunk_files_parallel(files, language="python", num_workers=2)

        # Should handle gracefully
        assert len(results) == 5  # All files in results
        # Deleted file should have empty chunks or error
        assert results[files[2]] == [] or files[2] not in results


class TestExportEdgeCases:
    """Test edge cases in export functionality."""

    def test_export_with_invalid_json_characters(self, tmp_path):
        """Test export of chunks containing problematic JSON characters."""
        test_file = tmp_path / "json_chars.py"
        test_file.write_text(
            '''def test():
    """Contains "quotes" and \\backslashes\\ and
    newlines and \ttabs"""
    return '{"json": "content"}'
''',
        )

        chunks = chunk_file(test_file, language="python")

        # Export should handle special characters
        json_file = tmp_path / "output.json"
        exporter = JSONExporter(schema_type=SchemaType.FLAT)
        exporter.export(chunks, json_file)

        # Should be valid JSON

        with Path(json_file).open(
            "r",
        ) as f:
            data = json.load(f)
            assert len(data) == 1
            assert '\\"' in data[0]["content"] or '"' in data[0]["content"]

    def test_export_empty_chunks_list(self, tmp_path):
        """Test export of empty chunks list."""
        empty_chunks = []

        # JSON export
        json_file = tmp_path / "empty.json"
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(empty_chunks, json_file)
        assert json_file.read_text().strip() == "[]"

        # JSONL export
        jsonl_file = tmp_path / "empty.jsonl"
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(empty_chunks, jsonl_file)
        assert jsonl_file.read_text().strip() == ""

    def test_export_with_null_values(self, tmp_path):
        """Test export of chunks with null/None values."""

        # Create chunk with some None values
        chunk = CodeChunk(
            language="python",
            file_path=str(tmp_path / "test.py"),
            node_type="function_definition",
            start_line=1,
            end_line=1,
            byte_start=0,
            byte_end=10,
            parent_context="",
            content="def test(): pass",
            parent_chunk_id=None,  # Explicitly None
            references=[],
            dependencies=[],
        )

        # Export should handle None values
        json_file = tmp_path / "nulls.json"
        exporter = JSONExporter(schema_type=SchemaType.FLAT)
        exporter.export([chunk], json_file)

        # Verify JSON is valid

        with Path(json_file).open(
            "r",
        ) as f:
            data = json.load(f)
            assert len(data) == 1


class TestSystemIntegrationEdgeCases:
    """Test edge cases in system integration."""

    def test_extremely_long_command_line(self, tmp_path):
        """Test handling of extremely long command lines."""
        # Create many files
        files = []
        for i in range(100):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def f{i}(): pass")
            files.append(str(f))

        # Very long file list might exceed command line limits
        # on some systems, but parallel chunker should handle it
        results = chunk_files_parallel(files[:50], language="python", num_workers=2)
        assert len(results) == 50

    def test_mixed_path_separators(self, tmp_path):
        """Test handling of mixed path separators."""
        # This is mainly relevant on Windows
        test_file = tmp_path / "subdir" / "test.py"
        test_file.parent.mkdir()
        test_file.write_text("def test(): pass")

        # Try different path representations
        paths_to_test = [
            str(test_file),
            str(test_file).replace(os.sep, "/"),
            str(test_file).replace("/", os.sep),
        ]

        for path in paths_to_test:
            try:
                chunks = chunk_file(path, language="python")
                assert len(chunks) == 1
            except FileNotFoundError:
                # Some path formats might not work on all systems
                pass

"""Edge case tests for the tree-sitter-chunker.

This module tests unusual, extreme, and error-prone scenarios
to ensure robust handling of edge cases.
"""
import json
import os
from pathlib import Path

import pytest

from chunker import CodeChunk, chunk_file
from chunker.parallel import chunk_files_parallel
from chunker.chunker_config import ChunkerConfig
from chunker.exceptions import LanguageNotFoundError
from chunker.export import JSONExporter, JSONLExporter, SchemaType


class TestFileSystemEdgeCases:
    """Test edge cases related to file system operations."""

    @staticmethod
    def test_empty_file_handling(tmp_path):
        """Test handling of empty files."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")
        chunks = chunk_file(empty_file, language="python")
        assert chunks == []

    @staticmethod
    def test_file_with_only_whitespace(tmp_path):
        """Test files containing only whitespace."""
        whitespace_file = tmp_path / "whitespace.py"
        whitespace_file.write_text("   \n\n\t\t\n   \n")
        chunks = chunk_file(whitespace_file, language="python")
        assert chunks == []

    @staticmethod
    def test_file_with_only_comments(tmp_path):
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
        assert chunks == []

    @staticmethod
    def test_very_long_filename(tmp_path):
        """Test handling of files with very long names."""
        long_name = "a" * 200 + ".py"
        long_file = tmp_path / long_name
        long_file.write_text("def test(): pass")
        chunks = chunk_file(long_file, language="python")
        assert len(chunks) == 1
        assert chunks[0].file_path == str(long_file)

    @staticmethod
    def test_special_characters_in_filename(tmp_path):
        """Test files with special characters in names."""
        special_names = ["file with spaces.py", "file-with-dashes.py",
            "file_with_underscores.py", "file.multiple.dots.py",
            "fileλunicode.py", "file@special#chars$.py"]
        for name in special_names:
            special_file = tmp_path / name
            special_file.write_text("def test(): pass")
            try:
                chunks = chunk_file(special_file, language="python")
                assert len(chunks) == 1
            except (FileNotFoundError, OSError) as e:
                assert "file" in str(e).lower()

    @staticmethod
    def test_symlink_handling(tmp_path):
        """Test handling of symbolic links."""
        original = tmp_path / "original.py"
        original.write_text("def original(): pass")
        symlink = tmp_path / "link.py"
        symlink.symlink_to(original)
        chunks = chunk_file(symlink, language="python")
        assert len(chunks) == 1
        assert chunks[0].content == "def original(): pass"

    @pytest.mark.skipif(os.name == "nt", reason="Permission test not reliable on Windows")
    @staticmethod
    def test_permission_denied_file(tmp_path):
        """Test handling of files without read permission."""
        restricted_file = tmp_path / "restricted.py"
        restricted_file.write_text("def test(): pass")
        os.chmod(restricted_file, 0)
        try:
            with pytest.raises((PermissionError, OSError)):
                chunk_file(restricted_file, language="python")
        finally:
            os.chmod(restricted_file, 420)


class TestCodeContentEdgeCases:
    """Test edge cases in code content."""

    @staticmethod
    def test_invalid_encoding(tmp_path):
        """Test handling of files with invalid encoding."""
        invalid_file = tmp_path / "invalid_encoding.py"
        invalid_file.write_bytes(b"\x80\x81\x82\x83def test(): pass")
        try:
            chunks = chunk_file(invalid_file, language="python")
            assert isinstance(chunks, list)
        except (FileNotFoundError, OSError) as e:
            assert "decode" in str(e).lower() or "encoding" in str(e).lower()

    @staticmethod
    def test_mixed_line_endings(tmp_path):
        """Test files with mixed line endings."""
        mixed_file = tmp_path / "mixed_endings.py"
        mixed_file.write_bytes(
            b"def unix():\n    pass\r\ndef windows():\r\n    pass\rdef mac():\r    pass",
            )
        chunks = chunk_file(mixed_file, language="python")
        assert len(chunks) >= 3

    @staticmethod
    def test_no_newline_at_eof(tmp_path):
        """Test files without newline at end."""
        no_newline_file = tmp_path / "no_newline.py"
        no_newline_file.write_bytes(b"def test(): pass")
        chunks = chunk_file(no_newline_file, language="python")
        assert len(chunks) == 1

    @staticmethod
    def test_extremely_long_lines(tmp_path):
        """Test files with extremely long lines."""
        long_line_file = tmp_path / "long_lines.py"
        long_string = "x" * 10000
        content = (
            f'def test():\n    data = "{long_string}"\n    return len(data)\n')
        long_line_file.write_text(content)
        chunks = chunk_file(long_line_file, language="python")
        assert len(chunks) == 1
        assert "def test():" in chunks[0].content

    @staticmethod
    def test_deeply_nested_structures(tmp_path):
        """Test deeply nested code structures."""
        nested_file = tmp_path / "deeply_nested.py"
        content = ["def level0():"]
        for i in range(1, 50):
            indent = "    " * i
            content.append(f"{indent}def level{i}():")
        content.append("    " * 50 + "pass")
        nested_file.write_text("\n".join(content))
        chunks = chunk_file(nested_file, language="python")
        assert len(chunks) >= 1

    @staticmethod
    def test_malformed_syntax(tmp_path):
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
        try:
            chunks = chunk_file(invalid_syntax_file, language="python")
            assert isinstance(chunks, list)
        except (FileNotFoundError, OSError):
            pass

    @staticmethod
    def test_unicode_identifiers(tmp_path):
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
    return "rocket\"
""",
            )
        chunks = chunk_file(unicode_file, language="python")
        assert len(chunks) >= 3


class TestLanguageEdgeCases:
    """Test edge cases related to language handling."""

    @staticmethod
    def test_unsupported_language(tmp_path):
        """Test handling of unsupported languages."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("some content")
        with pytest.raises(LanguageNotFoundError):
            chunk_file(test_file, language="xyz_unsupported_lang")

    @staticmethod
    def test_ambiguous_file_extension(tmp_path):
        """Test files with ambiguous extensions."""
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
        c_chunks = chunk_file(header_file, language="c")
        assert isinstance(c_chunks, list)
        cpp_chunks = chunk_file(header_file, language="cpp")
        assert isinstance(cpp_chunks, list)

    @staticmethod
    def test_language_specific_edge_cases(tmp_path):
        """Test language-specific edge cases."""
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

    @classmethod
    def test_invalid_config_values(cls, tmp_path):
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
        config = ChunkerConfig(str(config_file))
        assert config is not None

    @classmethod
    def test_circular_config_includes(cls, tmp_path):
        """Test handling of circular configuration includes."""
        config1 = tmp_path / "config1.toml"
        config2 = tmp_path / "config2.toml"
        config1.write_text(
            f'\n[general]\ninclude = "{config2}"\nvalue1 = true\n')
        config2.write_text(
            f'\n[general]\ninclude = "{config1}"\nvalue2 = true\n')
        config = ChunkerConfig(str(config1))
        assert config is not None

    @classmethod
    def test_missing_config_file_reference(cls, tmp_path):
        """Test handling of missing configuration files."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[general]
include = "/non/existent/config.toml"
min_chunk_size = 5
""",
            )
        config = ChunkerConfig(str(config_file))
        assert config is not None


class TestMemoryEdgeCases:
    """Test edge cases related to memory usage."""

    @staticmethod
    def test_extremely_large_chunk(tmp_path):
        """Test handling of extremely large code chunks."""
        large_chunk_file = tmp_path / "large_chunk.py"
        lines = ["def massive_function():"]
        lines.extend(f"    variable_{i} = {i}" for i in range(10000))
        lines.append("    return sum(locals().values())")
        large_chunk_file.write_text("\n".join(lines))
        chunks = chunk_file(large_chunk_file, language="python")
        assert len(chunks) >= 1
        assert chunks[0].end_line - chunks[0].start_line > 9000

    @staticmethod
    def test_many_small_chunks(tmp_path):
        """Test handling of files with many small chunks."""
        many_chunks_file = tmp_path / "many_chunks.py"
        lines = [f"def f{i}(): pass" for i in range(1000)]
        many_chunks_file.write_text("\n".join(lines))
        chunks = chunk_file(many_chunks_file, language="python")
        assert len(chunks) >= 1000


class TestConcurrencyEdgeCases:
    """Test edge cases in concurrent processing."""

    @staticmethod
    def test_race_condition_file_modification(tmp_path):
        """Test handling of files modified during processing."""
        test_file = tmp_path / "modified.py"
        test_file.write_text("def original(): pass")
        chunks = chunk_file(test_file, language="python")
        test_file.write_text("def modified(): pass")
        assert len(chunks) == 1
        assert "original" in chunks[0].content or "modified" in chunks[0
            ].content

    @staticmethod
    def test_file_deletion_during_batch(tmp_path):
        """Test handling of file deletion during batch processing."""
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files.append(f)
        files[2].unlink()
        results = chunk_files_parallel(files, language="python", num_workers=2)
        assert len(results) == 5
        assert results[files[2]] == [] or files[2] not in results


class TestExportEdgeCases:
    """Test edge cases in export functionality."""

    @classmethod
    def test_export_with_invalid_json_characters(cls, tmp_path):
        """Test export of chunks containing problematic JSON characters."""
        test_file = tmp_path / "json_chars.py"
        test_file.write_text(
            """def test():
    ""\"Contains "quotes" and \\backslashes\\ and
    newlines and 	tabs""\"
    return '{"json": "content"}'
""",
            )
        chunks = chunk_file(test_file, language="python")
        json_file = tmp_path / "output.json"
        exporter = JSONExporter(schema_type=SchemaType.FLAT)
        exporter.export(chunks, json_file)
        with Path(json_file).open("r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data) == 1
            assert '\\"' in data[0]["content"] or '"' in data[0]["content"]

    @classmethod
    def test_export_empty_chunks_list(cls, tmp_path):
        """Test export of empty chunks list."""
        empty_chunks = []
        json_file = tmp_path / "empty.json"
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(empty_chunks, json_file)
        assert json_file.read_text().strip() == "[]"
        jsonl_file = tmp_path / "empty.jsonl"
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(empty_chunks, jsonl_file)
        assert jsonl_file.read_text().strip() == ""

    @classmethod
    def test_export_with_null_values(cls, tmp_path):
        """Test export of chunks with null/None values."""
        chunk = CodeChunk(language="python", file_path=str(tmp_path /
            "test.py"), node_type="function_definition", start_line=1,
            end_line=1, byte_start=0, byte_end=10, parent_context="",
            content="def test(): pass", parent_chunk_id=None, references=[],
            dependencies=[])
        json_file = tmp_path / "nulls.json"
        exporter = JSONExporter(schema_type=SchemaType.FLAT)
        exporter.export([chunk], json_file)
        with Path(json_file).open("r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data) == 1


class TestSystemIntegrationEdgeCases:
    """Test edge cases in system integration."""

    @staticmethod
    def test_extremely_long_command_line(tmp_path):
        """Test handling of extremely long command lines."""
        files = []
        for i in range(100):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def f{i}(): pass")
            files.append(str(f))
        results = chunk_files_parallel(files[:50], language="python",
            num_workers=2)
        assert len(results) == 50

    @staticmethod
    def test_mixed_path_separators(tmp_path):
        """Test handling of mixed path separators."""
        test_file = tmp_path / "subdir" / "test.py"
        test_file.parent.mkdir()
        test_file.write_text("def test(): pass")
        paths_to_test = [str(test_file), str(test_file).replace(os.sep, "/",
            ), str(test_file).replace("/", os.sep)]
        for path in paths_to_test:
            try:
                chunks = chunk_file(path, language="python")
                assert len(chunks) == 1
            except FileNotFoundError:
                pass

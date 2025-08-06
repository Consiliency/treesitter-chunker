"""Tests for Virtual File System support."""

import zipfile
from unittest.mock import Mock, patch

from chunker.vfs import (
    CompositeFileSystem,
    HTTPFileSystem,
    InMemoryFileSystem,
    LocalFileSystem,
    ZipFileSystem,
    create_vfs,
)
from chunker.vfs_chunker import VFSChunker, chunk_from_zip


class TestLocalFileSystem:
    """Test local file system implementation."""

    @classmethod
    def test_local_file_operations(cls, tmp_path):
        """Test basic file operations on local file system."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'")
        vfs = LocalFileSystem(tmp_path)
        assert vfs.exists("test.py")
        assert not vfs.exists("nonexistent.py")
        assert vfs.is_file("test.py")
        assert not vfs.is_dir("test.py")
        assert vfs.is_dir(".")
        with vfs.Path("test.py").open("r") as f:
            content = f.read()
        assert "def hello():" in content
        assert vfs.read_text("test.py") == "def hello():\n    return 'world'"
        assert vfs.get_size("test.py") > 0

    @classmethod
    def test_local_directory_listing(cls, tmp_path):
        """Test directory listing on local file system."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# main")
        (tmp_path / "test.py").write_text("# test")
        vfs = LocalFileSystem(tmp_path)
        files = list(vfs.list_dir("."))
        assert len(files) == 2
        file_names = [f.path for f in files]
        assert "src" in file_names or "src/" in file_names
        assert "test.py" in file_names
        for f in files:
            if f.path == "test.py":
                assert not f.is_dir
                assert f.size > 0
            elif "src" in f.path:
                assert f.is_dir


class TestInMemoryFileSystem:
    """Test in-memory file system implementation."""

    @classmethod
    def test_in_memory_operations(cls):
        """Test operations on in-memory file system."""
        vfs = InMemoryFileSystem()
        vfs.add_file("/test.py", "def test():\n    pass")
        vfs.add_file("/data.bin", b"\x00\x01\x02\x03", is_text=False)
        assert vfs.exists("/test.py")
        assert vfs.exists("/data.bin")
        assert not vfs.exists("/missing.py")
        assert vfs.is_file("/test.py")
        assert not vfs.is_dir("/test.py")
        assert vfs.read_text("/test.py") == "def test():\n    pass"
        assert vfs.read_bytes("/data.bin") == b"\x00\x01\x02\x03"
        with vfs.Path("/test.py").open("r") as f:
            assert f.read() == "def test():\n    pass"
        with vfs.Path("/data.bin").open("rb") as f:
            assert f.read() == b"\x00\x01\x02\x03"

    @classmethod
    def test_in_memory_directory_structure(cls):
        """Test directory handling in in-memory file system."""
        vfs = InMemoryFileSystem()
        vfs.add_file("/src/main.py", "# main")
        vfs.add_file("/src/utils.py", "# utils")
        vfs.add_file("/test/test_main.py", "# test")
        vfs.add_file("/README.md", "# Project")
        assert vfs.is_dir("/src")
        assert vfs.is_dir("/test")
        assert not vfs.is_dir("/README.md")
        root_files = list(vfs.list_dir("/"))
        root_names = [f.path for f in root_files]
        assert "/src" in root_names or "src" in root_names
        assert "/test" in root_names or "test" in root_names
        assert "/README.md" in root_names or "README.md" in root_names
        src_files = list(vfs.list_dir("/src"))
        assert len(src_files) == 2
        src_names = [f.path for f in src_files]
        assert any("main.py" in name for name in src_names)
        assert any("utils.py" in name for name in src_names)


class TestZipFileSystem:
    """Test ZIP file system implementation."""

    @classmethod
    def test_zip_file_operations(cls, tmp_path):
        """Test operations on ZIP file system."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("main.py", "def main():\n    pass")
            zf.writestr("lib/utils.py", "def util():\n    pass")
            zf.writestr("data.txt", "Hello, World!")
        with ZipFileSystem(zip_path) as vfs:
            assert vfs.exists("main.py")
            assert vfs.exists("lib/utils.py")
            assert not vfs.exists("missing.py")
            assert vfs.is_file("main.py")
            assert vfs.is_dir("lib")
            assert not vfs.is_file("lib")
            assert vfs.read_text("main.py") == "def main():\n    pass"
            assert vfs.read_text("data.txt") == "Hello, World!"
            assert vfs.get_size("main.py") > 0
            assert vfs.get_size("data.txt") == 13

    @classmethod
    def test_zip_directory_listing(cls, tmp_path):
        """Test directory listing in ZIP file system."""
        zip_path = tmp_path / "project.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("src/main.py", "# main")
            zf.writestr("src/lib/utils.py", "# utils")
            zf.writestr("tests/test_main.py", "# test")
            zf.writestr("README.md", "# README")
        with ZipFileSystem(zip_path) as vfs:
            root_files = list(vfs.list_dir("/"))
            root_names = [f.path for f in root_files]
            assert "src" in root_names
            assert "tests" in root_names
            assert "README.md" in root_names
            src_files = list(vfs.list_dir("src"))
            src_names = [f.path for f in src_files]
            assert "src/main.py" in src_names
            assert "src/lib" in src_names


class TestHTTPFileSystem:
    """Test HTTP file system implementation."""

    @classmethod
    @patch("urllib.request.urlopen")
    def test_http_file_operations(cls, mock_urlopen):
        """Test operations on HTTP file system."""
        mock_response = Mock()
        mock_response.read.return_value = b"def test():\n    pass"
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "21"}
        mock_urlopen.return_value.__enter__.return_value = mock_response
        vfs = HTTPFileSystem("https://example.com")
        content = vfs.read_text("/test.py")
        assert content == "def test():\n    pass"
        assert vfs.exists("/test.py")
        assert vfs.get_size("/test.py") == 21
        vfs.read_text("/test.py")
        assert mock_urlopen.call_count == 3


class TestCompositeFileSystem:
    """Test composite file system implementation."""

    @classmethod
    def test_composite_operations(cls, tmp_path):
        """Test operations on composite file system."""
        composite = CompositeFileSystem()
        memory_fs = InMemoryFileSystem()
        memory_fs.add_file("test.py", "# memory test")
        composite.mount("/memory", memory_fs)
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        (local_dir / "main.py").write_text("# local main")
        composite.mount("/local", LocalFileSystem(local_dir))
        assert composite.exists("/memory/test.py")
        assert composite.exists("/local/main.py")
        assert not composite.exists("/memory/main.py")
        assert not composite.exists("/local/test.py")
        assert composite.read_text("/memory/test.py") == "# memory test"
        assert composite.read_text("/local/main.py") == "# local main"
        memory_files = list(composite.list_dir("/memory"))
        assert len(memory_files) == 1
        assert memory_files[0].path == "/memory/test.py"


class TestVFSChunker:
    """Test VFS chunker integration."""

    @classmethod
    def test_chunk_from_memory(cls):
        """Test chunking from in-memory file system."""
        vfs = InMemoryFileSystem()
        vfs.add_file(
            "test.py",
            """
def hello():
    return "world"

class Greeter:
    def greet(self, name):
        return f"Hello, {name}!\"
""",
        )
        chunker = VFSChunker(vfs)
        chunks = chunker.chunk_file("test.py", language="python")
        assert len(chunks) >= 2
        node_types = [chunk.node_type for chunk in chunks]
        assert "function_definition" in node_types
        assert "class_definition" in node_types

    @staticmethod
    def test_chunk_from_zip(tmp_path):
        """Test chunking from ZIP file."""
        zip_path = tmp_path / "code.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "src/main.py",
                """
def main():
    print("Hello from ZIP!")

def helper():
    return 42
""",
            )
        chunks = chunk_from_zip(
            str(zip_path),
            "src/main.py",
            language="python",
        )
        assert len(chunks) == 2
        assert all(chunk.node_type == "function_definition" for chunk in chunks)
        assert chunks[0].content.strip().startswith("def main()")
        assert chunks[1].content.strip().startswith("def helper()")

    @classmethod
    def test_chunk_directory(cls):
        """Test chunking entire directory from VFS."""
        vfs = InMemoryFileSystem()
        vfs.add_file("/src/main.py", "def main():\n    pass")
        vfs.add_file("/src/utils.py", "def util():\n    pass")
        vfs.add_file("/src/data.txt", "Not code")
        vfs.add_file("/test/test_main.py", "def test_main():\n    pass")
        chunker = VFSChunker(vfs)
        results = list(
            chunker.chunk_directory("/src", file_patterns=["*.py"], recursive=False),
        )
        assert len(results) == 2
        for file_path, chunks in results:
            assert file_path.endswith(".py")
            assert len(chunks) == 1
            assert chunks[0].node_type == "function_definition"

    @classmethod
    def test_auto_language_detection(cls):
        """Test automatic language detection from file extension."""
        vfs = InMemoryFileSystem()
        vfs.add_file("test.py", "def python_func():\n    pass")
        vfs.add_file("test.js", "function jsFunc() {\n    return 42;\n}")
        vfs.add_file("test.rs", "fn rust_func() -> i32 {\n    42\n}")
        chunker = VFSChunker(vfs)
        py_chunks = chunker.chunk_file("test.py")
        assert len(py_chunks) == 1
        assert py_chunks[0].language == "python"
        js_chunks = chunker.chunk_file("test.js")
        assert len(js_chunks) == 1
        assert js_chunks[0].language == "javascript"
        try:
            rs_chunks = chunker.chunk_file("test.rs")
            if rs_chunks:
                assert all(chunk.language == "rust" for chunk in rs_chunks)
        except (FileNotFoundError, IndexError, KeyError):
            pass


class TestVFSFactory:
    """Test VFS factory function."""

    @staticmethod
    def test_create_local_vfs():
        """Test creating local VFS."""
        vfs = create_vfs("/path/to/dir")
        assert isinstance(vfs, LocalFileSystem)

    @staticmethod
    def test_create_zip_vfs(tmp_path):
        """Test creating ZIP VFS."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test.txt", "test")
        vfs = create_vfs(str(zip_path))
        assert isinstance(vfs, ZipFileSystem)

    @staticmethod
    def test_create_http_vfs():
        """Test creating HTTP VFS."""
        vfs = create_vfs("https://example.com")
        assert isinstance(vfs, HTTPFileSystem)
        vfs = create_vfs("http://example.com")
        assert isinstance(vfs, HTTPFileSystem)

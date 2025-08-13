"""Unit tests for Grammar Download Manager"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chunker.contracts.download_contract import DownloadProgress
from chunker.grammar.download import GrammarDownloadManager


class TestGrammarDownloadManager:
    """Test the GrammarDownloadManager implementation"""

    @classmethod
    def test_initialization(cls):
        """Test manager initialization with default and custom cache"""
        manager = GrammarDownloadManager()
        assert manager._cache_dir.exists()
        assert "treesitter-chunker" in str(manager._cache_dir)
        assert "grammars" in str(manager._cache_dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_cache = Path(tmpdir) / "custom_cache"
            manager = GrammarDownloadManager(cache_dir=custom_cache)
            assert manager._cache_dir == custom_cache
            assert custom_cache.exists()

    @classmethod
    def test_metadata_handling(cls):
        """Test metadata loading and saving"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            assert manager._metadata["grammars"] == {}
            assert manager._metadata["version"] == "1.0"
            manager._metadata["grammars"]["python"] = {
                "version": "master",
                "path": str(cache_dir / "python"),
            }
            manager._save_metadata()
            manager2 = GrammarDownloadManager(cache_dir=cache_dir)
            assert "python" in manager2._metadata["grammars"]
            assert manager2._metadata["grammars"]["python"]["version"] == "master"

    @classmethod
    def test_is_grammar_cached(cls):
        """Test checking if grammar is cached"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            assert not manager.is_grammar_cached("python")
            manager._metadata["grammars"]["python"] = {
                "version": "master",
                "compiled": str(cache_dir / "python.so"),
            }
            assert not manager.is_grammar_cached("python")
            (cache_dir / "python.so").touch()
            assert manager.is_grammar_cached("python")
            assert not manager.is_grammar_cached("python", "v0.20.0")
            assert manager.is_grammar_cached("python", "master")

    @classmethod
    def test_validate_grammar(cls):
        """Test grammar validation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            result = manager.validate_grammar(cache_dir / "nonexistent.so")
            assert result == (False, "Grammar file does not exist")
            txt_file = cache_dir / "test.txt"
            txt_file.touch()
            result = manager.validate_grammar(txt_file)
            assert result == (False, "Grammar file must be a .so file")
            so_file = cache_dir / "python.so"
            so_file.touch()
            with patch("ctypes.CDLL") as mock_cdll:
                mock_lib = MagicMock()
                mock_lib.tree_sitter_python = True
                mock_cdll.return_value = mock_lib
                result = manager.validate_grammar(so_file)
                assert result == (True, None)

    @classmethod
    def test_clean_cache(cls):
        """Test cache cleaning"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            for i in range(10):
                dir_path = cache_dir / f"lang{i}-master"
                dir_path.mkdir()
                (dir_path / "grammar.js").touch()
                so_file = cache_dir / f"lang{i}.so"
                so_file.touch()
            removed = manager.clean_cache(keep_recent=3)
            assert removed > 0
            remaining_dirs = list(cache_dir.glob("*-*"))
            remaining_sos = list(cache_dir.glob("*.so"))
            assert len(remaining_dirs) <= 3
            assert len(remaining_sos) <= 3

    @classmethod
    @patch("chunker.grammar.download.urlopen")
    def test_download_file(cls, mock_urlopen):
        """Test file downloading with progress"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            mock_response = MagicMock()
            mock_response.headers = {"Content-Length": "1000"}
            mock_response.read.side_effect = [b"data" * 100, b""]
            mock_urlopen.return_value.__enter__.return_value = mock_response
            progress_calls = []

            def progress_callback(progress: DownloadProgress):
                progress_calls.append(progress)

            dest_file = cache_dir / "test.tar.gz"
            manager._download_file(
                "https://example.com/test.tar.gz",
                str(dest_file),
                "python",
                progress_callback,
            )
            assert dest_file.exists()
            assert dest_file.read_bytes() == b"data" * 100
            assert len(progress_calls) > 0
            assert all(
                p.current_file == "python-grammar.tar.gz" for p in progress_calls
            )

    @classmethod
    def test_compile_grammar(cls):
        """Test grammar compilation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            grammar_dir = cache_dir / "python-master"
            src_dir = grammar_dir / "src"
            src_dir.mkdir(parents=True)
            (src_dir / "parser.c").write_text("// parser code")
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                result = manager.compile_grammar(grammar_dir, cache_dir)
                assert result.success
                assert result.output_path == cache_dir / "python.so"
                assert result.error_message is None
                assert result.abi_version is not None
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "compilation error"
                result = manager.compile_grammar(grammar_dir, cache_dir)
                assert not result.success
                assert result.output_path is None
                assert "compilation error" in result.error_message

    @classmethod
    def test_compile_grammar_with_scanner(cls):
        """Test compilation with scanner files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            grammar_dir = cache_dir / "cpp-master"
            src_dir = grammar_dir / "src"
            src_dir.mkdir(parents=True)
            (src_dir / "parser.c").write_text("// parser")
            (src_dir / "scanner.cc").write_text("// scanner")
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                _ = manager.compile_grammar(grammar_dir, cache_dir)
                call_args = mock_run.call_args[0][0]
                assert "-xc++" in call_args
                assert "-lstdc++" in call_args

    @classmethod
    def test_download_and_compile_cached(cls):
        """Test download_and_compile when grammar is cached"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            so_file = cache_dir / "python.so"
            so_file.touch()
            manager._metadata["grammars"]["python"] = {
                "version": "master",
                "compiled": str(so_file),
            }
            success, path = manager.download_and_compile("python")
            assert success
            assert path == str(so_file)

    @classmethod
    def test_unknown_language(cls):
        """Test handling of unknown languages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GrammarDownloadManager(cache_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="Unknown language: unknown"):
                manager.download_grammar("unknown")

    @classmethod
    def test_get_abi_version(cls):
        """Test ABI version detection"""
        manager = GrammarDownloadManager()
        abi = manager._get_abi_version()
        assert isinstance(abi, int)
        assert abi in {14, 15}

    @classmethod
    def test_extract_archive(cls):
        """Test archive extraction"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            archive_dir = cache_dir / "archive_content"
            archive_dir.mkdir()
            inner_dir = archive_dir / "tree-sitter-python-master"
            inner_dir.mkdir()
            (inner_dir / "grammar.js").write_text("// grammar")
            (inner_dir / "src").mkdir()
            (inner_dir / "src" / "parser.c").write_text("// parser")
            import tarfile

            archive_path = cache_dir / "test.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(inner_dir, arcname="tree-sitter-python-master")
            dest_dir = cache_dir / "extracted"
            dest_dir.mkdir()
            manager._extract_archive(str(archive_path), dest_dir)
            assert (dest_dir / "grammar.js").exists()
            assert (dest_dir / "src" / "parser.c").exists()

    @classmethod
    def test_get_grammar_cache_dir(cls):
        """Test getting cache directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "new_cache"
            manager = GrammarDownloadManager(cache_dir=cache_dir)
            result = manager.get_grammar_cache_dir()
            assert result == cache_dir
            assert cache_dir.exists()

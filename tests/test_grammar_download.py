"""Unit tests for Grammar Download Manager"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chunker.contracts.download_contract import DownloadProgress
from chunker.grammar.download import GrammarDownloadManager


class TestGrammarDownloadManager:
    """Test the GrammarDownloadManager implementation"""

    def test_initialization(self):
        """Test manager initialization with default and custom cache"""
        # Test with default cache
        manager = GrammarDownloadManager()
        assert manager._cache_dir.exists()
        assert "treesitter-chunker" in str(manager._cache_dir)
        assert "grammars" in str(manager._cache_dir)

        # Test with custom cache
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_cache = Path(tmpdir) / "custom_cache"
            manager = GrammarDownloadManager(cache_dir=custom_cache)
            assert manager._cache_dir == custom_cache
            assert custom_cache.exists()

    def test_metadata_handling(self):
        """Test metadata loading and saving"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Initial metadata should be empty
            assert manager._metadata["grammars"] == {}
            assert manager._metadata["version"] == "1.0"

            # Add some metadata
            manager._metadata["grammars"]["python"] = {
                "version": "master",
                "path": str(cache_dir / "python"),
            }
            manager._save_metadata()

            # Create new manager and check it loads metadata
            manager2 = GrammarDownloadManager(cache_dir=cache_dir)
            assert "python" in manager2._metadata["grammars"]
            assert manager2._metadata["grammars"]["python"]["version"] == "master"

    def test_is_grammar_cached(self):
        """Test checking if grammar is cached"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Not cached initially
            assert not manager.is_grammar_cached("python")

            # Add to metadata but no .so file
            manager._metadata["grammars"]["python"] = {
                "version": "master",
                "compiled": str(cache_dir / "python.so"),
            }
            assert not manager.is_grammar_cached("python")

            # Create .so file
            (cache_dir / "python.so").touch()
            assert manager.is_grammar_cached("python")

            # Check version mismatch
            assert not manager.is_grammar_cached("python", "v0.20.0")
            assert manager.is_grammar_cached("python", "master")

    def test_validate_grammar(self):
        """Test grammar validation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Non-existent file
            result = manager.validate_grammar(cache_dir / "nonexistent.so")
            assert result == (False, "Grammar file does not exist")

            # Wrong extension
            txt_file = cache_dir / "test.txt"
            txt_file.touch()
            result = manager.validate_grammar(txt_file)
            assert result == (False, "Grammar file must be a .so file")

            # Valid .so file (mock loading)
            so_file = cache_dir / "python.so"
            so_file.touch()
            with patch("ctypes.CDLL") as mock_cdll:
                mock_lib = MagicMock()
                mock_lib.tree_sitter_python = True
                mock_cdll.return_value = mock_lib

                result = manager.validate_grammar(so_file)
                assert result == (True, None)

    def test_clean_cache(self):
        """Test cache cleaning"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Create some test files
            for i in range(10):
                dir_path = cache_dir / f"lang{i}-master"
                dir_path.mkdir()
                (dir_path / "grammar.js").touch()

                so_file = cache_dir / f"lang{i}.so"
                so_file.touch()

            # Clean cache keeping only 3 recent
            removed = manager.clean_cache(keep_recent=3)

            # Should have removed some files
            assert removed > 0

            # Check remaining files
            remaining_dirs = list(cache_dir.glob("*-*"))
            remaining_sos = list(cache_dir.glob("*.so"))
            assert len(remaining_dirs) <= 3
            assert len(remaining_sos) <= 3

    @patch("chunker.grammar.download.urlopen")
    def test_download_file(self, mock_urlopen):
        """Test file downloading with progress"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Mock response
            mock_response = MagicMock()
            mock_response.headers = {"Content-Length": "1000"}
            mock_response.read.side_effect = [b"data" * 100, b""]  # Two chunks
            mock_urlopen.return_value.__enter__.return_value = mock_response

            # Progress callback
            progress_calls = []

            def progress_callback(progress: DownloadProgress):
                progress_calls.append(progress)

            # Download
            dest_file = cache_dir / "test.tar.gz"
            manager._download_file(
                "https://example.com/test.tar.gz",
                str(dest_file),
                "python",
                progress_callback,
            )

            # Check file was written
            assert dest_file.exists()
            assert dest_file.read_bytes() == b"data" * 100

            # Check progress callbacks
            assert len(progress_calls) > 0
            assert all(
                p.current_file == "python-grammar.tar.gz" for p in progress_calls
            )

    def test_compile_grammar(self):
        """Test grammar compilation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Create mock grammar directory
            grammar_dir = cache_dir / "python-master"
            src_dir = grammar_dir / "src"
            src_dir.mkdir(parents=True)
            (src_dir / "parser.c").write_text("// parser code")

            # Mock subprocess run
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""

                result = manager.compile_grammar(grammar_dir, cache_dir)

                assert result.success
                assert result.output_path == cache_dir / "python.so"
                assert result.error_message is None
                assert result.abi_version is not None

            # Test compilation failure
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "compilation error"

                result = manager.compile_grammar(grammar_dir, cache_dir)

                assert not result.success
                assert result.output_path is None
                assert "compilation error" in result.error_message

    def test_compile_grammar_with_scanner(self):
        """Test compilation with scanner files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Create grammar with scanner.cc
            grammar_dir = cache_dir / "cpp-master"
            src_dir = grammar_dir / "src"
            src_dir.mkdir(parents=True)
            (src_dir / "parser.c").write_text("// parser")
            (src_dir / "scanner.cc").write_text("// scanner")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""

                _ = manager.compile_grammar(grammar_dir, cache_dir)

                # Check that C++ flags were added
                call_args = mock_run.call_args[0][0]
                assert "-xc++" in call_args
                assert "-lstdc++" in call_args

    def test_download_and_compile_cached(self):
        """Test download_and_compile when grammar is cached"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Setup cached grammar
            so_file = cache_dir / "python.so"
            so_file.touch()
            manager._metadata["grammars"]["python"] = {
                "version": "master",
                "compiled": str(so_file),
            }

            success, path = manager.download_and_compile("python")
            assert success
            assert path == str(so_file)

    def test_unknown_language(self):
        """Test handling of unknown languages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GrammarDownloadManager(cache_dir=Path(tmpdir))

            with pytest.raises(ValueError, match="Unknown language: unknown"):
                manager.download_grammar("unknown")

    def test_get_abi_version(self):
        """Test ABI version detection"""
        manager = GrammarDownloadManager()

        # Should return a valid ABI version
        abi = manager._get_abi_version()
        assert isinstance(abi, int)
        assert abi in [14, 15]  # Known ABI versions

    def test_extract_archive(self):
        """Test archive extraction"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Create a test tar.gz archive
            archive_dir = cache_dir / "archive_content"
            archive_dir.mkdir()
            inner_dir = archive_dir / "tree-sitter-python-master"
            inner_dir.mkdir()
            (inner_dir / "grammar.js").write_text("// grammar")
            (inner_dir / "src").mkdir()
            (inner_dir / "src" / "parser.c").write_text("// parser")

            import tarfile

            archive_path = cache_dir / "test.tar.gz"
            with tarfile.Path(archive_path).open("w:gz") as tar:
                tar.add(inner_dir, arcname="tree-sitter-python-master")

            # Extract to destination
            dest_dir = cache_dir / "extracted"
            dest_dir.mkdir()
            manager._extract_archive(str(archive_path), dest_dir)

            # Check files were extracted
            assert (dest_dir / "grammar.js").exists()
            assert (dest_dir / "src" / "parser.c").exists()

    def test_get_grammar_cache_dir(self):
        """Test getting cache directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "new_cache"
            manager = GrammarDownloadManager(cache_dir=cache_dir)

            # Should create directory if it doesn't exist
            result = manager.get_grammar_cache_dir()
            assert result == cache_dir
            assert cache_dir.exists()

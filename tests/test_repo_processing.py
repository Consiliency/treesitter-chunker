"""Test repository processing functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import git
import pytest

from chunker.exceptions import ChunkerError
from chunker.repo.processor import GitAwareRepoProcessor, RepoProcessor


class TestRepoProcessor:
    """Test basic repository processor."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create directory structure
            (repo_path / "src").mkdir()
            (repo_path / "tests").mkdir()
            (repo_path / "docs").mkdir()
            (repo_path / "node_modules").mkdir()

            # Create test files
            (repo_path / "src" / "main.py").write_text(
                '''
def hello():
    """Say hello."""
    print("Hello, World!")

def goodbye():
    """Say goodbye."""
    print("Goodbye!")
''',
            )

            (repo_path / "src" / "utils.js").write_text(
                """
function add(a, b) {
    return a + b;
}

function subtract(a, b) {
    return a - b;
}

module.exports = { add, subtract };
""",
            )

            (repo_path / "tests" / "test_main.py").write_text(
                """
def test_hello():
    assert True

def test_goodbye():
    assert True
""",
            )

            # Create files that should be ignored
            (repo_path / "src" / "__pycache__").mkdir()
            (repo_path / "src" / "__pycache__" / "main.cpython-39.pyc").write_bytes(
                b"fake pyc",
            )
            (repo_path / "node_modules" / "package.json").write_text("{}")

            # Create non-supported file
            (repo_path / "docs" / "README.md").write_text("# Documentation")

            yield repo_path

    @pytest.fixture
    def processor(self):
        """Create a repository processor."""
        return RepoProcessor(show_progress=False)

    def test_get_processable_files(self, processor, temp_repo):
        """Test getting list of processable files."""
        files = processor.get_processable_files(str(temp_repo))

        # Should include Python and JavaScript files
        file_names = [f.name for f in files]
        assert "main.py" in file_names
        assert "utils.js" in file_names
        assert "test_main.py" in file_names

        # Should not include ignored files
        assert "main.cpython-39.pyc" not in file_names
        assert "package.json" not in file_names
        assert "README.md" not in file_names

    def test_get_processable_files_with_pattern(self, processor, temp_repo):
        """Test file filtering with pattern."""
        # Only Python files
        files = processor.get_processable_files(str(temp_repo), file_pattern="*.py")
        file_names = [f.name for f in files]

        assert "main.py" in file_names
        assert "test_main.py" in file_names
        assert "utils.js" not in file_names

    def test_get_processable_files_with_excludes(self, processor, temp_repo):
        """Test file filtering with exclude patterns."""
        files = processor.get_processable_files(
            str(temp_repo),
            exclude_patterns=["tests/*"],
        )
        file_names = [f.name for f in files]

        assert "main.py" in file_names
        assert "utils.js" in file_names
        assert "test_main.py" not in file_names

    def test_process_repository(self, processor, temp_repo):
        """Test processing entire repository."""
        result = processor.process_repository(str(temp_repo), incremental=False)

        assert result.repo_path == str(temp_repo)
        assert result.total_files == 3  # main.py, utils.js, test_main.py
        assert len(result.file_results) == 3
        assert result.total_chunks > 0
        assert len(result.errors) == 0
        assert result.processing_time > 0

        # Check file results
        file_paths = [r.file_path for r in result.file_results]
        assert "src/main.py" in file_paths
        assert "src/utils.js" in file_paths
        assert "tests/test_main.py" in file_paths

        # Check chunks have file metadata
        for file_result in result.file_results:
            for chunk in file_result.chunks:
                assert "file_path" in chunk.metadata
                assert "repo_path" in chunk.metadata

    def test_process_files_iterator(self, processor, temp_repo):
        """Test iterator-based processing."""
        results = list(processor.process_files_iterator(str(temp_repo)))

        assert len(results) == 3

        # Check that results are FileChunkResult objects
        for result in results:
            assert hasattr(result, "file_path")
            assert hasattr(result, "chunks")
            assert hasattr(result, "processing_time")

    def test_estimate_processing_time(self, processor, temp_repo):
        """Test processing time estimation."""
        estimate = processor.estimate_processing_time(str(temp_repo))

        assert estimate > 0
        assert isinstance(estimate, float)

    def test_traversal_strategies(self, temp_repo):
        """Test different traversal strategies."""
        # Depth-first
        df_processor = RepoProcessor(
            show_progress=False,
            traversal_strategy="depth-first",
        )
        df_files = df_processor.get_processable_files(str(temp_repo))

        # Breadth-first
        bf_processor = RepoProcessor(
            show_progress=False,
            traversal_strategy="breadth-first",
        )
        bf_files = bf_processor.get_processable_files(str(temp_repo))

        # Should get same files, potentially different order
        assert set(df_files) == set(bf_files)

    def test_parallel_processing(self, temp_repo):
        """Test parallel file processing."""
        # Single worker
        single_processor = RepoProcessor(show_progress=False, max_workers=1)
        single_result = single_processor.process_repository(
            str(temp_repo),
            incremental=False,
        )

        # Multiple workers
        multi_processor = RepoProcessor(show_progress=False, max_workers=4)
        multi_result = multi_processor.process_repository(
            str(temp_repo),
            incremental=False,
        )

        # Should get same results
        assert single_result.total_chunks == multi_result.total_chunks
        assert single_result.total_files == multi_result.total_files

    def test_unicode_handling(self, processor):
        """Test handling of files with unicode content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create file with unicode content
            (repo_path / "unicode.py").write_text(
                '''
def greeting():
    """Unicode test."""
    print("Hello, 世界! 🌍")
    print("Здравствуй, мир!")
''',
                encoding="utf-8",
            )

            result = processor.process_repository(str(repo_path), incremental=False)

            assert result.total_files == 1
            assert len(result.errors) == 0
            assert result.file_results[0].chunks[0].content is not None

    def test_invalid_repo_path(self, processor):
        """Test handling of invalid repository path."""
        with pytest.raises(ChunkerError, match="Repository path does not exist"):
            processor.process_repository("/non/existent/path")


class TestGitAwareRepoProcessor:
    """Test Git-aware repository processor."""

    @pytest.fixture
    def git_repo(self):
        """Create a temporary git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Initialize git repo
            repo = git.Repo.init(repo_path)

            # Create initial files
            (repo_path / "main.py").write_text(
                """
def main():
    print("Initial version")
""",
            )

            (repo_path / ".gitignore").write_text(
                """
__pycache__/
*.pyc
.env
build/
dist/
""",
            )

            # Initial commit
            repo.index.add(["main.py", ".gitignore"])
            repo.index.commit("Initial commit")

            yield repo_path, repo

    @pytest.fixture
    def git_processor(self):
        """Create a Git-aware repository processor."""
        return GitAwareRepoProcessor(show_progress=False)

    def test_git_aware_initialization(self, git_processor):
        """Test Git-aware processor initialization."""
        assert hasattr(git_processor, "get_changed_files")
        assert hasattr(git_processor, "should_process_file")
        assert hasattr(git_processor, "load_gitignore_patterns")

    def test_get_changed_files(self, git_processor, git_repo):
        """Test getting changed files from git."""
        repo_path, repo = git_repo

        # No changes yet
        changed = git_processor.get_changed_files(str(repo_path))
        assert len(changed) == 0

        # Make a change
        (repo_path / "main.py").write_text(
            """
def main():
    print("Updated version")

def new_function():
    print("New feature")
""",
        )

        # Add new file
        (repo_path / "utils.py").write_text(
            """
def helper():
    return True
""",
        )

        repo.index.add(["main.py", "utils.py"])
        repo.index.commit("Add new feature")

        # Get changes since previous commit
        changed = git_processor.get_changed_files(str(repo_path), since_commit="HEAD~1")
        assert len(changed) == 2
        assert "main.py" in changed
        assert "utils.py" in changed

    def test_should_process_file_gitignore(self, git_processor, git_repo):
        """Test file processing decision with gitignore."""
        repo_path, repo = git_repo

        # Tracked file should be processed
        assert git_processor.should_process_file(
            str(repo_path / "main.py"),
            str(repo_path),
        )

        # Create ignored file
        (repo_path / "build").mkdir()
        (repo_path / "build" / "output.py").write_text("# Build output")

        # Ignored file should not be processed
        assert not git_processor.should_process_file(
            str(repo_path / "build" / "output.py"),
            str(repo_path),
        )

        # Untracked but not ignored file should be processed
        (repo_path / "new_file.py").write_text("# New file")
        assert git_processor.should_process_file(
            str(repo_path / "new_file.py"),
            str(repo_path),
        )

    def test_get_file_history(self, git_processor, git_repo):
        """Test getting file commit history."""
        repo_path, repo = git_repo

        # Make several commits to a file
        for i in range(3):
            (repo_path / "main.py").write_text(
                f"""
def main():
    print("Version {i + 2}")
""",
            )
            repo.index.add(["main.py"])
            repo.index.commit(f"Update version {i + 2}")

        # Get history
        history = git_processor.get_file_history(
            str(repo_path / "main.py"),
            str(repo_path),
            limit=5,
        )

        assert len(history) == 4  # Initial + 3 updates
        assert all("hash" in commit for commit in history)
        assert all("author" in commit for commit in history)
        assert all("date" in commit for commit in history)
        assert all("message" in commit for commit in history)

    def test_load_gitignore_patterns(self, git_processor, git_repo):
        """Test loading gitignore patterns."""
        repo_path, repo = git_repo

        patterns = git_processor.load_gitignore_patterns(str(repo_path))

        assert "__pycache__/" in patterns
        assert "*.pyc" in patterns
        assert ".env" in patterns
        assert "build/" in patterns
        assert "dist/" in patterns

    def test_incremental_processing(self, git_processor, git_repo):
        """Test incremental processing with state management."""
        repo_path, repo = git_repo

        # First run - process all files
        result1 = git_processor.process_repository(str(repo_path), incremental=True)
        assert result1.total_files == 1

        # Check state was saved
        state = git_processor.load_incremental_state(str(repo_path))
        assert state is not None
        assert "last_commit" in state
        assert state["total_files"] == 1

        # Add new file
        (repo_path / "new_file.py").write_text(
            """
def new_function():
    pass
""",
        )
        repo.index.add(["new_file.py"])
        repo.index.commit("Add new file")

        # Second run - should only process new file
        with patch.object(git_processor, "get_changed_files") as mock_changed:
            mock_changed.return_value = ["new_file.py"]

            git_processor.process_repository(str(repo_path), incremental=True)

            # Should have called get_changed_files with last commit
            mock_changed.assert_called_once()
            assert mock_changed.call_args[1]["since_commit"] == state["last_commit"]

    def test_process_bare_repository(self, git_processor):
        """Test processing a bare repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bare_repo_path = Path(tmpdir) / "bare.git"

            # Create bare repo
            git.Repo.init(str(bare_repo_path), bare=True)

            # Bare repos don't have working directory
            with pytest.raises(ChunkerError):
                git_processor.process_repository(str(bare_repo_path))

    def test_not_git_repository(self, git_processor):
        """Test handling of non-git directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should work but without git features
            (Path(tmpdir) / "file.py").write_text("print('hello')")

            result = git_processor.process_repository(tmpdir, incremental=False)
            assert result.total_files == 1

            # Git-specific methods should handle gracefully
            changed = git_processor.get_changed_files(tmpdir)
            assert changed == []  # Or raises ChunkerError

    def test_concurrent_processing(self, git_processor, git_repo):
        """Test thread-safe processing of git repository."""
        repo_path, repo = git_repo

        # Add multiple files
        for i in range(10):
            (repo_path / f"file_{i}.py").write_text(
                f"""
def function_{i}():
    return {i}
""",
            )

        repo.index.add([f"file_{i}.py" for i in range(10)])
        repo.index.commit("Add multiple files")

        # Process with multiple workers
        result = git_processor.process_repository(
            str(repo_path),
            incremental=False,
            max_workers=4,
        )

        assert result.total_files == 11  # main.py + 10 new files
        assert len(result.errors) == 0

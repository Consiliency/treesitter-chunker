"""Integration tests for Phase 9 repository processing with other features."""

import pytest

from chunker import BaseMetadataExtractor as MetadataExtractor
from chunker import (
    ChunkHierarchyBuilder,
    RepoConfig,
    RepoProcessorImpl,
    TiktokenCounter,
    TreeSitterSemanticMerger,
)


class TestRepoProcessingIntegration:
    """Test repository processing working with other Phase 9 features."""

    @pytest.fixture()
    def test_repo(self, tmp_path):
        """Create a test repository structure."""
        # Create git repo
        import subprocess

        subprocess.run(["git", "init"], check=False, cwd=tmp_path, capture_output=True)

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            """
__pycache__/
*.pyc
.env
node_modules/
build/
dist/
""",
        )

        # Create source files
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Main module
        main_py = src_dir / "main.py"
        main_py.write_text(
            '''
"""Main application module."""
from .auth import authenticate
from .database import Database

def main():
    """Run the application."""
    user = authenticate()
    db = Database()
    db.connect()
    print(f"Welcome {user.name}")

if __name__ == "__main__":
    main()
''',
        )

        # Auth module
        auth_py = src_dir / "auth.py"
        auth_py.write_text(
            '''
"""Authentication module."""

class User:
    def __init__(self, name):
        self.name = name

def authenticate():
    """Authenticate user."""
    # TODO: Implement real authentication
    return User("test_user")

def logout():
    """Logout user."""
    # TODO: Implement logout
    pass
''',
        )

        # Database module
        db_py = src_dir / "database.py"
        db_py.write_text(
            '''
"""Database module."""

class Database:
    def __init__(self):
        self.connection = None

    def connect(self):
        """Connect to database."""
        # TODO: Implement database connection
        self.connection = "mock_connection"

    def disconnect(self):
        """Disconnect from database."""
        self.connection = None
''',
        )

        # Test files
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        test_auth = test_dir / "test_auth.py"
        test_auth.write_text(
            '''
"""Test authentication."""
from src.auth import authenticate

def test_authenticate():
    user = authenticate()
    assert user.name == "test_user"
''',
        )

        # Files to ignore
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "output.js").write_text("compiled code")

        pycache = src_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-39.pyc").write_text("bytecode")

        # Git add files
        subprocess.run(
            ["git", "add", "."],
            check=False,
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            check=False,
            cwd=tmp_path,
            capture_output=True,
        )

        return tmp_path

    def test_repo_processing_with_token_counting(self, test_repo):
        """Test repo processing with token limits."""
        config = RepoConfig(
            include_patterns=["**/*.py"],
            exclude_patterns=["**/test_*.py"],
            respect_gitignore=True,
            max_file_size=1024 * 1024,  # 1MB
            follow_symlinks=False,
        )

        processor = RepoProcessorImpl()
        counter = TiktokenCounter()

        # Process repository
        results = processor.process_repository(str(test_repo), config)

        # Verify results
        assert results.total_files > 0
        assert results.processed_files > 0
        assert results.skipped_files > 0  # Should skip test files

        # Count tokens in all chunks
        total_tokens = 0
        for chunk in results.chunks:
            tokens = counter.count_tokens(chunk.content)
            total_tokens += tokens

        assert total_tokens > 0
        assert results.chunks  # Should have chunks

        # Verify gitignore is respected
        chunk_files = {chunk.file_path for chunk in results.chunks}
        assert not any("__pycache__" in str(f) for f in chunk_files)
        assert not any("build" in str(f) for f in chunk_files)

    def test_repo_processing_with_hierarchy(self, test_repo):
        """Test repo processing builds correct hierarchy."""
        config = RepoConfig(include_patterns=["**/*.py"])
        processor = RepoProcessorImpl()
        hierarchy_builder = ChunkHierarchyBuilder()

        # Process repository
        results = processor.process_repository(str(test_repo), config)

        # Build hierarchy for all chunks
        hierarchy = hierarchy_builder.build_hierarchy(results.chunks)

        # Verify hierarchy structure
        assert hierarchy.root_chunks  # Should have root chunks

        # Find class chunks
        class_chunks = [c for c in results.chunks if "class" in c.node_type]
        assert class_chunks

        # Verify class methods are children
        for class_chunk in class_chunks:
            children = hierarchy.get_children(class_chunk.chunk_id)
            assert children  # Classes should have method children

    def test_repo_processing_with_metadata_extraction(self, test_repo):
        """Test repo processing with metadata extraction."""
        config = RepoConfig(include_patterns=["**/*.py"])
        processor = RepoProcessorImpl()
        extractor = MetadataExtractor()

        # Process repository
        results = processor.process_repository(str(test_repo), config)

        # Extract metadata for all chunks
        for chunk in results.chunks:
            chunk.metadata = extractor.extract_metadata(chunk)

        # Verify TODO comments are extracted
        todos_found = False
        for chunk in results.chunks:
            if chunk.metadata and chunk.metadata.get("todos"):
                todos_found = True
                break

        assert todos_found, "Should find TODO comments"

        # Verify docstrings are extracted
        docstrings_found = any(
            chunk.metadata and chunk.metadata.get("docstring")
            for chunk in results.chunks
        )
        assert docstrings_found

    def test_repo_processing_with_progress_callback(self, test_repo):
        """Test repo processing with progress tracking."""
        config = RepoConfig(include_patterns=["**/*.py"])
        processor = RepoProcessorImpl()

        progress_updates = []

        def progress_callback(current, total, message):
            progress_updates.append(
                {
                    "current": current,
                    "total": total,
                    "message": message,
                },
            )

        # Process with progress callback
        processor.process_repository(
            str(test_repo),
            config,
            progress_callback=progress_callback,
        )

        # Verify progress updates
        assert progress_updates
        assert any("Discovering files" in u["message"] for u in progress_updates)
        assert any("Processing" in u["message"] for u in progress_updates)

        # Verify progress completion
        final_update = progress_updates[-1]
        assert final_update["current"] == final_update["total"]

    def test_repo_processing_with_semantic_merging(self, test_repo):
        """Test repo processing combined with semantic merging."""
        config = RepoConfig(
            include_patterns=["**/*.py"],
            exclude_patterns=["**/test_*.py"],
        )
        processor = RepoProcessorImpl()
        merger = TreeSitterSemanticMerger()

        # Process repository
        results = processor.process_repository(str(test_repo), config)
        original_count = len(results.chunks)

        # Group chunks by file for merging
        chunks_by_file = {}
        for chunk in results.chunks:
            file_path = chunk.file_path
            if file_path not in chunks_by_file:
                chunks_by_file[file_path] = []
            chunks_by_file[file_path].append(chunk)

        # Merge chunks within each file
        all_merged = []
        for file_path, file_chunks in chunks_by_file.items():
            merged = merger.merge_chunks(file_chunks)
            all_merged.extend(merged)

        # Should have fewer chunks after merging
        assert len(all_merged) < original_count

    def test_repo_processing_incremental(self, test_repo):
        """Test incremental repository processing."""
        config = RepoConfig(include_patterns=["**/*.py"])
        processor = RepoProcessorImpl()

        # First processing
        results1 = processor.process_repository(str(test_repo), config)

        # Modify a file
        auth_file = test_repo / "src" / "auth.py"
        original_content = auth_file.read_text()
        auth_file.write_text(original_content + "\n\ndef new_function():\n    pass\n")

        # Process again (would use incremental in real implementation)
        results2 = processor.process_repository(str(test_repo), config)

        # Should have more chunks due to new function
        assert len(results2.chunks) > len(results1.chunks)

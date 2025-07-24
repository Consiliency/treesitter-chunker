"""Integration tests combining multiple Phase 9 features."""

import pytest

from chunker import BaseMetadataExtractor as MetadataExtractor
from chunker import (  # Supporting; Core
    ChunkHierarchyBuilder,
    FallbackChunker,
    FallbackStrategy,
    ImportBlockRule,
    MergeStrategy,
    RepoConfig,
    RepoProcessorImpl,
    TiktokenCounter,
    TodoCommentRule,
    TokenAwareChunker,
    TreeSitterSemanticMerger,
    chunk_file,
)


class TestPhase9CombinedFeatures:
    """Test multiple Phase 9 features working together."""

    @pytest.fixture()
    def complex_project(self, tmp_path):
        """Create a complex project structure."""
        # Initialize git
        import subprocess

        subprocess.run(["git", "init"], check=False, cwd=tmp_path, capture_output=True)

        # Create project structure
        src = tmp_path / "src"
        src.mkdir()

        # API module with TODOs
        api_py = src / "api.py"
        api_py.write_text(
            '''
"""API module for web service."""
import json
from flask import Flask, request, jsonify
from typing import Dict, List, Optional

app = Flask(__name__)

# TODO: Add authentication middleware
# TODO: Implement rate limiting

@app.route('/api/users', methods=['GET'])
def get_users() -> Dict:
    """Get all users.
    
    Returns:
        Dict containing user list
    """
    # TODO: Add pagination support
    users = fetch_users_from_db()
    return jsonify({"users": users, "count": len(users)})

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id: int) -> Dict:
    """Get specific user by ID."""
    user = fetch_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)

@app.route('/api/users', methods=['POST'])
def create_user() -> Dict:
    """Create new user."""
    data = request.get_json()
    # TODO: Add input validation
    user = create_user_in_db(data)
    return jsonify(user), 201

# Helper functions
def fetch_users_from_db() -> List[Dict]:
    """Fetch users from database."""
    # Mock implementation
    return [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"}
    ]

def fetch_user_by_id(user_id: int) -> Optional[Dict]:
    """Fetch single user by ID."""
    users = fetch_users_from_db()
    return next((u for u in users if u["id"] == user_id), None)

def create_user_in_db(data: Dict) -> Dict:
    """Create user in database."""
    # Mock implementation
    return {"id": 3, **data}
''',
        )

        # Models module
        models_py = src / "models.py"
        models_py.write_text(
            '''
"""Data models."""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class User:
    """User model."""
    id: int
    name: str
    email: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Getter/setter pair
    def get_email(self) -> str:
        """Get user email."""
        return self.email
    
    def set_email(self, email: str) -> None:
        """Set user email."""
        # TODO: Add email validation
        self.email = email
        self.updated_at = datetime.now()
    
    # Another getter/setter pair
    def get_name(self) -> str:
        """Get user name."""
        return self.name
    
    def set_name(self, name: str) -> None:
        """Set user name."""
        self.name = name
        self.updated_at = datetime.now()

@dataclass 
class Post:
    """Blog post model."""
    id: int
    title: str
    content: str
    author_id: int
    tags: List[str]
    published: bool = False
    
    def publish(self) -> None:
        """Publish the post."""
        # TODO: Send notification to subscribers
        self.published = True
    
    def unpublish(self) -> None:
        """Unpublish the post."""
        self.published = False
''',
        )

        # Utils with small functions
        utils_py = src / "utils.py"
        utils_py.write_text(
            r'''
"""Utility functions."""
import re
import hashlib
from typing import Any

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def hash_password(password: str) -> str:
    """Hash password."""
    return hashlib.sha256(password.encode()).hexdigest()

def sanitize_input(text: str) -> str:
    """Sanitize user input."""
    # TODO: Implement proper sanitization
    return text.strip()

def format_date(date: Any) -> str:
    """Format date for display."""
    # TODO: Handle different date formats
    return str(date)

# Small utility functions that should be merged
def is_valid_id(id_val: Any) -> bool:
    """Check if ID is valid."""
    return isinstance(id_val, int) and id_val > 0

def is_empty(value: Any) -> bool:
    """Check if value is empty."""
    return not value

def get_default(value: Any, default: Any) -> Any:
    """Get value or default."""
    return value if value is not None else default
''',
        )

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("__pycache__/\n*.pyc\n.env\n")

        # Git add and commit
        subprocess.run(
            ["git", "add", "."],
            check=False,
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            check=False,
            cwd=tmp_path,
            capture_output=True,
        )

        return tmp_path

    def test_full_pipeline_integration(self, complex_project):
        """Test complete pipeline with all Phase 9 features."""
        # Step 1: Repository processing
        repo_processor = RepoProcessorImpl()
        repo_config = RepoConfig(
            include_patterns=["**/*.py"],
            respect_gitignore=True,
        )

        repo_results = repo_processor.process_repository(
            str(complex_project),
            repo_config,
        )

        assert repo_results.total_files >= 3
        assert repo_results.chunks

        # Step 2: Build hierarchy
        hierarchy_builder = ChunkHierarchyBuilder()
        hierarchy = hierarchy_builder.build_hierarchy(repo_results.chunks)

        # Step 3: Extract metadata with custom rules
        metadata_extractor = MetadataExtractor()
        todo_rule = TodoCommentRule()
        import_rule = ImportBlockRule()

        for chunk in repo_results.chunks:
            # Extract standard metadata
            chunk.metadata = metadata_extractor.extract_metadata(chunk)

            # Apply custom rules
            if todo_rule.matches(chunk):
                todos = todo_rule.extract(chunk)
                chunk.metadata["custom_todos"] = todos

            if import_rule.matches(chunk):
                imports = import_rule.extract(chunk)
                chunk.metadata["imports"] = imports

        # Verify TODOs were found
        chunks_with_todos = [
            c for c in repo_results.chunks if c.metadata and c.metadata.get("todos")
        ]
        assert chunks_with_todos

        # Step 4: Semantic merging
        merger = TreeSitterSemanticMerger(
            merge_strategy=MergeStrategy.BALANCED,
            max_chunk_size=500,
        )

        # Group by file for merging
        chunks_by_file = {}
        for chunk in repo_results.chunks:
            file_path = chunk.file_path
            if file_path not in chunks_by_file:
                chunks_by_file[file_path] = []
            chunks_by_file[file_path].append(chunk)

        # Merge chunks
        all_merged = []
        for file_path, file_chunks in chunks_by_file.items():
            merged = merger.merge_chunks(file_chunks)
            all_merged.extend(merged)

        # Should have fewer chunks after merging
        assert len(all_merged) < len(repo_results.chunks)

        # Step 5: Token counting and optimization
        counter = TiktokenCounter()
        token_aware = TokenAwareChunker(
            tokenizer=counter,
            max_tokens=200,
            min_tokens=50,
        )

        # Re-process merged chunks for token optimization
        token_optimized = []
        for chunk in all_merged:
            optimized = token_aware.optimize_chunk(chunk)
            token_optimized.extend(optimized)

        # Verify token limits
        for chunk in token_optimized:
            tokens = counter.count_tokens(chunk.content)
            assert tokens <= 200

    def test_cross_feature_metadata_flow(self, complex_project):
        """Test metadata flows correctly across features."""
        # Process single file
        api_file = complex_project / "src" / "api.py"
        chunks = chunk_file(api_file, "python")

        # Extract metadata
        extractor = MetadataExtractor()
        for chunk in chunks:
            chunk.metadata = extractor.extract_metadata(chunk)

        # Build hierarchy
        builder = ChunkHierarchyBuilder()
        hierarchy = builder.build_hierarchy(chunks)

        # Merge semantically
        merger = TreeSitterSemanticMerger()
        merged = merger.merge_chunks(chunks)

        # Verify metadata preserved through pipeline
        for chunk in merged:
            assert chunk.metadata is not None

            # If it's a function chunk, should have signature
            if "def " in chunk.content:
                assert chunk.metadata.get("signatures") or chunk.metadata.get(
                    "signature",
                )

    def test_fallback_with_other_features(self, tmp_path):
        """Test fallback chunking with other Phase 9 features."""
        # Create malformed Python file
        bad_file = tmp_path / "malformed.py"
        bad_file.write_text(
            '''
def incomplete_function(
    # This function is incomplete and will cause parsing issues
    print("This is inside an incomplete function"
    
class AlsoIncomplete:
    def method(self):
        # Missing closing
        return "something
        
# But this part is fine
def valid_function():
    """This function is complete."""
    return True
    
# TODO: Fix the incomplete parts above
# TODO: Add proper error handling
''',
        )

        # Try normal chunking (might fail or give incomplete results)
        try:
            chunks = chunk_file(bad_file, "python")
        except:
            chunks = []

        # Use fallback chunking
        fallback = FallbackChunker(
            chunk_size=10,
            chunk_overlap=2,
            strategy=FallbackStrategy.SYNTAX_AWARE,
        )

        fallback_chunks = fallback.chunk_file(str(bad_file), "python")
        assert fallback_chunks  # Should produce chunks even with bad syntax

        # Extract metadata from fallback chunks
        extractor = MetadataExtractor()
        for chunk in fallback_chunks:
            chunk.metadata = extractor.extract_metadata(chunk)

        # Should still find TODOs
        todos_found = any(
            chunk.metadata and chunk.metadata.get("todos") for chunk in fallback_chunks
        )
        assert todos_found

    def test_performance_with_combined_features(self, complex_project):
        """Test performance when using multiple features together."""
        import time

        # Time the full pipeline
        start = time.time()

        # 1. Repository processing
        processor = RepoProcessorImpl()
        config = RepoConfig(include_patterns=["**/*.py"])
        results = processor.process_repository(str(complex_project), config)

        # 2. Hierarchy building
        hierarchy_builder = ChunkHierarchyBuilder()
        hierarchy = hierarchy_builder.build_hierarchy(results.chunks)

        # 3. Metadata extraction
        extractor = MetadataExtractor()
        for chunk in results.chunks:
            chunk.metadata = extractor.extract_metadata(chunk)

        # 4. Token counting
        counter = TiktokenCounter()
        for chunk in results.chunks:
            tokens = counter.count_tokens(chunk.content)

        # 5. Semantic merging
        merger = TreeSitterSemanticMerger()
        # Group by file
        by_file = {}
        for chunk in results.chunks:
            by_file.setdefault(chunk.file_path, []).append(chunk)

        for file_chunks in by_file.values():
            merger.merge_chunks(file_chunks)

        elapsed = time.time() - start

        # Should complete reasonably fast for small project
        assert elapsed < 5.0  # 5 seconds for small test project

        # Verify all features produced results
        assert results.chunks
        assert hierarchy.root_chunks
        assert any(c.metadata for c in results.chunks)

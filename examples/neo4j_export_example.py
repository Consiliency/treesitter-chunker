#!/usr/bin/env python3
"""Example: Export code chunks to Neo4j format with relationship tracking."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.core import chunk_file
from chunker.export import (
    ASTRelationshipTracker,
    Neo4jExporter,
    StructuredExportOrchestrator,
)
from chunker.interfaces.export import ExportFormat


def export_to_neo4j(source_files, output_path):
    """Export source files to Neo4j Cypher format.

    Args:
        source_files: List of source file paths
        output_path: Output path for Cypher file
    """
    # Collect all chunks
    all_chunks = []

    print("Chunking source files...")
    for file_path in source_files:
        # Determine language from extension
        ext = Path(file_path).suffix
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".c": "c",
            ".cpp": "cpp",
            ".rs": "rust",
        }

        language = language_map.get(ext)
        if not language:
            print(f"Skipping {file_path} - unknown language")
            continue

        print(f"  Processing {file_path} ({language})...")
        chunks = chunk_file(file_path, language)
        all_chunks.extend(chunks)

    print(f"\nTotal chunks: {len(all_chunks)}")

    # Track relationships
    print("\nAnalyzing relationships...")
    tracker = ASTRelationshipTracker()
    relationships = tracker.infer_relationships(all_chunks)
    print(f"Found {len(relationships)} relationships")

    # Count relationship types
    rel_types = {}
    for rel in relationships:
        rel_type = rel.relationship_type.value
        rel_types[rel_type] = rel_types.get(rel_type, 0) + 1

    print("\nRelationship breakdown:")
    for rel_type, count in sorted(rel_types.items()):
        print(f"  {rel_type}: {count}")

    # Export to Neo4j
    print(f"\nExporting to Neo4j format: {output_path}")
    orchestrator = StructuredExportOrchestrator()
    neo4j_exporter = Neo4jExporter()
    orchestrator.register_exporter(ExportFormat.NEO4J, neo4j_exporter)

    orchestrator.export(all_chunks, relationships, output_path)
    print("Export complete!")

    # Print sample queries
    print("\nSample Neo4j queries to try:")
    print("1. Find all classes:")
    print("   MATCH (c:CodeChunk {node_type: 'class_definition'}) RETURN c.content")
    print("\n2. Find inheritance hierarchy:")
    print("   MATCH (child)-[:INHERITS]->(parent) RETURN child, parent")
    print("\n3. Find most connected chunks:")
    print(
        "   MATCH (c:CodeChunk)-[r]-() RETURN c, COUNT(r) as connections ORDER BY connections DESC LIMIT 10",
    )
    print("\n4. Find call graph:")
    print("   MATCH path = (caller)-[:CALLS*1..3]->(callee) RETURN path")


def main():
    """Main entry point."""
    # Example Python files
    example_dir = Path(__file__).parent

    # Create a sample codebase
    sample_dir = example_dir / "sample_codebase"
    sample_dir.mkdir(exist_ok=True)

    # Create base module
    (sample_dir / "base.py").write_text(
        '''
class BaseModel:
    """Base model for all entities."""
    def __init__(self, id):
        self.id = id

    def save(self):
        """Save the model."""
        print(f"Saving {self.__class__.__name__} with id {self.id}")

    def delete(self):
        """Delete the model."""
        print(f"Deleting {self.__class__.__name__} with id {self.id}")


class BaseManager:
    """Base manager for model operations."""
    def __init__(self, model_class):
        self.model_class = model_class

    def create(self, **kwargs):
        """Create a new instance."""
        return self.model_class(**kwargs)

    def find(self, id):
        """Find instance by id."""
        return self.model_class(id)
''',
    )

    # Create user module
    (sample_dir / "users.py").write_text(
        '''
from .base import BaseModel, BaseManager


class User(BaseModel):
    """User model."""
    def __init__(self, id, name, email):
        super().__init__(id)
        self.name = name
        self.email = email

    def send_email(self, message):
        """Send email to user."""
        print(f"Sending email to {self.email}: {message}")


class UserManager(BaseManager):
    """Manager for User operations."""
    def __init__(self):
        super().__init__(User)

    def find_by_email(self, email):
        """Find user by email."""
        # Simplified implementation
        return User(1, "Test User", email)

    def authenticate(self, email, password):
        """Authenticate user."""
        user = self.find_by_email(email)
        # Simplified auth
        return user if password == "password" else None
''',
    )

    # Create posts module
    (sample_dir / "posts.py").write_text(
        '''
from .base import BaseModel, BaseManager
from .users import User, UserManager


class Post(BaseModel):
    """Blog post model."""
    def __init__(self, id, title, content, author_id):
        super().__init__(id)
        self.title = title
        self.content = content
        self.author_id = author_id

    def get_author(self):
        """Get the post author."""
        user_manager = UserManager()
        return user_manager.find(self.author_id)

    def publish(self):
        """Publish the post."""
        self.save()
        author = self.get_author()
        author.send_email(f"Your post '{self.title}' has been published!")


class PostManager(BaseManager):
    """Manager for Post operations."""
    def __init__(self):
        super().__init__(Post)

    def find_by_author(self, author_id):
        """Find posts by author."""
        # Simplified implementation
        return [
            Post(1, "First Post", "Content 1", author_id),
            Post(2, "Second Post", "Content 2", author_id)
        ]

    def get_recent_posts(self, limit=10):
        """Get recent posts."""
        # Simplified implementation
        return [Post(i, f"Post {i}", f"Content {i}", 1) for i in range(limit)]
''',
    )

    # Create main app
    (sample_dir / "app.py").write_text(
        '''
from .users import UserManager
from .posts import PostManager


class BlogApp:
    """Main blog application."""
    def __init__(self):
        self.user_manager = UserManager()
        self.post_manager = PostManager()

    def create_post(self, user_email, password, title, content):
        """Create a new blog post."""
        # Authenticate user
        user = self.user_manager.authenticate(user_email, password)
        if not user:
            raise ValueError("Authentication failed")

        # Create post
        post = self.post_manager.create(
            id=None,
            title=title,
            content=content,
            author_id=user.id
        )

        # Publish it
        post.publish()
        return post

    def get_user_posts(self, user_id):
        """Get all posts by a user."""
        return self.post_manager.find_by_author(user_id)


def main():
    """Run the blog application."""
    app = BlogApp()

    # Create a post
    post = app.create_post(
        "user@example.com",
        "password",
        "Hello World",
        "This is my first blog post!"
    )

    # Get user's posts
    posts = app.get_user_posts(1)
    for p in posts:
        print(f"- {p.title}")


if __name__ == "__main__":
    main()
''',
    )

    # Export to Neo4j
    source_files = list(sample_dir.glob("*.py"))
    output_path = example_dir / "blog_codebase.cypher"

    export_to_neo4j(source_files, output_path)

    print("\nTo import into Neo4j:")
    print("1. Start Neo4j database")
    print("2. Open Neo4j Browser")
    print(f"3. Copy contents of {output_path}")
    print("4. Paste and run in Neo4j Browser")


if __name__ == "__main__":
    main()

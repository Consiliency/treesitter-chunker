#!/usr/bin/env python3
"""Example: Visualize code dependencies using GraphML and DOT formats."""

import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.chunker import chunk_file
from chunker.export import (
    ASTRelationshipTracker,
    DOTExporter,
    GraphMLExporter,
    StructuredExportOrchestrator,
)
from chunker.interfaces.export import ExportFormat, RelationshipType


def create_dependency_graph(source_files, output_base, format="dot"):
    """Create dependency graph visualization.

    Args:
        source_files: List of source files to analyze
        output_base: Base path for output files (without extension)
        format: Export format ("dot" or "graphml")
    """
    # Collect all chunks
    all_chunks = []

    print("Analyzing source files...")
    for file_path in source_files:
        # Determine language
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
            continue

        print(f"  Processing {file_path} ({language})...")
        chunks = chunk_file(file_path, language)
        all_chunks.extend(chunks)

    print(f"\nFound {len(all_chunks)} code chunks")

    # Track relationships
    print("\nAnalyzing dependencies...")
    tracker = ASTRelationshipTracker()
    relationships = tracker.infer_relationships(all_chunks)

    # Filter to specific relationship types for cleaner visualization
    dependency_types = [
        RelationshipType.IMPORTS,
        RelationshipType.DEPENDS_ON,
        RelationshipType.USES,
        RelationshipType.CALLS,
        RelationshipType.INHERITS,
        RelationshipType.IMPLEMENTS,
    ]

    filtered_relationships = [
        r for r in relationships if r.relationship_type in dependency_types
    ]

    print(f"Found {len(filtered_relationships)} dependency relationships")

    # Create exporter based on format
    orchestrator = StructuredExportOrchestrator()

    if format == "dot":
        exporter = DOTExporter()

        # Customize styles for different relationship types
        exporter.set_edge_style("imports", {"color": "gray", "style": "dashed"})
        exporter.set_edge_style("depends_on", {"color": "orange", "style": "dotted"})
        exporter.set_edge_style("calls", {"color": "blue", "style": "solid"})
        exporter.set_edge_style(
            "inherits",
            {"color": "red", "style": "solid", "arrowhead": "empty"},
        )
        exporter.set_edge_style(
            "implements",
            {"color": "green", "style": "dashed", "arrowhead": "empty"},
        )

        # Set layout algorithm
        exporter.add_layout_hints("LR")  # Left to right layout

        output_path = f"{output_base}.dot"
        export_format = ExportFormat.DOT

    else:  # graphml
        exporter = GraphMLExporter()
        exporter.set_node_attributes(["node_type", "language", "file_path"])
        exporter.set_edge_attributes(["relationship_type"])

        output_path = f"{output_base}.graphml"
        export_format = ExportFormat.GRAPHML

    orchestrator.register_exporter(export_format, exporter)

    # Export
    print(f"\nExporting to {format.upper()} format: {output_path}")
    orchestrator.export(all_chunks, filtered_relationships, output_path)

    # Try to render if DOT format and Graphviz is available
    if format == "dot":
        try:
            # Try to render to SVG
            svg_path = f"{output_base}.svg"
            print(f"\nRendering to SVG: {svg_path}")
            subprocess.run(
                ["dot", "-Tsvg", output_path, "-o", svg_path],
                check=True,
                capture_output=True,
            )
            print("Rendering complete!")

            # Also create PNG for easier viewing
            png_path = f"{output_base}.png"
            print(f"Rendering to PNG: {png_path}")
            subprocess.run(
                ["dot", "-Tpng", output_path, "-o", png_path],
                check=True,
                capture_output=True,
            )
            print("Rendering complete!")

        except subprocess.CalledProcessError as e:
            print(f"Error rendering graph: {e}")
            print("Make sure Graphviz is installed (apt install graphviz)")
        except FileNotFoundError:
            print("Graphviz not found. Install it to render the graph:")
            print("  Ubuntu/Debian: sudo apt install graphviz")
            print("  macOS: brew install graphviz")
            print("  Windows: https://graphviz.org/download/")

    return output_path


def create_sample_project():
    """Create a sample project structure for visualization."""
    sample_dir = Path(__file__).parent / "sample_project"
    sample_dir.mkdir(exist_ok=True)

    # Create config module
    (sample_dir / "config.py").write_text(
        '''
"""Configuration module."""

import os
from pathlib import Path


class Config:
    """Application configuration."""
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / "logs"
    
    # Database settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_NAME = os.getenv("DB_NAME", "myapp")
    
    # API settings
    API_KEY = os.getenv("API_KEY", "")
    API_TIMEOUT = 30
    
    @classmethod
    def get_db_url(cls):
        """Get database connection URL."""
        return f"postgresql://{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
''',
    )

    # Create database module
    (sample_dir / "database.py").write_text(
        '''
"""Database connection module."""

from .config import Config


class Database:
    """Database connection handler."""
    
    def __init__(self):
        self.connection_url = Config.get_db_url()
        self.connection = None
        
    def connect(self):
        """Establish database connection."""
        print(f"Connecting to {self.connection_url}")
        # Simulated connection
        self.connection = {"connected": True}
        
    def disconnect(self):
        """Close database connection."""
        if self.connection:
            print("Disconnecting from database")
            self.connection = None
            
    def execute(self, query):
        """Execute a database query."""
        if not self.connection:
            self.connect()
        print(f"Executing: {query}")
        return []


def get_db():
    """Get database instance."""
    return Database()
''',
    )

    # Create models module
    (sample_dir / "models.py").write_text(
        '''
"""Data models module."""

from .database import get_db


class Model:
    """Base model class."""
    
    table_name = None
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
            
    def save(self):
        """Save model to database."""
        db = get_db()
        query = f"INSERT INTO {self.table_name} ..."
        db.execute(query)
        
    @classmethod
    def find(cls, id):
        """Find model by ID."""
        db = get_db()
        query = f"SELECT * FROM {cls.table_name} WHERE id = {id}"
        result = db.execute(query)
        return cls(**result[0]) if result else None


class User(Model):
    """User model."""
    
    table_name = "users"
    
    def __init__(self, id=None, username=None, email=None):
        super().__init__(id=id, username=username, email=email)
        
    def get_profile(self):
        """Get user profile."""
        return Profile.find_by_user(self.id)


class Profile(Model):
    """User profile model."""
    
    table_name = "profiles"
    
    def __init__(self, id=None, user_id=None, bio=None):
        super().__init__(id=id, user_id=user_id, bio=bio)
        
    @classmethod
    def find_by_user(cls, user_id):
        """Find profile by user ID."""
        db = get_db()
        query = f"SELECT * FROM {cls.table_name} WHERE user_id = {user_id}"
        result = db.execute(query)
        return cls(**result[0]) if result else None
''',
    )

    # Create services module
    (sample_dir / "services.py").write_text(
        '''
"""Business logic services."""

from .models import User, Profile
from .database import get_db
from .config import Config


class UserService:
    """User-related business logic."""
    
    def __init__(self):
        self.db = get_db()
        
    def create_user(self, username, email, bio=None):
        """Create a new user with profile."""
        # Create user
        user = User(username=username, email=email)
        user.save()
        
        # Create profile
        if bio:
            profile = Profile(user_id=user.id, bio=bio)
            profile.save()
            
        return user
        
    def get_user_with_profile(self, user_id):
        """Get user with their profile."""
        user = User.find(user_id)
        if user:
            user.profile = user.get_profile()
        return user
        
    def update_user_email(self, user_id, new_email):
        """Update user email."""
        user = User.find(user_id)
        if user:
            user.email = new_email
            user.save()
        return user


class NotificationService:
    """Notification service."""
    
    def __init__(self):
        self.api_key = Config.API_KEY
        
    def send_email(self, user, subject, message):
        """Send email notification."""
        print(f"Sending email to {user.email}: {subject}")
        # Simulated email sending
        
    def notify_user_created(self, user):
        """Send notification for new user."""
        self.send_email(
            user,
            "Welcome!",
            f"Welcome to our app, {user.username}!"
        )
''',
    )

    # Create main app
    (sample_dir / "app.py").write_text(
        '''
"""Main application module."""

from .services import UserService, NotificationService
from .config import Config


class Application:
    """Main application class."""
    
    def __init__(self):
        self.user_service = UserService()
        self.notification_service = NotificationService()
        self.config = Config()
        
    def register_user(self, username, email, bio=None):
        """Register a new user."""
        # Create user
        user = self.user_service.create_user(username, email, bio)
        
        # Send welcome notification
        self.notification_service.notify_user_created(user)
        
        return user
        
    def get_user_info(self, user_id):
        """Get complete user information."""
        return self.user_service.get_user_with_profile(user_id)
        

def main():
    """Run the application."""
    app = Application()
    
    # Register a user
    user = app.register_user(
        "john_doe",
        "john@example.com",
        "Software developer"
    )
    
    # Get user info
    user_info = app.get_user_info(user.id)
    print(f"User: {user_info.username} ({user_info.email})")


if __name__ == "__main__":
    main()
''',
    )

    return sample_dir


def main():
    """Main entry point."""
    # Create sample project
    print("Creating sample project...")
    sample_dir = create_sample_project()

    # Get all Python files
    source_files = list(sample_dir.glob("*.py"))

    # Create output directory
    output_dir = Path(__file__).parent / "visualizations"
    output_dir.mkdir(exist_ok=True)

    # Generate DOT visualization
    print("\n" + "=" * 50)
    print("Generating DOT visualization...")
    dot_output = output_dir / "dependencies"
    create_dependency_graph(source_files, dot_output, format="dot")

    # Generate GraphML visualization
    print("\n" + "=" * 50)
    print("Generating GraphML visualization...")
    graphml_output = output_dir / "dependencies"
    create_dependency_graph(source_files, graphml_output, format="graphml")

    print("\n" + "=" * 50)
    print("Visualization complete!")
    print("\nOutput files:")
    print(f"  - {dot_output}.dot (Graphviz format)")
    print(f"  - {graphml_output}.graphml (yEd/Gephi format)")

    # Check if images were generated
    svg_path = f"{dot_output}.svg"
    png_path = f"{dot_output}.png"
    if Path(svg_path).exists():
        print(f"  - {svg_path} (Vector image)")
    if Path(png_path).exists():
        print(f"  - {png_path} (Raster image)")

    print("\nViewing options:")
    print("  - DOT: Use Graphviz, VSCode extensions, or online viewers")
    print("  - GraphML: Use yEd, Gephi, or Cytoscape")
    print("  - SVG/PNG: Any image viewer or web browser")


if __name__ == "__main__":
    main()

"""Tests for ConfigProcessor.

Tests section-based chunking for INI, TOML, YAML, and JSON files.
"""

import toml
import yaml
import json

import pytest

from chunker.processors.config import ConfigProcessor, ProcessorConfig
from chunker.types import CodeChunk


class TestConfigProcessor:
    """Test ConfigProcessor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = ConfigProcessor()

    def test_can_handle_by_extension(self):
        """Test file handling detection by extension."""
        # Should handle these
        assert self.processor.can_handle("config.ini")
        assert self.processor.can_handle("settings.cfg")
        assert self.processor.can_handle("app.conf")
        assert self.processor.can_handle("pyproject.toml")
        assert self.processor.can_handle("config.yaml")
        assert self.processor.can_handle("settings.yml")
        assert self.processor.can_handle("config.json")

        # Should not handle these
        assert not self.processor.can_handle("script.py")
        assert not self.processor.can_handle("document.txt")
        assert not self.processor.can_handle("image.png")

    def test_can_handle_by_name(self):
        """Test file handling detection by name."""
        assert self.processor.can_handle("config")
        assert self.processor.can_handle("settings")
        assert self.processor.can_handle(".env")
        assert not self.processor.can_handle("readme")

    def test_format_detection_ini(self):
        """Test INI fmt detection."""
        ini_content = """
[database]
host = localhost
port = 3306

[cache]
enabled = true
ttl = 3600
"""
        assert self.processor.detect_format("config.ini", ini_content) == "ini"
        assert self.processor.detect_format("unknown", ini_content) == "ini"

    def test_format_detection_json(self):
        """Test JSON fmt detection."""
        json_content = '{"name": "test", "version": "1.0.0"}'
        assert self.processor.detect_format("config.json", json_content) == "json"
        assert self.processor.detect_format("unknown", json_content) == "json"

    def test_format_detection_yaml(self):
        """Test YAML fmt detection."""
        yaml_content = """
name: test
version: 1.0.0
features:
  - authentication
  - logging
"""
        # Skip if yaml not available
        try:

            assert self.processor.detect_format("config.yaml", yaml_content) == "yaml"
            assert self.processor.detect_format("unknown", yaml_content) == "yaml"
        except ImportError:
            pytest.skip("yaml library not available")

    def test_format_detection_toml(self):
        """Test TOML fmt detection."""
        toml_content = """
[package]
name = "test"
version = "1.0.0"

[[dependencies]]
name = "requests"
version = "2.28.0"
"""
        # Skip if toml not available
        try:

            assert (
                self.processor.detect_format("pyproject.toml", toml_content) == "toml"
            )
            assert self.processor.detect_format("unknown", toml_content) == "toml"
        except ImportError:
            pytest.skip("toml library not available")

    def test_chunk_ini_file(self):
        """Test chunking INI files."""
        ini_content = """# Global settings
debug = true

[server]
host = 0.0.0.0
port = 8080
workers = 4

[database]
host = localhost
port = 5432
name = myapp
user = admin

[cache]
enabled = true
host = redis.local
port = 6379
"""

        chunks = self.processor.process("config.ini", ini_content)

        # Should have chunks for global section and each section
        assert len(chunks) >= 3

        # Check chunk properties
        section_names = []
        for chunk in chunks:
            assert isinstance(chunk, CodeChunk)
            assert chunk.language == "ini"
            assert chunk.file_path == "config.ini"
            assert chunk.start_line > 0
            assert chunk.end_line >= chunk.start_line
            assert chunk.content

            # Extract section names
            if "section" in chunk.metadata:
                section_names.append(chunk.metadata["section"])

        # Should have found our sections
        assert "server" in section_names
        assert "database" in section_names
        assert "cache" in section_names

    def test_chunk_ini_with_grouping(self):
        """Test INI chunking with related section grouping."""
        ini_content = """
[server1]
host = server1.example.com
port = 8080

[server2]
host = server2.example.com
port = 8080

[server3]
host = server3.example.com
port = 8080

[database]
host = db.example.com
port = 5432
"""

        # Enable grouping
        processor = ConfigProcessor(ProcessorConfig(group_related=True))
        chunks = processor.process("servers.ini", ini_content)

        # Should group server sections
        grouped_chunk = None
        for chunk in chunks:
            if chunk.metadata.get("grouped"):
                grouped_chunk = chunk
                break

        assert grouped_chunk is not None
        assert len(grouped_chunk.metadata["sections"]) > 1
        assert all("server" in s for s in grouped_chunk.metadata["sections"])

    def test_chunk_json_object(self):
        """Test chunking JSON objects."""
        json_content = json.dumps(
            {
                "name": "myapp",
                "version": "1.0.0",
                "dependencies": {
                    "express": "^4.18.0",
                    "mongoose": "^6.0.0",
                },
                "scripts": {
                    "start": "node index.js",
                    "test": "jest",
                },
            },
            indent=2,
        )

        chunks = self.processor.process("package.json", json_content)

        # Check chunks
        for chunk in chunks:
            assert isinstance(chunk, CodeChunk)
            assert chunk.language == "json"
            assert chunk.file_path == "package.json"
            assert chunk.content

            # Should be valid JSON
            parsed = json.loads(chunk.content)
            assert isinstance(parsed, dict | list)

    def test_chunk_json_array(self):
        """Test chunking JSON arrays."""
        # Create large array
        data = [{"id": i, "name": f"item{i}"} for i in range(100)]
        json_content = json.dumps(data, indent=2)

        processor = ConfigProcessor(ProcessorConfig(chunk_size=20))
        chunks = processor.process("data.json", json_content)

        # Should have multiple chunks
        assert len(chunks) > 1

        for chunk in chunks:
            assert chunk.node_type in ["json_array", "json_array_chunk"]
            # Each chunk should be valid JSON
            parsed = json.loads(chunk.content)
            assert isinstance(parsed, list)

    def test_chunk_yaml_file(self):
        """Test chunking YAML files."""
        yaml_content = """
# Application configuration
name: myapp
version: 1.0.0

server:
  host: 0.0.0.0
  port: 8080
  ssl:
    enabled: true
    cert: /path/to/cert

database:
  host: localhost
  port: 5432
  credentials:
    user: admin
    password: secret

features:
  - authentication
  - logging
  - caching
"""

        try:
        except ImportError:
            pytest.skip("yaml library not available")

        chunks = self.processor.process("config.yaml", yaml_content)

        # Should have chunks for root keys and sections
        assert len(chunks) >= 2

        section_names = []
        for chunk in chunks:
            assert chunk.language == "yaml"
            if "section" in chunk.metadata:
                section_names.append(chunk.metadata["section"])

        assert "server" in section_names
        assert "database" in section_names

    def test_chunk_toml_file(self):
        """Test chunking TOML files."""
        toml_content = """
# Project configuration
name = "myproject"
version = "0.1.0"

[build]
target = "x86_64"
opt-level = 3

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[[bin]]
name = "app"
path = "src/main.rs"

[[bin]]
name = "cli"
path = "src/cli.rs"
"""

        try:
        except ImportError:
            pytest.skip("toml library not available")

        chunks = self.processor.process("Cargo.toml", toml_content)

        # Should have chunks for root content and tables
        assert len(chunks) >= 3

        # Check for different table types
        table_types = set()
        for chunk in chunks:
            assert chunk.language == "toml"
            table_types.add(chunk.node_type)

        assert "toml_root" in table_types or "toml_table" in table_types

    def test_preserve_comments(self):
        """Test that comments are preserved in chunks."""
        ini_content = """
# Global configuration
# These settings apply to all sections
debug = true

[server]
# Server configuration
host = 0.0.0.0  # Bind to all interfaces
port = 8080     # Default port
"""

        chunks = self.processor.process("config.ini", ini_content)

        # Comments should be preserved
        for chunk in chunks:
            if "[server]" in chunk.content:
                assert "# Server configuration" in chunk.content
                assert "# Bind to all interfaces" in chunk.content

    def test_handle_malformed_config(self):
        """Test handling of malformed configuration files."""
        malformed_ini = """
[section1
key = value

[section2]
invalid line without equals
key2 = value2
"""

        # Should still detect as INI
        fmt = self.processor.detect_format("bad.ini", malformed_ini)
        assert fmt == "ini"

        # Should handle parsing errors gracefully
        try:
            chunks = self.processor.process("bad.ini", malformed_ini)
            # Should produce some chunks even if not perfect
            assert len(chunks) > 0
        except (FileNotFoundError, OSError, SyntaxError) as e:
            # Should be a meaningful error
            assert "parse" in str(e).lower() or "fmt" in str(e).lower()

    def test_empty_file_handling(self):
        """Test handling of empty files."""
        assert self.processor.detect_format("empty.ini", "") is None
        assert self.processor.detect_format("empty.json", "   ") is None

    def test_env_file_handling(self):
        """Test handling of .env files."""
        env_content = """
# Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp

# API Keys
API_KEY=secret123
SECRET_KEY=verysecret

# Feature flags
ENABLE_CACHE=true
DEBUG_MODE=false
"""

        # .env files should be detected as INI fmt
        assert self.processor.can_handle(".env")
        fmt = self.processor.detect_format(".env", env_content)
        assert fmt == "ini"

        chunks = self.processor.process(".env", env_content)
        assert len(chunks) > 0

    def test_get_supported_formats(self):
        """Test getting supported formats."""
        formats = self.processor.get_supported_formats()
        assert "ini" in formats
        assert "json" in formats
        # YAML and TOML depend on library availability

    def test_get_format_extensions(self):
        """Test getting fmt extensions."""
        extensions = self.processor.get_format_extensions()
        assert ".ini" in extensions["ini"]
        assert ".cfg" in extensions["ini"]
        assert ".json" in extensions["json"]
        assert ".yaml" in extensions["yaml"]
        assert ".toml" in extensions["toml"]

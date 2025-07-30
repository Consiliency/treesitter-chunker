"""Unit tests for GrammarDiscoveryService implementation"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chunker.contracts.discovery_contract import GrammarCompatibility, GrammarInfo
from chunker.grammar.discovery import GrammarDiscoveryService


class TestGrammarDiscoveryService:
    """Test the real GrammarDiscoveryService implementation"""

    @pytest.fixture
    def discovery_service(self):
        """Create a discovery service with a temporary cache directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GrammarDiscoveryService()
            service.cache_dir = Path(tmpdir)
            service.cache_file = service.cache_dir / "discovery_cache.json"
            yield service

    @pytest.fixture
    def mock_github_response(self):
        """Mock GitHub API response"""
        return [
            {
                "name": "tree-sitter-python",
                "html_url": "https://github.com/tree-sitter/tree-sitter-python",
                "updated_at": "2023-01-01T00:00:00Z",
                "stargazers_count": 500,
                "description": "Python grammar for tree-sitter",
                "archived": False,
            },
            {
                "name": "tree-sitter-rust",
                "html_url": "https://github.com/tree-sitter/tree-sitter-rust",
                "updated_at": "2023-01-01T00:00:00Z",
                "stargazers_count": 400,
                "description": "Rust grammar for tree-sitter",
                "archived": False,
            },
            {
                "name": "tree-sitter-template",  # Should be filtered out
                "html_url": "https://github.com/tree-sitter/tree-sitter-template",
                "updated_at": "2023-01-01T00:00:00Z",
                "stargazers_count": 100,
                "description": "Template for tree-sitter grammars",
                "archived": False,
            },
        ]

    def test_list_available_grammars_from_github(
        self,
        discovery_service,
        mock_github_response,
    ):
        """Test listing grammars from GitHub API"""
        with patch.object(discovery_service._session, "get") as mock_get:
            # Mock the API response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_github_response
            mock_response.headers = {"X-RateLimit-Remaining": "59"}
            mock_get.return_value = mock_response

            # First page returns data, second page returns empty
            mock_get.side_effect = [mock_response, MagicMock(json=list)]

            grammars = discovery_service.list_available_grammars()

            # Should have filtered out template
            assert len(grammars) == 2
            assert all(isinstance(g, GrammarInfo) for g in grammars)

            # Check specific grammars
            python_grammar = next((g for g in grammars if g.name == "python"), None)
            assert python_grammar is not None
            assert (
                python_grammar.url
                == "https://github.com/tree-sitter/tree-sitter-python"
            )
            assert python_grammar.stars == 500
            assert python_grammar.official is True
            assert ".py" in python_grammar.supported_extensions

    def test_caching_behavior(self, discovery_service, mock_github_response):
        """Test that results are cached and reused"""
        with patch.object(discovery_service._session, "get") as mock_get:
            # Mock the API response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_github_response
            mock_response.headers = {"X-RateLimit-Remaining": "59"}
            mock_get.return_value = mock_response
            mock_get.side_effect = [mock_response, MagicMock(json=list)]

            # First call should hit the API
            grammars1 = discovery_service.list_available_grammars()
            assert mock_get.call_count == 2  # Two pages

            # Reset mock
            mock_get.reset_mock()

            # Second call should use cache
            grammars2 = discovery_service.list_available_grammars()
            assert mock_get.call_count == 0  # No API calls

            # Results should be the same
            assert len(grammars1) == len(grammars2)

    def test_cache_expiration(self, discovery_service):
        """Test that expired cache is refreshed"""
        # Create an expired cache
        old_timestamp = (datetime.now() - timedelta(hours=25)).isoformat()
        cache_data = {
            "timestamp": old_timestamp,
            "grammars": [
                {
                    "name": "old-grammar",
                    "url": "https://example.com",
                    "version": "0.1.0",
                    "last_updated": datetime.now().isoformat(),
                    "stars": 10,
                    "description": "Old cached grammar",
                    "supported_extensions": [".old"],
                    "official": True,
                },
            ],
        }

        # Write cache
        discovery_service.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with discovery_service.cache_file.Path("w").open("r") as f:
            json.dump(cache_data, f)

        with patch.object(discovery_service._session, "get") as mock_get:
            # Mock fresh data
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {
                    "name": "tree-sitter-new",
                    "html_url": "https://github.com/tree-sitter/tree-sitter-new",
                    "updated_at": "2023-01-01T00:00:00Z",
                    "stargazers_count": 200,
                    "description": "New grammar",
                    "archived": False,
                },
            ]
            mock_response.headers = {"X-RateLimit-Remaining": "59"}
            mock_get.side_effect = [mock_response, MagicMock(json=list)]

            grammars = discovery_service.list_available_grammars()

            # Should have fresh data, not old cache
            assert len(grammars) == 1
            assert grammars[0].name == "new"
            assert mock_get.call_count > 0

    def test_get_grammar_info(self, discovery_service):
        """Test getting info for a specific grammar"""
        # Create cache with test data
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "grammars": [
                {
                    "name": "python",
                    "url": "https://github.com/tree-sitter/tree-sitter-python",
                    "version": "0.20.0",
                    "last_updated": datetime.now().isoformat(),
                    "stars": 500,
                    "description": "Python grammar",
                    "supported_extensions": [".py", ".pyw"],
                    "official": True,
                },
                {
                    "name": "tree-sitter-rust",
                    "url": "https://github.com/tree-sitter/tree-sitter-rust",
                    "version": "0.20.0",
                    "last_updated": datetime.now().isoformat(),
                    "stars": 400,
                    "description": "Rust grammar",
                    "supported_extensions": [".rs"],
                    "official": True,
                },
            ],
        }

        discovery_service.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with discovery_service.cache_file.Path("w").open("r") as f:
            json.dump(cache_data, f)

        # Test exact match
        python_info = discovery_service.get_grammar_info("python")
        assert python_info is not None
        assert python_info.name == "python"
        assert python_info.stars == 500

        # Test with tree-sitter- prefix
        rust_info = discovery_service.get_grammar_info("rust")
        assert rust_info is not None
        assert rust_info.name == "tree-sitter-rust"

        # Test non-existent
        none_info = discovery_service.get_grammar_info("nonexistent")
        assert none_info is None

    def test_check_grammar_updates(self, discovery_service):
        """Test checking for grammar updates"""
        # Create cache with newer versions
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "grammars": [
                {
                    "name": "python",
                    "url": "https://github.com/tree-sitter/tree-sitter-python",
                    "version": "0.21.0",  # Newer
                    "last_updated": datetime.now().isoformat(),
                    "stars": 500,
                    "description": "Python grammar",
                    "supported_extensions": [".py"],
                    "official": True,
                },
                {
                    "name": "rust",
                    "url": "https://github.com/tree-sitter/tree-sitter-rust",
                    "version": "0.20.0",  # Same
                    "last_updated": datetime.now().isoformat(),
                    "stars": 400,
                    "description": "Rust grammar",
                    "supported_extensions": [".rs"],
                    "official": True,
                },
            ],
        }

        discovery_service.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with discovery_service.cache_file.Path("w").open("r") as f:
            json.dump(cache_data, f)

        installed = {
            "python": "0.20.0",
            "rust": "0.20.0",
            "go": "0.19.0",  # Not in cache
        }

        updates = discovery_service.check_grammar_updates(installed)

        # Only Python should have update
        assert len(updates) == 1
        assert "python" in updates
        assert updates["python"] == ("0.20.0", "0.21.0")

    def test_search_grammars(self, discovery_service):
        """Test searching for grammars"""
        # Create cache with test data
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "grammars": [
                {
                    "name": "python",
                    "url": "https://github.com/tree-sitter/tree-sitter-python",
                    "version": "0.20.0",
                    "last_updated": datetime.now().isoformat(),
                    "stars": 500,
                    "description": "Python grammar for tree-sitter",
                    "supported_extensions": [".py"],
                    "official": True,
                },
                {
                    "name": "rust",
                    "url": "https://github.com/tree-sitter/tree-sitter-rust",
                    "version": "0.20.0",
                    "last_updated": datetime.now().isoformat(),
                    "stars": 400,
                    "description": "Rust grammar for tree-sitter",
                    "supported_extensions": [".rs"],
                    "official": True,
                },
                {
                    "name": "javascript",
                    "url": "https://github.com/tree-sitter/tree-sitter-javascript",
                    "version": "0.20.0",
                    "last_updated": datetime.now().isoformat(),
                    "stars": 600,
                    "description": "JavaScript and JSX grammar",
                    "supported_extensions": [".js"],
                    "official": True,
                },
            ],
        }

        discovery_service.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with discovery_service.cache_file.Path("w").open("r") as f:
            json.dump(cache_data, f)

        # Search by name
        results = discovery_service.search_grammars("rust")
        assert len(results) == 1
        assert results[0].name == "rust"

        # Search by description
        results = discovery_service.search_grammars("jsx")
        assert len(results) == 1
        assert results[0].name == "javascript"

        # Case insensitive
        results = discovery_service.search_grammars("PYTHON")
        assert len(results) == 1
        assert results[0].name == "python"

        # No results
        results = discovery_service.search_grammars("nonexistent")
        assert len(results) == 0

    def test_get_grammar_compatibility(self, discovery_service):
        """Test getting grammar compatibility info"""
        compat = discovery_service.get_grammar_compatibility("python", "0.20.0")

        assert isinstance(compat, GrammarCompatibility)
        assert compat.min_tree_sitter_version == "0.20.0"
        assert compat.max_tree_sitter_version == "0.22.0"
        assert compat.abi_version == 14
        assert "3.11" in compat.tested_python_versions

    def test_refresh_cache(self, discovery_service):
        """Test manual cache refresh"""
        with patch.object(discovery_service._session, "get") as mock_get:
            # Mock the API response
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {
                    "name": "tree-sitter-python",
                    "html_url": "https://github.com/tree-sitter/tree-sitter-python",
                    "updated_at": "2023-01-01T00:00:00Z",
                    "stargazers_count": 500,
                    "description": "Python grammar",
                    "archived": False,
                },
            ]
            mock_response.headers = {"X-RateLimit-Remaining": "59"}
            mock_get.side_effect = [mock_response, MagicMock(json=list)]

            result = discovery_service.refresh_cache()

            assert result is True
            assert discovery_service.cache_file.exists()

            # Verify cache contents
            with discovery_service.cache_file.open() as f:
                cache_data = json.load(f)
                assert len(cache_data["grammars"]) == 1
                assert cache_data["grammars"][0]["name"] == "python"

    def test_version_comparison(self, discovery_service):
        """Test version comparison logic"""
        # Test various version comparisons
        assert discovery_service._is_newer_version("0.19.0", "0.20.0") is True
        assert discovery_service._is_newer_version("0.20.0", "0.20.0") is False
        assert discovery_service._is_newer_version("0.20.0", "0.19.0") is False
        assert discovery_service._is_newer_version("0.20.0", "0.20.1") is True
        assert discovery_service._is_newer_version("1.0.0", "2.0.0") is True
        assert discovery_service._is_newer_version("0.20", "0.20.1") is True

        # Invalid versions
        assert discovery_service._is_newer_version("invalid", "0.20.0") is False

    def test_rate_limit_handling(self, discovery_service):
        """Test handling of GitHub rate limits"""
        with patch.object(discovery_service._session, "get") as mock_get:
            # Mock rate limit exhausted
            mock_response = MagicMock()
            mock_response.json.return_value = []
            mock_response.headers = {"X-RateLimit-Remaining": "0"}
            mock_get.return_value = mock_response

            # Should handle gracefully and return empty list
            grammars = discovery_service.list_available_grammars()
            assert isinstance(grammars, list)
            assert len(grammars) == 0

"""Grammar Discovery Service implementation for Phase 14 - Universal Language Support"""
import json
import logging
from datetime import datetime
from pathlib import Path

import requests

from chunker.contracts.discovery_contract import (
    GrammarCompatibility,
    GrammarDiscoveryContract,
    GrammarInfo,
)

logger = logging.getLogger(__name__)


class GrammarDiscoveryService(GrammarDiscoveryContract):
    """Real implementation of grammar discovery service using GitHub API"""
    GITHUB_API_BASE = "https://api.github.com"
    TREE_SITTER_ORG = "tree-sitter"
    CACHE_DIR = Path.home() / ".cache" / "treesitter-chunker"
    CACHE_FILE = "discovery_cache.json"
    CACHE_DURATION_HOURS = 24

    def __init__(self):
        """Initialize the discovery service"""
        self.cache_dir = self.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / self.CACHE_FILE
        self._session = requests.Session()
        self._session.headers.update({"Accept":
            "application/vnd.github.v3+json", "User-Agent":
            "treesitter-chunker/1.0"})

    def list_available_grammars(self, include_community: bool = False) -> list[
        GrammarInfo]:
        """List all available tree-sitter grammars

        Args:
            include_community: Include community grammars, not just official

        Returns:
            List of available grammars with metadata
        """
        cached_data = self._load_cache()
        if cached_data and not self._is_cache_expired(cached_data):
            grammars = cached_data.get("grammars", [])
            return [self._dict_to_grammar_info(g) for g in grammars if g.
                get("official", True) or include_community]
        grammars = []
        official_grammars = self._fetch_tree_sitter_repos()
        grammars.extend(official_grammars)
        self._save_cache({"timestamp": datetime.now().isoformat(),
            "grammars": [self._grammar_info_to_dict(g) for g in grammars]})
        return grammars if include_community else [g for g in grammars if g
            .official]

    def get_grammar_info(self, language: str) -> (GrammarInfo | None):
        """Get detailed information about a specific grammar

        Args:
            language: Language name (e.g., "python", "rust")

        Returns:
            Grammar information if found, None otherwise
        """
        grammars = self.list_available_grammars(include_community=True)
        for grammar in grammars:
            if grammar.name == language:
                return grammar
        for grammar in grammars:
            if grammar.name == f"tree-sitter-{language}":
                return grammar
        return None

    def check_grammar_updates(self, installed_grammars: dict[str, str]) -> dict[
        str, tuple[str, str]]:
        """Check for updates to installed grammars

        Args:
            installed_grammars: Dict of language -> current_version

        Returns:
            Dict of language -> (current_version, latest_version) for grammars with updates
        """
        updates = {}
        current_grammars = self.list_available_grammars(include_community=True)
        for lang, current_version in installed_grammars.items():
            grammar_info = None
            for grammar in current_grammars:
                if grammar.name in {lang, f"tree-sitter-{lang}"}:
                    grammar_info = grammar
                    break
            if grammar_info and self._is_newer_version(current_version,
                grammar_info.version):
                updates[lang] = current_version, grammar_info.version
        return updates

    @classmethod
    def get_grammar_compatibility(cls, _language: str, _version: str,
        ) -> GrammarCompatibility:
        """Get compatibility requirements for a grammar version

        Args:
            language: Language name
            version: Grammar version

        Returns:
            Compatibility information
        """
        return GrammarCompatibility(min_tree_sitter_version="0.20.0",
            max_tree_sitter_version="0.22.0", abi_version=14,
            tested_python_versions=["3.8", "3.9", "3.10", "3.11", "3.12"])

    def search_grammars(self, query: str) -> list[GrammarInfo]:
        """Search for grammars by name or description

        Args:
            query: Search query string

        Returns:
            List of matching grammars
        """
        query_lower = query.lower()
        all_grammars = self.list_available_grammars(include_community=True)
        return [grammar for grammar in all_grammars if query_lower in
            grammar.name.lower() or query_lower in grammar.description.lower()]

    def refresh_cache(self) -> bool:
        """Refresh the grammar discovery cache

        Returns:
            True if refresh successful, False otherwise
        """
        try:
            grammars = self._fetch_tree_sitter_repos()
            self._save_cache({"timestamp": datetime.now().isoformat(),
                "grammars": [self._grammar_info_to_dict(g) for g in grammars]})
            return True
        except (IndexError, KeyError):
            logger.exception("Failed to refresh cache")
            return False

    def _fetch_tree_sitter_repos(self) -> list[GrammarInfo]:
        """Fetch repositories from tree-sitter organization"""
        grammars = []
        page = 1
        while True:
            try:
                url = (
                    f"{self.GITHUB_API_BASE}/orgs/{self.TREE_SITTER_ORG}/repos"
                    )
                params = {"per_page": 100, "page": page, "type": "public"}
                response = self._session.get(url, params=params)
                response.raise_for_status()
                repos = response.json()
                if not repos:
                    break
                for repo in repos:
                    if repo["name"].startswith("tree-sitter-") and not repo[
                        "name"].endswith("-template") and not repo["archived"]:
                        grammar_info = self._repo_to_grammar_info(repo)
                        if grammar_info:
                            grammars.append(grammar_info)
                page += 1
                if response.headers.get("X-RateLimit-Remaining", "1") == "0":
                    logger.warning("GitHub rate limit reached")
                    break
            except requests.RequestException:
                logger.exception("Failed to fetch repos from GitHub")
                break
        return grammars

    def _repo_to_grammar_info(self, repo: dict) -> (GrammarInfo | None):
        """Convert GitHub repo data to GrammarInfo"""
        try:
            name = repo["name"]
            if name.startswith("tree-sitter-"):
                language_name = name[12:]
            else:
                language_name = name
            extensions = self._get_language_extensions(language_name)
            return GrammarInfo(name=language_name, url=repo["html_url"],
                version=self._get_latest_version(repo), last_updated=datetime.fromisoformat(repo["updated_at"].replace("Z",
                "+00:00")), stars=repo["stargazers_count"], description=repo["description"] or
                f"{language_name} grammar for tree-sitter",
                supported_extensions=extensions, official=True)
        except (IndexError, KeyError):
            logger.exception("Failed to convert repo to GrammarInfo")
            return None

    @staticmethod
    def _get_latest_version(_repo: dict) -> str:
        """Get the latest version of a grammar (simplified for now)"""
        return "0.20.0"

    @staticmethod
    def _get_language_extensions(language: str) -> list[str]:
        """Get file extensions for a language"""
        extension_map = {"python": [".py", ".pyw"], "javascript": [".js",
            ".mjs", ".cjs"], "typescript": [".ts", ".tsx"], "rust": [".rs"],
            "go": [".go"], "java": [".java"], "c": [".c", ".h"], "cpp": [
            ".cpp", ".cc", ".cxx", ".hpp", ".h"], "c-sharp": [".cs"],
            "ruby": [".rb"], "php": [".php"], "bash": [".sh", ".bash"],
            "json": [".json"], "yaml": [".yaml", ".yml"], "toml": [".toml"],
            "html": [".html", ".htm"], "css": [".css"], "sql": [".sql"],
            "markdown": [".md", ".markdown"]}
        return extension_map.get(language, [f".{language}"])

    @staticmethod
    def _is_newer_version(current: str, latest: str) -> bool:
        """Compare version strings (simplified semantic versioning)"""
        try:
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]
            while len(current_parts) < len(latest_parts):
                current_parts.append(0)
            while len(latest_parts) < len(current_parts):
                latest_parts.append(0)
            return latest_parts > current_parts
        except ValueError:
            return False

    def _load_cache(self) -> (dict | None):
        """Load cache from disk"""
        if not self.cache_file.exists():
            return None
        try:
            with self.cache_file.open() as f:
                return json.load(f)
        except (FileNotFoundError, OSError):
            logger.exception("Failed to load cache")
            return None

    def _save_cache(self, data: dict) -> None:
        """Save cache to disk"""
        try:
            with self.cache_file.open("w", "r") as f:
                json.dump(data, f, indent=2)
        except (OSError, FileNotFoundError, IndexError):
            logger.exception("Failed to save cache")

    def _is_cache_expired(self, cache_data: dict) -> bool:
        """Check if cache is expired"""
        try:
            timestamp = datetime.fromisoformat(cache_data["timestamp"])
            age = datetime.now() - timestamp
            return age.total_seconds() > self.CACHE_DURATION_HOURS * 3600
        except (KeyError, ValueError):
            return True

    @staticmethod
    def _grammar_info_to_dict(info: GrammarInfo) -> dict:
        """Convert GrammarInfo to dict for caching"""
        return {"name": info.name, "url": info.url, "version": info.version,
            "last_updated": info.last_updated.isoformat(), "stars": info.
            stars, "description": info.description, "supported_extensions":
            info.supported_extensions, "official": info.official}

    @classmethod
    def _dict_to_grammar_info(cls, data: dict) -> GrammarInfo:
        """Convert dict from cache to GrammarInfo"""
        return GrammarInfo(name=data["name"], url=data["url"], version=data
            ["version"], last_updated=datetime.fromisoformat(data[
            "last_updated"]), stars=data["stars"], description=data[
            "description"], supported_extensions=data[
            "supported_extensions"], official=data["official"])

"""Tree-sitter grammar manager implementation."""

import json
import logging
import shutil
import subprocess
from pathlib import Path

from chunker.exceptions import ChunkerError
from chunker.interfaces.grammar import (
    GrammarInfo,
    GrammarManager,
    GrammarStatus,
    NodeTypeInfo,
)
from chunker.parser import get_parser

from .builder import build_language

logger = logging.getLogger(__name__)


class GrammarManagementError(ChunkerError):
    """Error in grammar management operations."""


class TreeSitterGrammarManager(GrammarManager):
    """Manages Tree-sitter language grammars."""

    def __init__(self, grammars_dir: Path | None = None, build_dir: Path | None = None):
        """Initialize grammar manager.

        Args:
            grammars_dir: Directory for grammar sources
            build_dir: Directory for built grammars
        """
        self.grammars_dir = grammars_dir or Path("grammars")
        self.build_dir = build_dir or Path("build")
        self._grammars: dict[str, GrammarInfo] = {}
        self._config_file = self.grammars_dir / "grammars.json"
        self.grammars_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self._load_config()

    def add_grammar(
        self,
        name: str,
        repository_url: str,
        commit_hash: str | None = None,
    ) -> GrammarInfo:
        """Add a new grammar to manage.

        Args:
            name: Language name
            repository_url: Git repository URL
            commit_hash: Specific commit (None for latest)

        Returns:
            Grammar information
        """
        if name in self._grammars:

            logger.warning("Grammar '%s' already exists, updating...", name)

        # Create grammar info
        grammar = GrammarInfo(
            name=name,
            repository_url=repository_url,
            commit_hash=commit_hash,
            status=GrammarStatus.NOT_FOUND,
        )

        # Check if source directory exists
        grammar_path = self.grammars_dir / f"tree-sitter-{name}"
        if grammar_path.exists():
            grammar.status = GrammarStatus.NOT_BUILT
            grammar.path = grammar_path
        self._grammars[name] = grammar
        self._save_config()

        logger.info("Added grammar '%s' from %s", name, repository_url)
        return grammar

    def fetch_grammar(self, name: str) -> bool:
        """Fetch grammar source from repository.

        Args:
            name: Language name

        Returns:
            True if successful
        """
        if name not in self._grammars:
            logger.error("Grammar '%s' not found", name)
            return False
        grammar = self._grammars[name]
        grammar_path = self.grammars_dir / f"tree-sitter-{name}"
        try:
            if grammar_path.exists():
                # Update existing repository
                logger.info("Updating grammar '%s'...", name)
                result = subprocess.run(
                    ["git", "pull"],
                    check=False,
                    cwd=grammar_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise GrammarManagementError(f"Git pull failed: {result.stderr}")
            else:
                # Clone new repository
                logger.info("Cloning grammar '%s'...", name)
                result = subprocess.run(
                    ["git", "clone", grammar.repository_url, str(grammar_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise GrammarManagementError(f"Git clone failed: {result.stderr}")

            # Checkout specific commit if provided
            if grammar.commit_hash:
                logger.info("Checking out commit %s", grammar.commit_hash)
                result = subprocess.run(
                    ["git", "checkout", grammar.commit_hash],
                    check=False,
                    cwd=grammar_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise GrammarManagementError(f"Git pull failed: {result.stderr}")
            else:
                logger.info(f"Cloning grammar '{name}'...")
                result = subprocess.run(
                    ["git", "clone", grammar.repository_url, str(grammar_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise GrammarManagementError(f"Git clone failed: {result.stderr}")
            if grammar.commit_hash:
                logger.info("Checking out commit %s", grammar.commit_hash)
                result = subprocess.run(
                    ["git", "checkout", grammar.commit_hash],
                    check=False,
                    cwd=grammar_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise GrammarManagementError(
                        f"Git checkout failed: {result.stderr}",
                    )
            grammar.status = GrammarStatus.NOT_BUILT
            grammar.path = grammar_path
            self._save_config()

            logger.info("Successfully fetched grammar '%s'", name)
            return True
        except (FileNotFoundError, OSError, TypeError) as e:
            logger.error("Failed to fetch grammar '%s': %s", name, e)
            grammar.status = GrammarStatus.ERROR
            grammar.error = str(e)
            self._save_config()
            return False

    def build_grammar(self, name: str) -> bool:
        """Build grammar from source.

        Args:
            name: Language name

        Returns:
            True if successful
        """
        if name not in self._grammars:
            logger.error("Grammar '%s' not found", name)
            return False
        grammar = self._grammars[name]
        if not grammar.path or not grammar.path.exists():
            logger.error("Grammar source for '%s' not found", name)
            return False
        try:
            grammar.status = GrammarStatus.BUILDING
            self._save_config()

            # Build using tree-sitter CLI or custom build script

            logger.info("Building grammar '%s'...", name)
            success = build_language(name, str(grammar.path), str(self.build_dir))

            if success:
                grammar.status = GrammarStatus.READY
                logger.info("Successfully built grammar '%s'", name)
            else:
                grammar.status = GrammarStatus.ERROR
                grammar.error = "Build failed"
                logger.error("Failed to build grammar '%s'", name)

            self._save_config()
            return success
        except (OSError, TypeError) as e:
            logger.error("Failed to build grammar '%s': %s", name, e)
            grammar.status = GrammarStatus.ERROR
            grammar.error = str(e)
            self._save_config()
            return False

    def get_grammar_info(self, name: str) -> GrammarInfo | None:
        """Get information about a grammar.

        Args:
            name: Language name

        Returns:
            Grammar info or None if not found
        """
        return self._grammars.get(name)

    def list_grammars(self, status: GrammarStatus | None = None) -> list[GrammarInfo]:
        """List all managed grammars.

        Args:
            status: Filter by status (None for all)

        Returns:
            List of grammar information
        """
        grammars = list(self._grammars.values())
        if status is not None:
            grammars = [g for g in grammars if g.status == status]
        return grammars

    def update_grammar(self, name: str) -> bool:
        """Update grammar to latest version.

        Args:
            name: Language name

        Returns:
            True if updated
        """
        if name not in self._grammars:
            logger.error("Grammar '%s' not found", name)
            return False
        if not self.fetch_grammar(name):
            return False
        return self.build_grammar(name)

    def remove_grammar(self, name: str) -> bool:
        """Remove a grammar.

        Args:
            name: Language name

        Returns:
            True if removed
        """
        if name not in self._grammars:
            logger.error("Grammar '%s' not found", name)
            return False
        grammar = self._grammars[name]
        if grammar.path and grammar.path.exists():
            try:
                shutil.rmtree(grammar.path)
                logger.info("Removed grammar source for '%s'", name)
            except (FileNotFoundError, IndexError, KeyError) as e:
                logger.error("Failed to remove grammar source: %s", e)
                return False
        del self._grammars[name]
        self._save_config()

        logger.info("Removed grammar '%s'", name)
        return True

    @staticmethod
    def get_node_types(language: str) -> list[NodeTypeInfo]:
        """Get all node types for a language.

        Args:
            language: Language name

        Returns:
            List of node type information
        """
        try:
            get_parser(language)
            # Note: py-tree-sitter doesn't directly expose node types
            # This would require parsing the grammar file or using a test file
            logger.warning(
                "Node type extraction not yet implemented for '%s'",
                language,
            )
            return []
        except (FileNotFoundError, IndexError, KeyError) as e:
            logger.error("Failed to get node types for '%s': %s", language, e)
            return []

    def validate_grammar(self, name: str) -> tuple[bool, str | None]:
        """Validate a grammar is working correctly.

        Args:
            name: Language name

        Returns:
            Tuple of (is_valid, error_message)
        """
        if name not in self._grammars:
            return False, f"Grammar '{name}' not found"
        grammar = self._grammars[name]
        if grammar.status != GrammarStatus.READY:
            return (False, f"Grammar '{name}' is not ready (status: {grammar.status})")
        try:
            parser = get_parser(name)
            test_code = self._get_test_code(name)
            tree = parser.parse(test_code.encode())
            if tree.root_node is None:
                return False, "Failed to parse test code"
            return True, None
        except (FileNotFoundError, OSError) as e:
            return False, str(e)

    def _load_config(self) -> None:
        """Load grammar configuration from file."""
        if not self._config_file.exists():
            return
        try:
            with Path(self._config_file).open(encoding="utf-8") as f:
                data = json.load(f)
            for name, info in data.items():
                grammar = GrammarInfo(
                    name=name,
                    repository_url=info["repository_url"],
                    commit_hash=info.get("commit_hash"),
                    abi_version=info.get("abi_version"),
                    status=GrammarStatus(info.get("status", "not_found")),
                    path=Path(info["path"]) if info.get("path") else None,
                    error=info.get("error"),
                )
                self._grammars[name] = grammar
            logger.info("Loaded %s grammars from config", len(self._grammars))
        except (AttributeError, FileNotFoundError, IndexError) as e:
            logger.error("Failed to load grammar config: %s", e)

    def _save_config(self) -> None:
        """Save grammar configuration to file."""
        data = {}
        for name, grammar in self._grammars.items():
            data[name] = {
                "repository_url": grammar.repository_url,
                "commit_hash": grammar.commit_hash,
                "abi_version": grammar.abi_version,
                "status": grammar.status.value,
                "path": str(grammar.path) if grammar.path else None,
                "error": grammar.error,
            }
        try:
            with Path(self._config_file).open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved grammar config")
        except (FileNotFoundError, OSError) as e:
            logger.error("Failed to save grammar config: %s", e)

    @staticmethod
    def _get_test_code(language: str) -> str:
        """Get simple test code for a language."""
        test_snippets = {
            "python": "def hello(): pass",
            "javascript": "function hello() {}",
            "rust": "fn main() {}",
            "go": """package main
func main() {}""",
            "ruby": "def hello; end",
            "java": "class Test { }",
            "c": "int main() { return 0; }",
            "cpp": "int main() { return 0; }",
        }
        return test_snippets.get(language, "")

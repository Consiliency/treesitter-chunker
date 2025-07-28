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

logger = logging.getLogger(__name__)


class GrammarManagementError(ChunkerError):
    """Error in grammar management operations."""


class TreeSitterGrammarManager(GrammarManager):
    """Manages Tree-sitter language grammars."""

    def __init__(
        self,
        grammars_dir: Path | None = None,
        build_dir: Path | None = None,
    ):
        """Initialize grammar manager.

        Args:
            grammars_dir: Directory for grammar sources
            build_dir: Directory for built grammars
        """
        self.grammars_dir = grammars_dir or Path("grammars")
        self.build_dir = build_dir or Path("build")
        self._grammars: dict[str, GrammarInfo] = {}
        self._config_file = self.grammars_dir / "grammars.json"

        # Create directories if they don't exist
        self.grammars_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)

        # Load existing grammar configuration
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
        # Check if already exists
        if name in self._grammars:
            logger.warning(f"Grammar '{name}' already exists, updating...")

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

        # Store grammar info
        self._grammars[name] = grammar
        self._save_config()

        logger.info(f"Added grammar '{name}' from {repository_url}")
        return grammar

    def fetch_grammar(self, name: str) -> bool:
        """Fetch grammar source from repository.

        Args:
            name: Language name

        Returns:
            True if successful
        """
        if name not in self._grammars:
            logger.error(f"Grammar '{name}' not found")
            return False

        grammar = self._grammars[name]
        grammar_path = self.grammars_dir / f"tree-sitter-{name}"

        try:
            if grammar_path.exists():
                # Update existing repository
                logger.info(f"Updating grammar '{name}'...")
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
                logger.info(f"Cloning grammar '{name}'...")
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
                    raise GrammarManagementError(
                        f"Git checkout failed: {result.stderr}",
                    )

            # Update grammar info
            grammar.status = GrammarStatus.NOT_BUILT
            grammar.path = grammar_path
            self._save_config()

            logger.info(f"Successfully fetched grammar '{name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to fetch grammar '{name}': {e}")
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
            logger.error(f"Grammar '{name}' not found")
            return False

        grammar = self._grammars[name]
        if not grammar.path or not grammar.path.exists():
            logger.error(f"Grammar source for '{name}' not found")
            return False

        try:
            grammar.status = GrammarStatus.BUILDING
            self._save_config()

            # Build using tree-sitter CLI or custom build script
            from .builder import build_language

            logger.info(f"Building grammar '{name}'...")
            success = build_language(name, str(grammar.path), str(self.build_dir))

            if success:
                grammar.status = GrammarStatus.READY
                logger.info(f"Successfully built grammar '{name}'")
            else:
                grammar.status = GrammarStatus.ERROR
                grammar.error = "Build failed"
                logger.error(f"Failed to build grammar '{name}'")

            self._save_config()
            return success

        except Exception as e:
            logger.error(f"Failed to build grammar '{name}': {e}")
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

    def list_grammars(
        self,
        status: GrammarStatus | None = None,
    ) -> list[GrammarInfo]:
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
            logger.error(f"Grammar '{name}' not found")
            return False

        # Fetch latest version
        if not self.fetch_grammar(name):
            return False

        # Rebuild grammar
        return self.build_grammar(name)

    def remove_grammar(self, name: str) -> bool:
        """Remove a grammar.

        Args:
            name: Language name

        Returns:
            True if removed
        """
        if name not in self._grammars:
            logger.error(f"Grammar '{name}' not found")
            return False

        grammar = self._grammars[name]

        # Remove source directory
        if grammar.path and grammar.path.exists():
            try:
                shutil.rmtree(grammar.path)
                logger.info(f"Removed grammar source for '{name}'")
            except Exception as e:
                logger.error("Failed to remove grammar source: %s", e)
                return False

        # Remove from registry
        del self._grammars[name]
        self._save_config()

        logger.info(f"Removed grammar '{name}'")
        return True

    def get_node_types(self, language: str) -> list[NodeTypeInfo]:
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
            logger.warning(f"Node type extraction not yet implemented for '{language}'")
            return []
        except Exception as e:
            logger.error(f"Failed to get node types for '{language}': {e}")
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
            return False, f"Grammar '{name}' is not ready (status: {grammar.status})"

        try:
            # Try to create a parser
            parser = get_parser(name)

            # Try to parse some simple code
            test_code = self._get_test_code(name)
            tree = parser.parse(test_code.encode())

            if tree.root_node is None:
                return False, "Failed to parse test code"

            return True, None

        except Exception as e:
            return False, str(e)

    def _load_config(self) -> None:
        """Load grammar configuration from file."""
        if not self._config_file.exists():
            return

        try:
            with open(self._config_file) as f:
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

        except Exception as e:
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
            with open(self._config_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved grammar config")
        except Exception as e:
            logger.error("Failed to save grammar config: %s", e)

    def _get_test_code(self, language: str) -> str:
        """Get simple test code for a language."""
        test_snippets = {
            "python": "def hello(): pass",
            "javascript": "function hello() {}",
            "rust": "fn main() {}",
            "go": "package main\nfunc main() {}",
            "ruby": "def hello; end",
            "java": "class Test { }",
            "c": "int main() { return 0; }",
            "cpp": "int main() { return 0; }",
        }
        return test_snippets.get(language, "")

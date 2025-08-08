"""Gitignore pattern matching for repository processing."""

import os
import re
from pathlib import Path


class GitignorePattern:
    """Represents a single gitignore pattern with its rules."""

    def __init__(self, pattern: str, base_dir: Path):
        """
        Initialize a gitignore pattern.

        Args:
            pattern: The pattern string from gitignore
            base_dir: The directory containing the gitignore file
        """
        self.original = pattern
        self.base_dir = base_dir
        self.is_negation = False
        self.is_directory_only = False
        self.is_anchored = False

        # Parse the pattern
        self._parse_pattern()

    def _parse_pattern(self):
        """Parse the gitignore pattern and set flags."""
        pattern = self.original.strip()

        # Skip empty lines and comments
        if not pattern or pattern.startswith("#"):
            self.pattern = None
            return

        # Handle negation
        if pattern.startswith("!"):
            self.is_negation = True
            pattern = pattern[1:]

        # Handle directory-only patterns
        if pattern.endswith("/"):
            self.is_directory_only = True
            pattern = pattern[:-1]

        # Handle anchored patterns (containing / but not starting with /)
        if "/" in pattern:
            self.is_anchored = True
            # Convert to relative path pattern
            if pattern.startswith("/"):
                pattern = pattern[1:]

        # Convert gitignore pattern to regex
        self.pattern = self._gitignore_to_regex(pattern)

    def _gitignore_to_regex(self, pattern: str) -> re.Pattern:
        """Convert gitignore pattern to regex pattern."""
        # Escape special regex characters except * and ?
        pattern = re.escape(pattern)

        # Convert gitignore wildcards to regex
        pattern = pattern.replace(
            r"\*\*/",
            ".*/",
        )  # ** matches any number of directories
        pattern = pattern.replace(r"\*\*", ".*")  # ** at end matches anything
        pattern = pattern.replace(r"\*", "[^/]*")  # * matches anything except /
        pattern = pattern.replace(
            r"\?",
            "[^/]",
        )  # ? matches any single character except /

        # Add anchoring
        pattern = "^" + pattern if self.is_anchored else "(^|.*/)" + pattern

        # Add end anchor
        pattern += "(/.*)?$"

        return re.compile(pattern)

    def matches(self, path: Path, is_dir: bool = False) -> bool:
        """
        Check if the pattern matches the given path.

        Args:
            path: Path to check (relative to base_dir)
            is_dir: Whether the path is a directory

        Returns:
            True if pattern matches
        """
        if self.pattern is None:
            return False

        # Directory-only patterns shouldn't match files
        if self.is_directory_only and not is_dir:
            return False

        # Convert path to string for matching
        path_str = str(path).replace(os.sep, "/")

        return bool(self.pattern.match(path_str))


class GitignoreMatcher:
    """Matches paths against gitignore patterns."""

    def __init__(self, patterns: list[str] | None = None, base_dir: Path | None = None):
        """
        Initialize the matcher with patterns.

        Args:
            patterns: List of gitignore patterns
            base_dir: Base directory for pattern matching
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.patterns: list[GitignorePattern] = []
        self._cache = {}

        if patterns:
            self.add_patterns(patterns)

        # Add default patterns
        self._add_default_patterns()

    def _add_default_patterns(self):
        """Add default patterns that should always be ignored."""
        default_patterns = [
            ".git/",
            ".svn/",
            ".hg/",
            ".bzr/",
            "__pycache__/",
            "*.pyc",
            "*.pyo",
            ".DS_Store",
            "Thumbs.db",
            ".vscode/",
            ".idea/",
            "*.swp",
            "*.swo",
            "*~",
            ".cache/",
            "node_modules/",
            ".env",
            ".venv/",
            "venv/",
        ]

        for pattern in default_patterns:
            self.patterns.append(GitignorePattern(pattern, self.base_dir))

    def add_patterns(self, patterns: list[str], base_dir: Path | None = None):
        """
        Add patterns from a list.

        Args:
            patterns: List of gitignore patterns
            base_dir: Base directory for these patterns
        """
        base = Path(base_dir) if base_dir else self.base_dir

        for pattern in patterns:
            pattern_obj = GitignorePattern(pattern, base)
            if pattern_obj.pattern is not None:
                self.patterns.append(pattern_obj)

    def load_gitignore_file(self, gitignore_path: Path):
        """
        Load patterns from a gitignore file.

        Args:
            gitignore_path: Path to the gitignore file
        """
        if not gitignore_path.exists():
            return

        base_dir = gitignore_path.parent
        patterns = []

        try:
            with Path(gitignore_path).open(encoding="utf-8") as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith("#"):
                        patterns.append(stripped_line)

            self.add_patterns(patterns, base_dir)
        except (OSError, FileNotFoundError, IndexError):
            # Silently ignore errors reading gitignore
            pass

    def should_ignore(self, path: str | Path, is_dir: bool = False) -> bool:
        """
        Check if a path should be ignored.

        Args:
            path: Path to check (relative to base_dir)
            is_dir: Whether the path is a directory

        Returns:
            True if the path should be ignored
        """
        path = Path(path)

        # Check cache
        cache_key = (str(path), is_dir)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Make path relative to base_dir
        try:
            if path.is_absolute():
                path = path.relative_to(self.base_dir)
        except ValueError:
            # Path is not under base_dir
            self._cache[cache_key] = False
            return False

        # Check all patterns
        ignored = False
        for pattern in self.patterns:
            if pattern.matches(path, is_dir):
                ignored = not pattern.is_negation

        self._cache[cache_key] = ignored
        return ignored

    def filter_paths(self, paths: list[Path], check_is_dir: bool = True) -> list[Path]:
        """
        Filter a list of paths, removing ignored ones.

        Args:
            paths: List of paths to filter
            check_is_dir: Whether to check if paths are directories

        Returns:
            List of paths that should not be ignored
        """
        result = []
        for path in paths:
            is_dir = path.is_dir() if check_is_dir else False
            if not self.should_ignore(path, is_dir):
                result.append(path)
        return result

    def clear_cache(self):
        """Clear the pattern matching cache."""
        self._cache.clear()


def load_gitignore_patterns(repo_path: Path) -> GitignoreMatcher:
    """
    Load all gitignore patterns from a repository.

    Searches for .gitignore files at all levels and combines their patterns.

    Args:
        repo_path: Path to the repository root

    Returns:
        GitignoreMatcher configured with all patterns
    """
    matcher = GitignoreMatcher(base_dir=repo_path)

    # Find all .gitignore files in the repository
    for gitignore_path in repo_path.rglob(".gitignore"):
        # Skip .gitignore files that are themselves ignored
        relative_path = gitignore_path.relative_to(repo_path)
        if not matcher.should_ignore(relative_path.parent, is_dir=True):
            matcher.load_gitignore_file(gitignore_path)

    return matcher

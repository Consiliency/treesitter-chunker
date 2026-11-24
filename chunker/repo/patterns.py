"""Gitignore pattern matching for repository processing."""

import os
import re
from pathlib import Path

from pathspec.patterns.gitwildmatch import GitWildMatchPattern


class GitignorePattern:
    """A compiled rule for one entry relative to its declaring directory."""

    def __init__(self, pattern: str, base_dir: Path):
        self.original = pattern
        self.base_dir = base_dir
        # Git discards unescaped trailing spaces, even after an escaped space.
        line = pattern.rstrip(" ")
        if line != pattern and (len(line) - len(line.rstrip("\\"))) % 2:
            line += " "
        self.is_negation = line.startswith("!")
        self.is_directory_only = line.endswith("/")
        line = line.removesuffix("/")
        self.is_anchored = "/" in line
        self.pattern: re.Pattern[str] | None = None
        if line in ("", "!") or line.startswith("#"):
            return
        # pathspec 0.12 strips whitespace at both ends. Protect significant
        # leading whitespace and terminal whitespace other than escaped space.
        if line[0].isspace():
            line = "\\" + line
        if line[-1].isspace() and not line.endswith("\\ "):
            prefix = line[:-1]
            if (len(prefix) - len(prefix.rstrip("\\"))) % 2:
                prefix = prefix[:-1]
            line = f"{prefix}[{line[-1]}]"
        try:
            regex, _ = GitWildMatchPattern.pattern_to_regex(line)
            if regex is not None:
                self.pattern = re.compile(regex, re.DOTALL)
        except (ValueError, re.error):
            # One unusable rule must not discard the rest of its file.
            pass

    def matches(self, path: Path, is_dir: bool = False) -> bool:
        if self.pattern is None or (self.is_directory_only and not is_dir):
            return False
        match = self.pattern.fullmatch(path.as_posix())
        # pathspec's ps_d captures an implicit match of an ancestor. We decide
        # ancestors separately, so that explicitly reopening one takes effect.
        return match is not None and match.groupdict().get("ps_d") is None


class GitignoreMatcher:
    """Match repository entries against rules from their ancestor directories."""

    def __init__(self, patterns: list[str] | None = None, base_dir: Path | None = None):
        self.base_dir = Path(os.path.normpath(Path.cwd() / (base_dir or Path())))
        self.patterns: list[GitignorePattern] = []
        self._groups: dict[str, list[GitignorePattern]] = {}
        self._cache: dict[tuple[str, bool], bool] = {}
        if patterns:
            self.add_patterns(patterns)
        self._add_default_patterns()

    def _add_default_patterns(self) -> None:
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

        self.add_patterns(default_patterns)

    def add_patterns(self, patterns: list[str], base_dir: Path | None = None) -> None:
        """Append rules declared in base_dir (the matcher root by default)."""
        base = (
            Path(os.path.normpath(Path.cwd() / base_dir)) if base_dir else self.base_dir
        )
        if not base.is_relative_to(self.base_dir):
            return
        group = self._groups.setdefault(base.relative_to(self.base_dir).as_posix(), [])
        for line in patterns:
            rule = GitignorePattern(line, base)
            if rule.pattern is not None:
                group.append(rule)
                self.patterns.append(rule)
        self.clear_cache()

    def load_gitignore_file(self, gitignore_path: Path) -> None:
        """Read a regular rule file without following a .gitignore symlink."""
        try:
            if not gitignore_path.is_file(follow_symlinks=False):
                return
            with gitignore_path.open(
                encoding="utf-8-sig", errors="surrogateescape", newline="\n"
            ) as rules:
                lines = [line.removesuffix("\n").removesuffix("\r") for line in rules]
            self.add_patterns(lines, gitignore_path.parent)
        except OSError:
            pass

    def _entry_ignored(self, entry: Path, directory: bool) -> bool:
        # Search highest precedence first: nearest file, then latest line.
        for base in entry.parents:
            if rules := self._groups.get(base.as_posix()):
                local = entry.relative_to(base)
                for rule in reversed(rules):
                    if rule.matches(local, directory):
                        return not rule.is_negation
        return False

    def should_ignore(self, path: str | Path, is_dir: bool = False) -> bool:
        """Return whether this entry or one of its ancestor directories is ignored."""
        absolute = Path(os.path.normpath(self.base_dir / path))
        if not absolute.is_relative_to(self.base_dir):
            return False
        relative = absolute.relative_to(self.base_dir)
        key = (relative.as_posix(), is_dir)
        if key in self._cache:
            return self._cache[key]

        ignored = False
        for entry in (*reversed(relative.parents), relative):
            if not entry.parts:
                continue
            directory = entry != relative or is_dir
            entry_key = (entry.as_posix(), directory)
            if entry_key not in self._cache:
                self._cache[entry_key] = self._entry_ignored(entry, directory)
            if self._cache[entry_key]:
                ignored = True
                break
        self._cache[key] = ignored
        return ignored

    def filter_paths(self, paths: list[Path], check_is_dir: bool = True) -> list[Path]:
        """Retain eligible paths in their original order and spelling."""
        return [
            path
            for path in paths
            if not self.should_ignore(
                path,
                check_is_dir and (self.base_dir / path).is_dir(follow_symlinks=False),
            )
        ]

    def clear_cache(self) -> None:
        self._cache.clear()


def load_gitignore_patterns(repo_path: Path) -> GitignoreMatcher:
    """Collect .gitignore rules top-down, pruning excluded directories."""
    matcher = GitignoreMatcher(base_dir=repo_path)
    for base, directories, files in matcher.base_dir.walk():
        if ".gitignore" in files:
            matcher.load_gitignore_file(base / ".gitignore")
        directories[:] = [
            name
            for name in directories
            if not matcher.should_ignore(base / name, is_dir=True)
        ]
    return matcher

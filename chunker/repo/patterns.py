"""Gitignore pattern matching for repository processing."""

import os
import re
import warnings
from pathlib import Path

try:
    from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern
except ImportError:  # pathspec 0.x
    from pathspec.patterns.gitwildmatch import (
        GitWildMatchPattern as GitIgnoreSpecPattern,
    )


def _ends_in_escape(text: str) -> bool:
    return (len(text) - len(text.rstrip("\\"))) % 2 == 1


# NUL cannot occur in a filename. Marking the end of both the pattern and the
# entry prevents pathspec's implicit match of descendants, across its supported
# compiler versions. Directory inheritance is handled by the matcher.
_ENTRY_END = "\0"


class GitignorePattern:
    """A compiled rule for one entry relative to its declaring directory."""

    def __init__(self, pattern: str, base_dir: Path):
        self.original = pattern
        self.base_dir = base_dir
        # Git discards unescaped trailing spaces, even after an escaped space.
        line = pattern.rstrip(" ")
        if line != pattern and _ends_in_escape(line):
            line += " "
        self.is_negation = line.startswith("!")
        self.is_directory_only = line.endswith("/")
        line = line.removesuffix("/")
        self.is_anchored = "/" in line
        self.pattern: re.Pattern[str] | None = None
        if line in ("", "!") or line.startswith("#"):
            return
        # Git accepts an escaped internal separator. pathspec splits on the
        # slash first and would treat the preceding escape as dangling.
        segments = line.split("/")
        for index, segment in enumerate(segments[:-1]):
            if _ends_in_escape(segment):
                if segment in ("\\", "!\\"):
                    return
                segments[index] = segment[:-1]
        if _ends_in_escape(segments[-1]):
            return
        line = "/".join(segments)
        if line[0].isspace():
            line = "\\" + line
        if line.endswith("/**"):
            # Contents include the immediate children of this directory.
            line += "/*"
        try:
            regex, _ = GitIgnoreSpecPattern.pattern_to_regex(line + _ENTRY_END)
            if regex is not None:
                # Older compilers emit valid Git bracket escapes such as [[]
                # verbatim. Python warns about potential future set syntax.
                with warnings.catch_warnings(action="ignore", category=FutureWarning):
                    self.pattern = re.compile(regex, re.DOTALL)
        except (ValueError, re.error):
            # One unusable rule must not discard the rest of its file.
            pass

    def matches(self, path: Path, is_dir: bool = False) -> bool:
        if self.pattern is None or (self.is_directory_only and not is_dir):
            return False
        return self.pattern.fullmatch(path.as_posix() + _ENTRY_END) is not None


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
        spelling = entry.as_posix()
        base = spelling.rpartition("/")[0]
        while True:
            if rules := self._groups.get(base or "."):
                local = Path(spelling[len(base) + 1 :]) if base else entry
                for rule in reversed(rules):
                    if rule.matches(local, directory):
                        return not rule.is_negation
            if not base:
                return False
            base = base.rpartition("/")[0]

    def should_ignore(self, path: str | Path, is_dir: bool = False) -> bool:
        """Return whether this entry or one of its ancestor directories is ignored."""
        relative = path if isinstance(path, Path) else Path(path)
        if relative.anchor or ".." in relative.parts:
            absolute = Path(os.path.normpath(self.base_dir / relative))
            if not absolute.is_relative_to(self.base_dir):
                return False
            relative = absolute.relative_to(self.base_dir)

        # Walk up to the nearest known decision, then evaluate only missing
        # entries from parent to child. Siblings reuse their parent directly.
        pending = []
        entry, directory = relative, is_dir
        while entry.parts:
            key = (entry.as_posix(), directory)
            if key in self._cache:
                ignored = self._cache[key]
                break
            pending.append((entry, key))
            entry, directory = entry.parent, True
        else:
            ignored = False
        for entry, key in reversed(pending):
            ignored = ignored or self._entry_ignored(entry, key[1])
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

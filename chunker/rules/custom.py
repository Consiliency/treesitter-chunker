"""Base implementations for custom chunking rules."""

import re
from re import Pattern

from tree_sitter import Node

from chunker.interfaces.rules import CommentBlockRule, CustomRule, RegexRule, RuleMatch
from chunker.types import CodeChunk


class BaseCustomRule(CustomRule):
    """Base implementation with common functionality for custom rules."""

    def __init__(self, name: str, description: str, priority: int = 0):
        self._name = name
        self._description = description
        self._priority = priority

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description

    def get_priority(self) -> int:
        return self._priority


class BaseRegexRule(RegexRule):
    """Base implementation for regex-based rules."""

    def __init__(
        self,
        name: str,
        description: str,
        pattern: str,
        priority: int = 0,
        cross_boundaries: bool = True,
        multiline: bool = True,
    ):
        self._name = name
        self._description = description
        self._priority = priority
        self._cross_boundaries = cross_boundaries
        self._pattern = re.compile(pattern, re.MULTILINE if multiline else 0)

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description

    def get_priority(self) -> int:
        return self._priority

    def get_pattern(self) -> Pattern:
        return self._pattern

    def should_cross_node_boundaries(self) -> bool:
        return self._cross_boundaries

    def matches(self, node: Node, source: bytes) -> bool:
        """Check if pattern matches within node text."""
        if not self._cross_boundaries:
            node_text = source[node.start_byte : node.end_byte]
            return bool(
                self._pattern.search(node_text.decode("utf-8", errors="replace")),
            )
        return False

    def extract_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
    ) -> CodeChunk | None:
        """Extract chunk based on regex match within node."""
        if not self._cross_boundaries:
            node_text = source[node.start_byte : node.end_byte]
            match = self._pattern.search(node_text.decode("utf-8", errors="replace"))
            if match:
                start_byte = node.start_byte + match.start()
                end_byte = node.start_byte + match.end()
                lines_before = source[:start_byte].count(b"\n")
                lines_in_match = source[start_byte:end_byte].count(b"\n")
                return CodeChunk(
                    language=self._get_language_from_path(file_path),
                    file_path=file_path,
                    node_type=f"regex_match_{self._name}",
                    start_line=lines_before + 1,
                    end_line=lines_before + lines_in_match + 1,
                    byte_start=start_byte,
                    byte_end=end_byte,
                    parent_context=node.type,
                    content=source[start_byte:end_byte].decode(
                        "utf-8",
                        errors="replace",
                    ),
                )
        return None

    def find_all_matches(self, source: bytes, _file_path: str) -> list[RuleMatch]:
        """Find all matches in source text (for cross-boundary matching)."""
        matches = []
        text = source.decode("utf-8", errors="replace")
        for match in self._pattern.finditer(text):
            start_byte = len(text[: match.start()].encode("utf-8"))
            end_byte = len(text[: match.end()].encode("utf-8"))
            lines_before = text[: match.start()].count("\n")
            start_col = match.start() - text.rfind("\n", 0, match.start()) - 1
            lines_in_match = text[match.start() : match.end()].count("\n")
            end_col = match.end() - text.rfind("\n", 0, match.end()) - 1
            matches.append(
                RuleMatch(
                    rule_name=self._name,
                    start_byte=start_byte,
                    end_byte=end_byte,
                    start_point=(lines_before, start_col),
                    end_point=(lines_before + lines_in_match, end_col),
                    metadata={"matched_text": match.group(0)},
                ),
            )
        return matches

    @staticmethod
    def _get_language_from_path(file_path: str) -> str:
        """Infer language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return "unknown"


class BaseCommentBlockRule(CommentBlockRule):
    """Base implementation for comment block extraction."""

    def __init__(
        self,
        name: str,
        description: str,
        priority: int = 0,
        merge_adjacent: bool = True,
    ):
        self._name = name
        self._description = description
        self._priority = priority
        self._merge_adjacent = merge_adjacent

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description

    def get_priority(self) -> int:
        return self._priority

    def should_merge_adjacent_comments(self) -> bool:
        return self._merge_adjacent

    @staticmethod
    def matches(node: Node, _source: bytes) -> bool:
        """Check if node is a comment node."""
        comment_types = [
            "comment",
            "line_comment",
            "block_comment",
            "documentation_comment",
            "doc_comment",
        ]
        return node.type in comment_types

    def extract_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
    ) -> CodeChunk | None:
        """Extract comment block as chunk."""
        if self.matches(node, source):
            content = source[node.start_byte : node.end_byte].decode(
                "utf-8",
                errors="replace",
            )
            lines_before = source[: node.start_byte].count(b"\n")
            lines_in_node = source[node.start_byte : node.end_byte].count(b"\n")
            return CodeChunk(
                language=self._get_language_from_path(file_path),
                file_path=file_path,
                node_type=f"comment_block_{node.type}",
                start_line=lines_before + 1,
                end_line=lines_before + lines_in_node + 1,
                byte_start=node.start_byte,
                byte_end=node.end_byte,
                parent_context="file",
                content=content,
            )
        return None

    @staticmethod
    def _get_language_from_path(file_path: str) -> str:
        """Infer language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return "unknown"


class MetadataRule(BaseCustomRule):
    """Extract file-level metadata chunks."""

    def __init__(self, priority: int = 100):
        super().__init__(
            name="file_metadata",
            description="Extract file metadata as a chunk",
            priority=priority,
        )

    @staticmethod
    def matches(node: Node, _source: bytes) -> bool:
        """Match root node for file metadata."""
        return node.parent is None

    def extract_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
    ) -> CodeChunk | None:
        """Extract file metadata."""
        if self.matches(node, source):
            total_lines = source.count(b"\n") + 1
            metadata_content = f"""File: {file_path}
Language: {self._get_language_from_path(file_path)}
Total Lines: {total_lines}
Total Bytes: {len(source)}
"""
            return CodeChunk(
                language=self._get_language_from_path(file_path),
                file_path=file_path,
                node_type="file_metadata",
                start_line=1,
                end_line=1,
                byte_start=0,
                byte_end=0,
                parent_context="root",
                content=metadata_content,
            )
        return None

    @staticmethod
    def _get_language_from_path(file_path: str) -> str:
        """Infer language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return "unknown"

"""Comment-based chunking rules for extracting structured comments."""

import re

from tree_sitter import Node

from chunker.types import CodeChunk

from .custom import BaseCommentBlockRule


class TodoBlockRule(BaseCommentBlockRule):
    """Extract TODO/FIXME blocks with context."""

    def __init__(
        self,
        keywords: list[str] | None = None,
        include_context_lines: int = 2,
        priority: int = 55,
    ):
        """
        Initialize TODO block rule.

        Args:
            keywords: Keywords to look for (default: TODO, FIXME, HACK, etc.)
            include_context_lines: Number of context lines to include
            priority: Rule priority
        """
        super().__init__(
            name="todo_blocks",
            description="Extract TODO/FIXME comment blocks with context",
            priority=priority,
            merge_adjacent=True,
        )
        self.keywords = keywords or [
            "TODO",
            "FIXME",
            "HACK",
            "NOTE",
            "XXX",
            "BUG",
            "OPTIMIZE",
            "REFACTOR",
        ]
        self.include_context_lines = include_context_lines
        self._keyword_pattern = re.compile(
            f"\\b({'|'.join(self.keywords)})\\b\\s*:?\\s*(.+)",
            re.IGNORECASE,
        )

    @staticmethod
    def get_comment_markers() -> dict[str, list[str]]:
        """Get comment markers for different styles."""
        return {
            "single_line": ["#", "//", "--"],
            "block_start": ["/*", "/**", "<!--"],
            "block_end": ["*/", "-->", "*/"],
        }

    def matches(self, node: Node, source: bytes) -> bool:
        """Check if node contains TODO-like keywords."""
        if not super().matches(node, source):
            return False
        content = source[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        return bool(self._keyword_pattern.search(content))

    def extract_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
    ) -> CodeChunk | None:
        """Extract TODO block with context."""
        if not self.matches(node, source):
            return None
        chunk = super().extract_chunk(node, source, file_path)
        if not chunk:
            return None
        content = source[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        match = self._keyword_pattern.search(content)
        if match:
            keyword = match.group(1).upper()
            match.group(2).strip()
            chunk.node_type = f"todo_block_{keyword.lower()}"
            if self.include_context_lines > 0:
                chunk = self._add_context_lines(chunk, source)
        return chunk

    def _add_context_lines(self, chunk: CodeChunk, source: bytes) -> CodeChunk:
        """Add context lines around the chunk."""
        lines = source.decode("utf-8", errors="replace").split("\n")
        start_line = max(0, chunk.start_line - 1 - self.include_context_lines)
        end_line = min(len(lines), chunk.end_line + self.include_context_lines)
        new_start_byte = sum(len(line) + 1 for line in lines[:start_line])
        new_end_byte = sum(len(line) + 1 for line in lines[:end_line])
        chunk.start_line = start_line + 1
        chunk.end_line = end_line
        chunk.byte_start = new_start_byte
        chunk.byte_end = new_end_byte
        chunk.content = "\n".join(lines[start_line:end_line])
        return chunk


class DocumentationBlockRule(BaseCommentBlockRule):
    """Extract documentation comment blocks (docstrings, JSDoc, etc.)."""

    def __init__(self, priority: int = 65):
        """Initialize documentation block rule."""
        super().__init__(
            name="doc_blocks",
            description="Extract documentation comment blocks",
            priority=priority,
            merge_adjacent=False,
        )
        self._doc_patterns = {
            "python": re.compile(r"^\s*[\"'].*[\"']", re.DOTALL),
            "javascript": re.compile(r"^\s*/\*\*", re.MULTILINE),
            "java": re.compile(r"^\s*/\*\*", re.MULTILINE),
            "rust": re.compile(r"^\s*//[/!]", re.MULTILINE),
            "go": re.compile(r"^\s*//\s*\w+\s+\w+", re.MULTILINE),
        }

    @staticmethod
    def get_comment_markers() -> dict[str, list[str]]:
        """Get comment markers for different styles."""
        return {
            "single_line": ["#", "//", "--", "///", "//!"],
            "block_start": ["/*", "/**", '"""', "'''", "<!--"],
            "block_end": ["*/", '"""', "'''", "-->"],
        }

    def matches(self, node: Node, source: bytes) -> bool:
        """Check if node is a documentation comment."""
        if not super().matches(node, source):
            return False
        content = source[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        if node.type in {"string", "string_literal", "template_string"}:
            parent = node.parent
            if (
                parent
                and parent.type
                in {"function_definition", "class_definition", "method_definition"}
            ) and (parent.children and node in parent.children[:3]):
                return True
        lang = self._get_language_from_node(node)
        if lang in self._doc_patterns:
            return bool(self._doc_patterns[lang].match(content))
        return False

    @staticmethod
    def extract_chunk(node: Node, source: bytes, file_path: str) -> CodeChunk | None:
        """Extract documentation block with metadata."""
        chunk = super().extract_chunk(node, source, file_path)
        if not chunk:
            return None
        chunk.node_type = f"doc_block_{node.type}"
        parent = node.parent
        if parent and parent.type in {
            "function_definition",
            "class_definition",
            "method_definition",
        }:
            for child in parent.children:
                if child.type in {"identifier", "property_identifier"}:
                    entity_name = source[child.start_byte : child.end_byte].decode(
                        "utf-8",
                        errors="replace",
                    )
                    chunk.parent_context = f"{parent.type}:{entity_name}"
                    break
        return chunk

    @staticmethod
    def _get_language_from_node(node: Node) -> str:
        """Try to determine language from node context."""
        node_types_to_lang = {
            "python": ["def", "class", "import", "from"],
            "javascript": ["function", "const", "let", "var", "require"],
            "java": ["public", "private", "class", "interface"],
            "rust": ["fn", "impl", "struct", "enum"],
            "go": ["func", "type", "package"],
        }
        current = node
        for _ in range(5):
            if current.parent:
                current = current.parent
                for lang, keywords in node_types_to_lang.items():
                    if any(kw in current.type for kw in keywords):
                        return lang
        return "unknown"


class HeaderCommentRule(BaseCommentBlockRule):
    """Extract file header comments (copyright, license, etc.)."""

    def __init__(self, max_lines_from_start: int = 50, priority: int = 85):
        """
        Initialize header comment rule.

        Args:
            max_lines_from_start: Maximum lines from file start to consider
            priority: Rule priority
        """
        super().__init__(
            name="header_comments",
            description="Extract file header comments",
            priority=priority,
            merge_adjacent=True,
        )
        self.max_lines_from_start = max_lines_from_start
        self._header_patterns = [
            re.compile(
                r"\\b(?:copyright|©|\\(c\\)|license|author|created|modified)\\b",
                re.IGNORECASE,
            ),
            re.compile(r"^\\s*(?:@file|@module|@package|@brief)\\b", re.MULTILINE),
            re.compile(r"^\\s*(?:File|Module|Package|Description):\\s*", re.MULTILINE),
        ]

    @staticmethod
    def get_comment_markers() -> dict[str, list[str]]:
        """Get comment markers for different styles."""
        return {
            "single_line": ["#", "//", "--", ";"],
            "block_start": ["/*", "/**", "<!--", '"""', "'''"],
            "block_end": ["*/", "-->", '"""', "'''"],
        }

    def matches(self, node: Node, source: bytes) -> bool:
        """Check if node is a header comment."""
        if not super().matches(node, source):
            return False
        lines_before = source[: node.start_byte].count(b"\n")
        if lines_before > self.max_lines_from_start:
            return False
        content = source[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        return any(pattern.search(content) for pattern in self._header_patterns)

    def extract_chunk(self, node: Node, source: bytes, file_path: str) -> CodeChunk | None:
        """Extract header comment."""
        chunk = super().extract_chunk(node, source, file_path)
        if chunk:
            chunk.node_type = "header_comment"
            chunk.parent_context = "file_header"
        return chunk


class InlineCommentGroupRule(BaseCommentBlockRule):
    """Group related inline comments into chunks."""

    def __init__(
        self,
        max_gap_lines: int = 1,
        min_comments: int = 2,
        priority: int = 25,
    ):
        """
        Initialize inline comment group rule.

        Args:
            max_gap_lines: Maximum lines between comments to group
            min_comments: Minimum comments to form a group
            priority: Rule priority
        """
        super().__init__(
            name="inline_comment_groups",
            description="Group related inline comments",
            priority=priority,
            merge_adjacent=True,
        )
        self.max_gap_lines = max_gap_lines
        self.min_comments = min_comments
        self._processed_nodes = set()

    @staticmethod
    def get_comment_markers() -> dict[str, list[str]]:
        """Get comment markers for different styles."""
        return {
            "single_line": ["#", "//", "--", ";", "///", "//!"],
            "block_start": [],
            "block_end": [],
        }

    def matches(self, node: Node, source: bytes) -> bool:
        """Check if node is part of a comment group."""
        if not super().matches(node, source):
            return False
        if id(node) in self._processed_nodes:
            return False
        return self._find_comment_group(node, source) is not None

    def extract_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
    ) -> CodeChunk | None:
        """Extract grouped comments."""
        group_nodes = self._find_comment_group(node, source)
        if not group_nodes or len(group_nodes) < self.min_comments:
            return None
        for n in group_nodes:
            self._processed_nodes.add(id(n))
        start_byte = min(n.start_byte for n in group_nodes)
        end_byte = max(n.end_byte for n in group_nodes)
        lines = source.decode("utf-8", errors="replace").split("\n")
        start_line = source[:start_byte].count(b"\n")
        end_line = source[:end_byte].count(b"\n")
        content = "\n".join(lines[start_line : end_line + 1])
        return CodeChunk(
            language=self._get_language_from_path(file_path),
            file_path=file_path,
            node_type="inline_comment_group",
            start_line=start_line + 1,
            end_line=end_line + 1,
            byte_start=start_byte,
            byte_end=end_byte,
            parent_context="code_section",
            content=content,
        )

    def _find_comment_group(self, start_node: Node, source: bytes) -> list[Node] | None:
        """Find all comments that should be grouped together."""
        if not start_node.parent:
            return None
        parent = start_node.parent
        comment_nodes = [
            child
            for child in parent.children
            if child.type in {"comment", "line_comment"}
        ]
        if not comment_nodes:
            return None
        groups = []
        current_group = [comment_nodes[0]]
        for i in range(1, len(comment_nodes)):
            prev_node = comment_nodes[i - 1]
            curr_node = comment_nodes[i]
            prev_line = source[: prev_node.end_byte].count(b"\n")
            curr_line = source[: curr_node.start_byte].count(b"\n")
            if curr_line - prev_line <= self.max_gap_lines:
                current_group.append(curr_node)
            else:
                if len(current_group) >= self.min_comments:
                    groups.append(current_group)
                current_group = [curr_node]
        if len(current_group) >= self.min_comments:
            groups.append(current_group)
        for group in groups:
            if start_node in group:
                return group
        return None


class StructuredCommentRule(BaseCommentBlockRule):
    """Extract comments with structured content (tables, lists, etc.)."""

    def __init__(self, priority: int = 40):
        """Initialize structured comment rule."""
        super().__init__(
            name="structured_comments",
            description="Extract comments with structured content",
            priority=priority,
            merge_adjacent=True,
        )
        self._structure_patterns = [
            re.compile(r"^\\s*[-*+]\\s+", re.MULTILINE),
            re.compile(r"^\\s*\\d+\\.\\s+", re.MULTILINE),
            re.compile(r"^\\s*\\|.*\\|", re.MULTILINE),
            re.compile(r"^\\s*#+\\s+", re.MULTILINE),
            re.compile(r"^\\s*```", re.MULTILINE),
            re.compile(r"^\\s*@\\w+\\s*:", re.MULTILINE),
        ]

    @staticmethod
    def get_comment_markers() -> dict[str, list[str]]:
        """Get comment markers for different styles."""
        return {
            "single_line": ["#", "//", "--", ";"],
            "block_start": ["/*", "/**", "<!--", '"""', "'''"],
            "block_end": ["*/", "-->", '"""', "'''"],
        }

    def matches(self, node: Node, source: bytes) -> bool:
        """Check if comment contains structured content."""
        if not super().matches(node, source):
            return False
        content = source[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        cleaned = self._clean_comment_markers(content)
        return any(pattern.search(cleaned) for pattern in self._structure_patterns)

    def extract_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
    ) -> CodeChunk | None:
        """Extract structured comment."""
        chunk = super().extract_chunk(node, source, file_path)
        if chunk:
            chunk.node_type = "structured_comment"
            content = chunk.content
            cleaned = self._clean_comment_markers(content)
            if re.search(r"^\\s*\\|.*\\|", cleaned, re.MULTILINE):
                chunk.node_type = "structured_comment_table"
            elif re.search(r"^\\s*[-*+]\\s+", cleaned, re.MULTILINE):
                chunk.node_type = "structured_comment_list"
            elif re.search(r"^\\s*```", cleaned, re.MULTILINE):
                chunk.node_type = "structured_comment_code"
        return chunk

    @staticmethod
    def _clean_comment_markers(content: str) -> str:
        """Remove comment markers from content."""
        lines = content.split("\n")
        cleaned_lines = []
        for line in lines:
            cleaned = re.sub(r"^\\s*(?://|#|\\*|/\\*|\\*/)\\s*", "", line)
            cleaned_lines.append(cleaned)
        return "\n".join(cleaned_lines)


def create_comment_rule_chain(
    *rules: BaseCommentBlockRule,
) -> list[BaseCommentBlockRule]:
    """
    Create a chain of comment rules that work together.

    Args:
        *rules: Comment rules to chain

    Returns:
        List of chained rules
    """
    return sorted(rules, key=lambda r: r.get_priority(), reverse=True)

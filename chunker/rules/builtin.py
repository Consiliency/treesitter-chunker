"""Built-in custom chunking rules."""

from tree_sitter import Node

from chunker.types import CodeChunk

from .custom import BaseCommentBlockRule, BaseRegexRule, MetadataRule


class TodoCommentRule(BaseRegexRule):
    """Extract TODO/FIXME/HACK/NOTE comments."""

    def __init__(self, priority: int = 50):
        super().__init__(
            name="todo_comments",
            description="Extract TODO, FIXME, HACK, and NOTE comments",
            pattern="(?:#|//|/\\*|\\*)\\s*(TODO|FIXME|HACK|NOTE|XXX|BUG|OPTIMIZE|REFACTOR)\\s*:?\\s*(.+?)(?:\\*/|$)",
            priority=priority,
            cross_boundaries=True,
            multiline=True,
        )


class CopyrightHeaderRule(BaseRegexRule):
    """Extract copyright headers."""

    def __init__(self, priority: int = 90):
        super().__init__(
            name="copyright_header",
            description="Extract copyright and license headers",
            pattern="(?:#|//|/\\*)\\s*(?:Copyright|©|\\(c\\)|License).*?(?:\\*/|$)",
            priority=priority,
            cross_boundaries=True,
            multiline=True,
        )


class DocstringRule(BaseRegexRule):
    """Extract documentation strings/blocks."""

    def __init__(self, priority: int = 60):
        super().__init__(
            name="docstring",
            description="Extract documentation strings and blocks",
            pattern="(?:\"\"\"[\\s\\S]*?\"\"\"|\\'\\'\\'[\\s\\S]*?\\'\\'\\'|/\\*\\*[\\s\\S]*?\\*/)",
            priority=priority,
            cross_boundaries=False,
            multiline=True,
        )


class ImportBlockRule(BaseRegexRule):
    """Extract import statement blocks."""

    def __init__(self, priority: int = 70):
        super().__init__(
            name="import_block",
            description="Extract grouped import statements",
            pattern="(?:(?:^|\\n)\\s*(?:import|from|require|use|using|include)\\s+.+(?:\\n|$))+",
            priority=priority,
            cross_boundaries=True,
            multiline=True,
        )


class CustomMarkerRule(BaseRegexRule):
    """Extract custom marker regions."""

    def __init__(
        self,
        marker_start: str = "CHUNK_START",
        marker_end: str = "CHUNK_END",
        priority: int = 80,
    ):
        pattern = f"(?:#|//|/\\*)\\s*{marker_start}.*?\\n([\\s\\S]*?)(?:#|//|/\\*)\\s*{marker_end}"
        super().__init__(
            name="custom_markers",
            description=f"Extract regions between {marker_start} and {marker_end} markers",
            pattern=pattern,
            priority=priority,
            cross_boundaries=True,
            multiline=True,
        )
        self.marker_start = marker_start
        self.marker_end = marker_end


class SectionHeaderRule(BaseRegexRule):
    """Extract section headers (like markdown-style headers in comments)."""

    def __init__(self, priority: int = 40):
        super().__init__(
            name="section_headers",
            description="Extract section headers from comments",
            pattern="(?:^|\\n)\\s*(?:#|//)\\s*(?:={3,}|#{2,}|-{3,})\\s*(.+?)\\s*(?:={3,}|-{3,}|#{2,})?(?:\\n|$)",
            priority=priority,
            cross_boundaries=True,
            multiline=True,
        )


class ConfigurationBlockRule(BaseRegexRule):
    """Extract configuration blocks (JSON, YAML, etc. in comments)."""

    def __init__(self, priority: int = 30):
        super().__init__(
            name="config_blocks",
            description="Extract configuration blocks from comments",
            pattern="(?:/\\*|#|//)\\s*(?:config|configuration|settings|options)\\s*:\\s*[\\{\\[][\\s\\S]*?[\\}\\]][\\s\\S]*?(?:\\*/|\\n)",
            priority=priority,
            cross_boundaries=True,
            multiline=True,
        )


class LanguageSpecificCommentRule(BaseCommentBlockRule):
    """Language-aware comment block extraction."""

    def __init__(self, priority: int = 20):
        super().__init__(
            name="language_comments",
            description="Extract comment blocks with language-specific handling",
            priority=priority,
            merge_adjacent=True,
        )
        self._comment_markers = {
            "python": {
                "single_line": ["#"],
                "block_start": ['"""', "'''"],
                "block_end": ['"""', "'''"],
            },
            "javascript": {
                "single_line": ["//"],
                "block_start": ["/*"],
                "block_end": ["*/"],
            },
            "c": {"single_line": ["//"], "block_start": ["/*"], "block_end": ["*/"]},
            "cpp": {"single_line": ["//"], "block_start": ["/*"], "block_end": ["*/"]},
            "java": {
                "single_line": ["//"],
                "block_start": ["/*", "/**"],
                "block_end": ["*/"],
            },
            "rust": {
                "single_line": ["///", "//!", "//"],
                "block_start": ["/*", "/**", "/*!"],
                "block_end": ["*/"],
            },
            "go": {"single_line": ["//"], "block_start": ["/*"], "block_end": ["*/"]},
            "ruby": {
                "single_line": ["#"],
                "block_start": ["=begin"],
                "block_end": ["=end"],
            },
            "php": {
                "single_line": ["//", "#"],
                "block_start": ["/*", "/**"],
                "block_end": ["*/"],
            },
        }

    @staticmethod
    def get_comment_markers() -> dict[str, list[str]]:
        """Get default comment markers (overridden per language in extract)."""
        return {
            "single_line": ["#", "//"],
            "block_start": ["/*", "/**", '"""', "'''"],
            "block_end": ["*/", '"""', "'''"],
        }

    def extract_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
    ) -> CodeChunk | None:
        """Extract comment with language-specific handling."""
        chunk = super().extract_chunk(node, source, file_path)
        if chunk:
            lang = self._get_language_from_path(file_path)
            if lang in self._comment_markers:
                chunk.node_type = f"comment_{lang}_{node.type}"
        return chunk


class DebugStatementRule(BaseRegexRule):
    """Extract debug print/log statements."""

    def __init__(self, priority: int = 10):
        super().__init__(
            name="debug_statements",
            description="Extract debug print and log statements",
            pattern="(?:console\\.(?:log|debug|info|warn|error)|print(?:ln)?|debug|logger\\.(?:debug|info)|System\\.out\\.println?)\\s*\\([^;]+\\);?",
            priority=priority,
            cross_boundaries=False,
            multiline=False,
        )


class TestAnnotationRule(BaseRegexRule):
    """Extract test-related markers and annotations."""

    def __init__(self, priority: int = 35):
        super().__init__(
            name="test_markers",
            description="Extract test markers and annotations",
            pattern="(?:@(?:test|skip|ignore|disabled)|(?:it|test|describe)\\s*\\([\"\\'].*?[\"\\']\\s*,|TEST_CASE\\s*\\()",
            priority=priority,
            cross_boundaries=False,
            multiline=False,
        )


def get_builtin_rules() -> list[BaseRegexRule]:
    """Get all built-in rules with default priorities."""
    return [
        TodoCommentRule(),
        CopyrightHeaderRule(),
        DocstringRule(),
        ImportBlockRule(),
        CustomMarkerRule(),
        SectionHeaderRule(),
        ConfigurationBlockRule(),
        LanguageSpecificCommentRule(),
        DebugStatementRule(),
        TestAnnotationRule(),
        MetadataRule(),
    ]

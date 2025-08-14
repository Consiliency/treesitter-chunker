"""Relationship analyzer for semantic chunk analysis."""

import re
from collections import defaultdict

from chunker.interfaces.semantic import RelationshipAnalyzer
from chunker.types import CodeChunk


class TreeSitterRelationshipAnalyzer(RelationshipAnalyzer):
    """Analyze relationships between code chunks using Tree-sitter AST information."""

    @staticmethod
    def _safe_compile(pattern: str) -> re.Pattern | None:
        """Safely compile a regex pattern with error handling."""
        try:
            return re.compile(pattern)
        except re.error:
            return None

    @staticmethod
    def _safe_search(pattern: str, text: str) -> re.Match | None:
        """Safely search for a pattern in text with error handling."""
        if not text or not pattern:
            return None
        try:
            return re.search(pattern, text)
        except re.error:
            return None

    def __init__(self):
        """Initialize the analyzer with language-specific patterns."""
        self.getter_patterns = {
            "python": self._safe_compile(r"^(get_|get|is_|has_)(\w+)$"),
            "javascript": self._safe_compile(r"^(get|is|has)([A-Z]\w*)$"),
            "typescript": self._safe_compile(r"^(get|is|has)([A-Z]\w*)$"),
            "java": self._safe_compile(r"^(get|is|has)([A-Z]\w*)$"),
            "csharp": self._safe_compile(r"^(Get|Is|Has)([A-Z]\w*)$"),
            "cpp": self._safe_compile(r"^(get|is|has)_?(\w+)$"),
            "c": self._safe_compile(r"^(get|is|has)_(\w+)$"),
            "go": self._safe_compile(r"^(Get|Is|Has)([A-Z]\w*)$"),
        }
        self.setter_patterns = {
            "python": self._safe_compile(r"^set_(\w+)$"),
            "javascript": self._safe_compile(r"^set([A-Z]\w*)$"),
            "typescript": self._safe_compile(r"^set([A-Z]\w*)$"),
            "java": self._safe_compile(r"^set([A-Z]\w*)$"),
            "csharp": self._safe_compile(r"^Set([A-Z]\w*)$"),
            "cpp": self._safe_compile(r"^set_?(\w+)$"),
            "c": self._safe_compile(r"^set_(\w+)$"),
            "go": self._safe_compile(r"^Set([A-Z]\w*)$"),
        }
        self.interface_indicators = {
            "java": ["interface"],
            "csharp": ["interface"],
            "typescript": ["interface"],
            "cpp": ["class"],
            "python": ["ABC", "Protocol"],
        }
        self.implementation_indicators = {
            "java": ["implements"],
            "csharp": [":", "implements"],
            "typescript": ["implements"],
            "cpp": [":", "public", "private", "protected"],
            "python": ["class"],
        }

    def find_related_chunks(self, chunks: list[CodeChunk]) -> dict[str, list[str]]:
        """Find all types of relationships between chunks."""
        relationships = defaultdict(list)
        chunks_by_file = defaultdict(list)
        for chunk in chunks:
            chunks_by_file[chunk.file_path].append(chunk)
        for file_chunks in chunks_by_file.values():
            file_chunks.sort(key=lambda c: c.start_line)
            for i, chunk1 in enumerate(file_chunks):
                for chunk2 in file_chunks[i + 1 :]:
                    if self._are_in_same_class(chunk1, chunk2):
                        relationships[chunk1.chunk_id].append(chunk2.chunk_id)
                        relationships[chunk2.chunk_id].append(chunk1.chunk_id)
                    if self._is_getter_setter_pair(chunk1, chunk2):
                        relationships[chunk1.chunk_id].append(chunk2.chunk_id)
                        relationships[chunk2.chunk_id].append(chunk1.chunk_id)
                    if self._are_overloaded(chunk1, chunk2):
                        relationships[chunk1.chunk_id].append(chunk2.chunk_id)
                        relationships[chunk2.chunk_id].append(chunk1.chunk_id)
        for chunk_id in relationships:
            relationships[chunk_id] = list(set(relationships[chunk_id]))
        return dict(relationships)

    def find_overloaded_functions(
        self,
        chunks: list[CodeChunk],
    ) -> list[list[CodeChunk]]:
        """Find groups of overloaded functions."""
        function_groups = defaultdict(list)
        for chunk in chunks:
            if chunk.node_type in {
                "function_definition",
                "method_definition",
                "constructor",
            }:
                base_name = self._extract_function_base_name(chunk)
                if base_name:
                    key = chunk.file_path, chunk.parent_context, base_name
                    function_groups[key].append(chunk)
        overloaded_groups = []
        for group in function_groups.values():
            if len(group) > 1:
                group.sort(key=lambda c: c.start_line)
                overloaded_groups.append(group)
        return overloaded_groups

    def find_getter_setter_pairs(
        self,
        chunks: list[CodeChunk],
    ) -> list[tuple[CodeChunk, CodeChunk]]:
        """Find getter/setter method pairs."""
        pairs = []
        class_methods = defaultdict(list)
        for chunk in chunks:
            if chunk.node_type in {"function_definition", "method_definition"}:
                key = chunk.file_path, chunk.parent_context
                class_methods[key].append(chunk)
        for methods in class_methods.values():
            getters = {}
            setters = {}
            for method in methods:
                method_name = self._extract_method_name(method)
                if not method_name:
                    continue
                getter_match = self._match_getter_pattern(method_name, method.language)
                if getter_match:
                    property_name = getter_match.group(2).lower()
                    getters[property_name] = method
                setter_match = self._match_setter_pattern(method_name, method.language)
                if setter_match:
                    property_name = setter_match.group(1).lower()
                    setters[property_name] = method
            for prop_name, getter in getters.items():
                if prop_name in setters:
                    pairs.append((getter, setters[prop_name]))
        return pairs

    def find_interface_implementations(
        self,
        chunks: list[CodeChunk],
    ) -> dict[str, list[str]]:
        """Find interface/implementation relationships."""
        interfaces = {}
        implementations = defaultdict(list)
        for chunk in chunks:
            if chunk.node_type in {"class_definition", "interface_definition"}:
                if self._is_interface(chunk):
                    interface_name = self._extract_class_name(chunk)
                    if interface_name:
                        interfaces[interface_name] = chunk.chunk_id
                implemented_interfaces = self._extract_implemented_interfaces(chunk)
                for interface_name in implemented_interfaces:
                    implementations[interface_name].append(chunk.chunk_id)
        result = {}
        for interface_name, interface_chunk_id in interfaces.items():
            if interface_name in implementations:
                result[interface_chunk_id] = implementations[interface_name]
        return result

    def calculate_cohesion_score(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> float:
        """Calculate cohesion score between two chunks."""
        score = 0.0
        if chunk1.file_path == chunk2.file_path:
            score += 0.2
            line_distance = abs(chunk1.start_line - chunk2.start_line)
            if line_distance < 10:
                score += 0.2 * (1.0 - line_distance / 10.0)
            elif line_distance < 50:
                score += 0.1 * (1.0 - line_distance / 50.0)
        if chunk1.parent_context and chunk1.parent_context == chunk2.parent_context:
            score += 0.3
        if self._are_related_node_types(chunk1.node_type, chunk2.node_type):
            score += 0.1
        if self._is_getter_setter_pair(chunk1, chunk2):
            score += 0.4
        if self._are_overloaded(chunk1, chunk2):
            score += 0.3
        shared_refs = set(chunk1.references) & set(chunk2.references)
        if shared_refs:
            score += min(0.2, 0.05 * len(shared_refs))
        shared_deps = set(chunk1.dependencies) & set(chunk2.dependencies)
        if shared_deps:
            score += min(0.2, 0.05 * len(shared_deps))
        return min(1.0, score)

    @staticmethod
    def _extract_method_name(chunk: CodeChunk) -> str | None:
        """Extract method name from chunk content."""
        if not chunk.content or not chunk.content.strip():
            return None
        lines = chunk.content.strip().split("\n")
        if not lines:
            return None
        first_line = lines[0].strip()
        if not first_line:
            return None
        patterns = {
            "python": TreeSitterRelationshipAnalyzer._safe_compile(r"def\s+(\w+)\s*\("),
            "javascript": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:function\s+)?(\w+)\s*\(",
            ),
            "typescript": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:function\s+)?(\w+)\s*\(",
            ),
            "java": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(",
            ),
            "csharp": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(",
            ),
            "cpp": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:\w+\s+)?(\w+)\s*\(",
            ),
            "c": TreeSitterRelationshipAnalyzer._safe_compile(r"(?:\w+\s+)?(\w+)\s*\("),
            "go": TreeSitterRelationshipAnalyzer._safe_compile(
                r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(",
            ),
        }
        pattern = patterns.get(chunk.language)
        if pattern:
            match = pattern.search(first_line)
            if match:
                return match.group(1)
        return None

    def _extract_function_base_name(self, chunk: CodeChunk) -> str | None:
        """Extract base function name (without parameters) for overload detection."""
        method_name = self._extract_method_name(chunk)
        if not method_name:
            return None
        if chunk.node_type == "constructor":
            return self._extract_class_name_from_context(chunk)
        return method_name

    @staticmethod
    def _extract_class_name(chunk: CodeChunk) -> str | None:
        """Extract class/interface name from chunk content."""
        if not chunk.content or not chunk.content.strip():
            return None
        lines = chunk.content.strip().split("\n")
        if not lines:
            return None
        first_line = lines[0].strip()
        if not first_line:
            return None
        patterns = {
            "python": TreeSitterRelationshipAnalyzer._safe_compile(r"class\s+(\w+)"),
            "javascript": TreeSitterRelationshipAnalyzer._safe_compile(
                r"class\s+(\w+)",
            ),
            "typescript": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:class|interface)\s+(\w+)",
            ),
            "java": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:class|interface)\s+(\w+)",
            ),
            "csharp": TreeSitterRelationshipAnalyzer._safe_compile(
                r"(?:class|interface)\s+(\w+)",
            ),
            "cpp": TreeSitterRelationshipAnalyzer._safe_compile(r"class\s+(\w+)"),
            "c": TreeSitterRelationshipAnalyzer._safe_compile(r"struct\s+(\w+)"),
        }
        pattern = patterns.get(chunk.language)
        if pattern:
            match = pattern.search(first_line)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _extract_class_name_from_context(chunk: CodeChunk) -> str | None:
        """Extract class name from parent context."""
        if not chunk.parent_context:
            return None
        parts = chunk.parent_context.split(":")
        if len(parts) > 1:
            return parts[1]
        return None

    def _match_getter_pattern(self, method_name: str, language: str) -> re.Match | None:
        """Check if method name matches getter pattern."""
        if not method_name or not method_name.strip():
            return None
        pattern = self.getter_patterns.get(language)
        if pattern:
            return pattern.match(method_name)
        return None

    def _match_setter_pattern(self, method_name: str, language: str) -> re.Match | None:
        """Check if method name matches setter pattern."""
        if not method_name or not method_name.strip():
            return None
        pattern = self.setter_patterns.get(language)
        if pattern:
            return pattern.match(method_name)
        return None

    def _is_getter_setter_pair(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> bool:
        """Check if two chunks form a getter/setter pair."""
        if chunk1.language != chunk2.language:
            return False
        name1 = self._extract_method_name(chunk1)
        name2 = self._extract_method_name(chunk2)
        if not name1 or not name2:
            return False
        getter1 = self._match_getter_pattern(name1, chunk1.language)
        setter2 = self._match_setter_pattern(name2, chunk2.language)
        if getter1 and setter2:
            prop1 = getter1.group(2).lower()
            prop2 = setter2.group(1).lower()
            return prop1 == prop2
        getter2 = self._match_getter_pattern(name2, chunk2.language)
        setter1 = self._match_setter_pattern(name1, chunk1.language)
        if getter2 and setter1:
            prop2 = getter2.group(2).lower()
            prop1 = setter1.group(1).lower()
            return prop1 == prop2
        return False

    def _are_overloaded(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks are overloaded versions of the same function."""
        if chunk1.language != chunk2.language:
            return False
        if chunk1.file_path != chunk2.file_path:
            return False
        if chunk1.parent_context != chunk2.parent_context:
            return False
        if chunk1.node_type not in {
            "function_definition",
            "method_definition",
            "constructor",
        }:
            return False
        if chunk2.node_type not in {
            "function_definition",
            "method_definition",
            "constructor",
        }:
            return False
        name1 = self._extract_function_base_name(chunk1)
        name2 = self._extract_function_base_name(chunk2)
        return name1 and name2 and name1 == name2

    @staticmethod
    def _are_in_same_class(chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks are in the same class."""
        if not chunk1.parent_context or not chunk2.parent_context:
            return False
        return (
            chunk1.file_path == chunk2.file_path
            and chunk1.parent_context == chunk2.parent_context
            and "class" in chunk1.parent_context
        )

    @staticmethod
    def _are_related_node_types(type1: str, type2: str) -> bool:
        """Check if two node types are related."""
        related_groups = [
            {"function_definition", "method_definition", "constructor"},
            {"class_definition", "interface_definition"},
            {"import_statement", "import_from_statement"},
        ]
        return any(type1 in group and type2 in group for group in related_groups)

    def _is_interface(self, chunk: CodeChunk) -> bool:
        """Check if a chunk represents an interface."""
        if chunk.node_type == "interface_definition":
            return True
        if not chunk.content or not chunk.content.strip():
            return False
        indicators = self.interface_indicators.get(chunk.language, [])
        content_lower = chunk.content.lower()
        return any(indicator.lower() in content_lower for indicator in indicators)

    def _extract_implemented_interfaces(self, chunk: CodeChunk) -> list[str]:
        """Extract names of interfaces implemented by a class."""
        interfaces = []
        if not chunk.content or not chunk.content.strip():
            return interfaces
        if chunk.language == "java":
            match = self._safe_search(r"implements\s+([\w\s,]+)(?:\{|$)", chunk.content)
            if match:
                interface_list = match.group(1)
                interfaces = [i.strip() for i in interface_list.split(",")]
        elif chunk.language in {"csharp", "typescript"}:
            match = self._safe_search(
                r"(?::|implements)\s+([\w\s,]+)(?:\{|$)",
                chunk.content,
            )
            if match:
                interface_list = match.group(1)
                interfaces = [i.strip() for i in interface_list.split(",")]
        elif chunk.language == "python":
            match = self._safe_search(r"class\s+\w+\s*\(([\w\s,\.]+)\)", chunk.content)
            if match:
                parent_list = match.group(1)
                parents = [p.strip() for p in parent_list.split(",")]
                interfaces = [
                    p
                    for p in parents
                    if any(
                        ind in p for ind in self.interface_indicators.get("python", [])
                    )
                ]
        return interfaces

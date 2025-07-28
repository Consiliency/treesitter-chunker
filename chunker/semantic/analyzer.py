"""Relationship analyzer for semantic chunk analysis."""

import re
from collections import defaultdict

from chunker.interfaces.semantic import RelationshipAnalyzer
from chunker.types import CodeChunk


class TreeSitterRelationshipAnalyzer(RelationshipAnalyzer):
    """Analyze relationships between code chunks using Tree-sitter AST information."""

    def __init__(self):
        """Initialize the analyzer with language-specific patterns."""
        # Getter/setter patterns for various languages
        self.getter_patterns = {
            "python": re.compile(r"^(get_|get|is_|has_)(\w+)$"),
            "javascript": re.compile(r"^(get|is|has)([A-Z]\w*)$"),
            "typescript": re.compile(r"^(get|is|has)([A-Z]\w*)$"),
            "java": re.compile(r"^(get|is|has)([A-Z]\w*)$"),
            "csharp": re.compile(r"^(Get|Is|Has)([A-Z]\w*)$"),
            "cpp": re.compile(r"^(get|is|has)_?(\w+)$"),
            "c": re.compile(r"^(get|is|has)_(\w+)$"),
            "go": re.compile(r"^(Get|Is|Has)([A-Z]\w*)$"),  # Go uses CamelCase
        }

        self.setter_patterns = {
            "python": re.compile(r"^set_(\w+)$"),
            "javascript": re.compile(r"^set([A-Z]\w*)$"),
            "typescript": re.compile(r"^set([A-Z]\w*)$"),
            "java": re.compile(r"^set([A-Z]\w*)$"),
            "csharp": re.compile(r"^Set([A-Z]\w*)$"),
            "cpp": re.compile(r"^set_?(\w+)$"),
            "c": re.compile(r"^set_(\w+)$"),
            "go": re.compile(r"^Set([A-Z]\w*)$"),  # Go uses CamelCase
        }

        # Interface/implementation indicators
        self.interface_indicators = {
            "java": ["interface"],
            "csharp": ["interface"],
            "typescript": ["interface"],
            "cpp": ["class"],  # Abstract classes
            "python": ["ABC", "Protocol"],  # Abstract base classes
        }

        self.implementation_indicators = {
            "java": ["implements"],
            "csharp": [":", "implements"],
            "typescript": ["implements"],
            "cpp": [":", "public", "private", "protected"],  # Inheritance
            "python": ["class"],  # Classes that inherit from interfaces
        }

    def find_related_chunks(self, chunks: list[CodeChunk]) -> dict[str, list[str]]:
        """Find all types of relationships between chunks."""
        relationships = defaultdict(list)

        # Group chunks by file for better performance
        chunks_by_file = defaultdict(list)
        for chunk in chunks:
            chunks_by_file[chunk.file_path].append(chunk)

        # Find relationships within each file
        for file_chunks in chunks_by_file.values():
            # Sort by start line for sequential analysis
            file_chunks.sort(key=lambda c: c.start_line)

            for i, chunk1 in enumerate(file_chunks):
                for chunk2 in file_chunks[i + 1 :]:
                    # Check various relationship types
                    if self._are_in_same_class(chunk1, chunk2):
                        relationships[chunk1.chunk_id].append(chunk2.chunk_id)
                        relationships[chunk2.chunk_id].append(chunk1.chunk_id)

                    # Check for getter/setter relationship
                    if self._is_getter_setter_pair(chunk1, chunk2):
                        relationships[chunk1.chunk_id].append(chunk2.chunk_id)
                        relationships[chunk2.chunk_id].append(chunk1.chunk_id)

                    # Check for overloaded functions
                    if self._are_overloaded(chunk1, chunk2):
                        relationships[chunk1.chunk_id].append(chunk2.chunk_id)
                        relationships[chunk2.chunk_id].append(chunk1.chunk_id)

        # Remove duplicates
        for chunk_id in relationships:
            relationships[chunk_id] = list(set(relationships[chunk_id]))

        return dict(relationships)

    def find_overloaded_functions(
        self,
        chunks: list[CodeChunk],
    ) -> list[list[CodeChunk]]:
        """Find groups of overloaded functions."""
        # Group by file and function base name
        function_groups = defaultdict(list)

        for chunk in chunks:
            if chunk.node_type in [
                "function_definition",
                "method_definition",
                "constructor",
            ]:
                base_name = self._extract_function_base_name(chunk)
                if base_name:
                    key = (chunk.file_path, chunk.parent_context, base_name)
                    function_groups[key].append(chunk)

        # Filter groups with multiple functions (overloaded)
        overloaded_groups = []
        for group in function_groups.values():
            if len(group) > 1:
                # Sort by start line for consistent ordering
                group.sort(key=lambda c: c.start_line)
                overloaded_groups.append(group)

        return overloaded_groups

    def find_getter_setter_pairs(
        self,
        chunks: list[CodeChunk],
    ) -> list[tuple[CodeChunk, CodeChunk]]:
        """Find getter/setter method pairs."""
        pairs = []

        # Group chunks by file and class
        class_methods = defaultdict(list)
        for chunk in chunks:
            if chunk.node_type in ["function_definition", "method_definition"]:
                key = (chunk.file_path, chunk.parent_context)
                class_methods[key].append(chunk)

        # Find pairs within each class
        for methods in class_methods.values():
            getters = {}
            setters = {}

            for method in methods:
                method_name = self._extract_method_name(method)
                if not method_name:
                    continue

                # Check if it's a getter
                getter_match = self._match_getter_pattern(method_name, method.language)
                if getter_match:
                    property_name = getter_match.group(2).lower()
                    getters[property_name] = method

                # Check if it's a setter
                setter_match = self._match_setter_pattern(method_name, method.language)
                if setter_match:
                    property_name = setter_match.group(1).lower()
                    setters[property_name] = method

            # Match getters with setters
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
            if chunk.node_type in ["class_definition", "interface_definition"]:
                # Check if it's an interface
                if self._is_interface(chunk):
                    interface_name = self._extract_class_name(chunk)
                    if interface_name:
                        interfaces[interface_name] = chunk.chunk_id

                # Check if it implements interfaces
                implemented_interfaces = self._extract_implemented_interfaces(chunk)
                for interface_name in implemented_interfaces:
                    implementations[interface_name].append(chunk.chunk_id)

        # Build the result mapping interface chunks to implementation chunks
        result = {}
        for interface_name, interface_chunk_id in interfaces.items():
            if interface_name in implementations:
                result[interface_chunk_id] = implementations[interface_name]

        return result

    def calculate_cohesion_score(self, chunk1: CodeChunk, chunk2: CodeChunk) -> float:
        """Calculate cohesion score between two chunks."""
        score = 0.0

        # Same file bonus
        if chunk1.file_path == chunk2.file_path:
            score += 0.2

            # Proximity bonus (inverse of line distance)
            line_distance = abs(chunk1.start_line - chunk2.start_line)
            if line_distance < 10:
                score += 0.2 * (1.0 - line_distance / 10.0)
            elif line_distance < 50:
                score += 0.1 * (1.0 - line_distance / 50.0)

        # Same parent context (e.g., same class)
        if chunk1.parent_context and chunk1.parent_context == chunk2.parent_context:
            score += 0.3

        # Related node types
        if self._are_related_node_types(chunk1.node_type, chunk2.node_type):
            score += 0.1

        # Check for specific relationships
        if self._is_getter_setter_pair(chunk1, chunk2):
            score += 0.4

        if self._are_overloaded(chunk1, chunk2):
            score += 0.3

        # Check for shared references/dependencies
        shared_refs = set(chunk1.references) & set(chunk2.references)
        if shared_refs:
            score += min(0.2, 0.05 * len(shared_refs))

        shared_deps = set(chunk1.dependencies) & set(chunk2.dependencies)
        if shared_deps:
            score += min(0.2, 0.05 * len(shared_deps))

        # Cap the score at 1.0
        return min(1.0, score)

    # Helper methods

    def _extract_method_name(self, chunk: CodeChunk) -> str | None:
        """Extract method name from chunk content."""
        # Simple extraction - can be enhanced with proper parsing
        lines = chunk.content.strip().split("\n")
        if not lines:
            return None

        first_line = lines[0]

        # Language-specific patterns
        patterns = {
            "python": re.compile(r"def\s+(\w+)\s*\("),
            "javascript": re.compile(r"(?:function\s+)?(\w+)\s*\("),
            "typescript": re.compile(r"(?:function\s+)?(\w+)\s*\("),
            "java": re.compile(r"(?:public|private|protected)?\s*\w+\s+(\w+)\s*\("),
            "csharp": re.compile(r"(?:public|private|protected)?\s*\w+\s+(\w+)\s*\("),
            "cpp": re.compile(r"(?:\w+\s+)?(\w+)\s*\("),
            "c": re.compile(r"(?:\w+\s+)?(\w+)\s*\("),
            "go": re.compile(
                r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(",
            ),  # Handles receivers
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

        # For constructors, use the class name
        if chunk.node_type == "constructor":
            return self._extract_class_name_from_context(chunk)

        return method_name

    def _extract_class_name(self, chunk: CodeChunk) -> str | None:
        """Extract class/interface name from chunk content."""
        lines = chunk.content.strip().split("\n")
        if not lines:
            return None

        first_line = lines[0]

        # Language-specific patterns
        patterns = {
            "python": re.compile(r"class\s+(\w+)"),
            "javascript": re.compile(r"class\s+(\w+)"),
            "typescript": re.compile(r"(?:class|interface)\s+(\w+)"),
            "java": re.compile(r"(?:class|interface)\s+(\w+)"),
            "csharp": re.compile(r"(?:class|interface)\s+(\w+)"),
            "cpp": re.compile(r"class\s+(\w+)"),
            "c": re.compile(r"struct\s+(\w+)"),
        }

        pattern = patterns.get(chunk.language)
        if pattern:
            match = pattern.search(first_line)
            if match:
                return match.group(1)

        return None

    def _extract_class_name_from_context(self, chunk: CodeChunk) -> str | None:
        """Extract class name from parent context."""
        if not chunk.parent_context:
            return None

        # Try to extract from parent_context which might be "class_definition:ClassName"
        parts = chunk.parent_context.split(":")
        if len(parts) > 1:
            return parts[1]

        return None

    def _match_getter_pattern(self, method_name: str, language: str) -> re.Match | None:
        """Check if method name matches getter pattern."""
        pattern = self.getter_patterns.get(language)
        if pattern:
            return pattern.match(method_name)
        return None

    def _match_setter_pattern(self, method_name: str, language: str) -> re.Match | None:
        """Check if method name matches setter pattern."""
        pattern = self.setter_patterns.get(language)
        if pattern:
            return pattern.match(method_name)
        return None

    def _is_getter_setter_pair(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks form a getter/setter pair."""
        if chunk1.language != chunk2.language:
            return False

        name1 = self._extract_method_name(chunk1)
        name2 = self._extract_method_name(chunk2)

        if not name1 or not name2:
            return False

        # Check if one is getter and other is setter for same property
        getter1 = self._match_getter_pattern(name1, chunk1.language)
        setter2 = self._match_setter_pattern(name2, chunk2.language)

        if getter1 and setter2:
            prop1 = getter1.group(2).lower()
            prop2 = setter2.group(1).lower()
            return prop1 == prop2

        # Check the reverse
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

        # Must be function/method definitions
        if chunk1.node_type not in [
            "function_definition",
            "method_definition",
            "constructor",
        ]:
            return False

        if chunk2.node_type not in [
            "function_definition",
            "method_definition",
            "constructor",
        ]:
            return False

        # Check if they have the same base name
        name1 = self._extract_function_base_name(chunk1)
        name2 = self._extract_function_base_name(chunk2)

        return name1 and name2 and name1 == name2

    def _are_in_same_class(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks are in the same class."""
        if not chunk1.parent_context or not chunk2.parent_context:
            return False

        return (
            chunk1.file_path == chunk2.file_path
            and chunk1.parent_context == chunk2.parent_context
            and "class" in chunk1.parent_context
        )

    def _are_related_node_types(self, type1: str, type2: str) -> bool:
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

        # Check content for interface indicators
        indicators = self.interface_indicators.get(chunk.language, [])
        content_lower = chunk.content.lower()

        return any(indicator.lower() in content_lower for indicator in indicators)

    def _extract_implemented_interfaces(self, chunk: CodeChunk) -> list[str]:
        """Extract names of interfaces implemented by a class."""
        interfaces = []

        # Language-specific extraction
        if chunk.language == "java":
            # Look for "implements Interface1, Interface2"
            match = re.search(r"implements\s+([\w\s,]+)(?:\{|$)", chunk.content)
            if match:
                interface_list = match.group(1)
                interfaces = [i.strip() for i in interface_list.split(",")]

        elif chunk.language in ["csharp", "typescript"]:
            # Look for ": Interface1, Interface2" or "implements Interface1, Interface2"
            match = re.search(r"(?::|implements)\s+([\w\s,]+)(?:\{|$)", chunk.content)
            if match:
                interface_list = match.group(1)
                interfaces = [i.strip() for i in interface_list.split(",")]

        elif chunk.language == "python":
            # Look for inheritance in class definition
            match = re.search(r"class\s+\w+\s*\(([\w\s,\.]+)\)", chunk.content)
            if match:
                parent_list = match.group(1)
                # Filter for likely interfaces (ABC, Protocol, etc.)
                parents = [p.strip() for p in parent_list.split(",")]
                interfaces = [
                    p
                    for p in parents
                    if any(
                        ind in p for ind in self.interface_indicators.get("python", [])
                    )
                ]

        return interfaces

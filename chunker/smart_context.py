"""Smart context implementation for intelligent chunk context selection."""
import builtins
import re
import time
from collections import defaultdict
from functools import lru_cache
from typing import Any

from .interfaces.smart_context import (
    ContextCache,
    ContextMetadata,
    ContextStrategy,
    SmartContextProvider,
)
from .parser import get_parser
from .types import CodeChunk


class TreeSitterSmartContextProvider(SmartContextProvider):
    """
    Provides intelligent context for chunks using tree-sitter analysis.

    This implementation analyzes code structure, dependencies, and relationships
    to provide optimal context for LLM processing.
    """

    def __init__(self, cache: (ContextCache | None) = None):
        """
        Initialize the smart context provider.

        Args:
            cache: Optional cache for context computations
        """
        self.cache = cache or InMemoryContextCache()
        self._parsers = {}

    def get_semantic_context(self, chunk: CodeChunk, max_tokens: int = 2000,
        ) -> tuple[str, ContextMetadata]:
        """
        Get semantically relevant context for a chunk.

        This includes related functions, classes, or modules that are
        semantically connected to the chunk (similar functionality, same domain).

        Args:
            chunk: The chunk to get context for
            max_tokens: Maximum tokens for context

        Returns:
            Tuple of (context_string, metadata)
        """
        chunk_features = self._extract_semantic_features(chunk)
        file_chunks = self._get_file_chunks(chunk.file_path, chunk.language)
        similar_chunks = []
        for candidate in file_chunks:
            if candidate.chunk_id == chunk.chunk_id:
                continue
            candidate_features = self._extract_semantic_features(candidate)
            similarity_score = self._calculate_semantic_similarity(
                chunk_features, candidate_features)
            if similarity_score > 0.3:
                metadata = ContextMetadata(relevance_score=similarity_score,
                    relationship_type="semantic", distance=abs(candidate.
                    start_line - chunk.start_line), token_count=len(
                    candidate.content.split()))
                similar_chunks.append((candidate, metadata))
        similar_chunks.sort(key=lambda x: x[1].relevance_score, reverse=True)
        context_parts = []
        total_tokens = 0
        for candidate, metadata in similar_chunks:
            estimated_tokens = len(candidate.content.split())
            if total_tokens + estimated_tokens > max_tokens:
                break
            context_parts.append(
                f"""# Related {candidate.node_type} at line {candidate.start_line}:
{candidate.content}""",
                )
            total_tokens += estimated_tokens
        context_string = "\n\n".join(context_parts)
        overall_metadata = ContextMetadata(relevance_score=similar_chunks[0
            ][1].relevance_score if similar_chunks else 0.0,
            relationship_type="semantic", distance=0, token_count=total_tokens)
        return context_string, overall_metadata

    def get_dependency_context(self, chunk: CodeChunk, chunks: list[CodeChunk],
        ) -> list[tuple[CodeChunk, ContextMetadata]]:
        """
        Get chunks that this chunk depends on.

        This includes imports, function calls, class inheritance, etc.

        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search

        Returns:
            List of (chunk, metadata) tuples for dependencies
        """
        cached = self.cache.get(chunk.chunk_id, "dependency")
        if cached is not None:
            return cached
        dependencies = []
        imports = self._extract_imports(chunk)
        function_calls = self._extract_function_calls(chunk)
        class_references = self._extract_class_references(chunk)
        for candidate in chunks:
            relevance_score = 0.0
            if self._defines_import(candidate, imports):
                relevance_score += 0.8
            if self._defines_function(candidate, function_calls):
                relevance_score += 0.9
            if self._defines_class(candidate, class_references):
                relevance_score += 0.9
            if relevance_score > 0:
                metadata = ContextMetadata(relevance_score=relevance_score,
                    relationship_type="dependency", distance=self.
                    _calculate_file_distance(chunk, candidate), token_count=len(candidate.content.split()))
                dependencies.append((candidate, metadata))
        dependencies.sort(key=lambda x: x[1].relevance_score, reverse=True)
        self.cache.set(chunk.chunk_id, "dependency", dependencies)
        return dependencies

    def get_usage_context(self, chunk: CodeChunk, chunks: list[CodeChunk],
        ) -> list[tuple[CodeChunk, ContextMetadata]]:
        """
        Get chunks that use this chunk.

        This includes all places where this chunk is imported, called, or referenced.

        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search

        Returns:
            List of (chunk, metadata) tuples for usages
        """
        cached = self.cache.get(chunk.chunk_id, "usage")
        if cached is not None:
            return cached
        usages = []
        chunk_exports = self._extract_exports(chunk)
        for candidate in chunks:
            if candidate.chunk_id == chunk.chunk_id:
                continue
            relevance_score = 0.0
            if self._imports_from(candidate, chunk, chunk_exports):
                relevance_score += 0.8
            if self._calls_functions_from(candidate, chunk_exports):
                relevance_score += 0.7
            if self._uses_classes_from(candidate, chunk_exports):
                relevance_score += 0.7
            if relevance_score > 0:
                metadata = ContextMetadata(relevance_score=relevance_score,
                    relationship_type="usage", distance=self.
                    _calculate_file_distance(chunk, candidate), token_count=len(candidate.content.split()))
                usages.append((candidate, metadata))
        usages.sort(key=lambda x: x[1].relevance_score, reverse=True)
        self.cache.set(chunk.chunk_id, "usage", usages)
        return usages

    def get_structural_context(self, chunk: CodeChunk, chunks: list[CodeChunk],
        ) -> list[tuple[CodeChunk, ContextMetadata]]:
        """
        Get structurally related chunks.

        This includes parent classes, sibling methods, nested functions, etc.

        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search

        Returns:
            List of (chunk, metadata) tuples for structural relations
        """
        cached = self.cache.get(chunk.chunk_id, "structural")
        if cached is not None:
            return cached
        structural_relations = []
        file_chunks = [c for c in chunks if c.file_path == chunk.file_path]
        for candidate in file_chunks:
            if candidate.chunk_id == chunk.chunk_id:
                continue
            relevance_score = 0.0
            if self._is_parent_of(candidate, chunk):
                relevance_score = 1.0
            elif self._is_child_of(candidate, chunk):
                relevance_score = 0.9
            elif self._is_sibling_of(candidate, chunk):
                relevance_score = 0.8
            elif self._is_in_same_class(candidate, chunk):
                relevance_score = 0.7
            if relevance_score > 0:
                metadata = ContextMetadata(relevance_score=relevance_score,
                    relationship_type="structural", distance=abs(candidate.
                    start_line - chunk.start_line), token_count=len(
                    candidate.content.split()))
                structural_relations.append((candidate, metadata))
        structural_relations.sort(key=lambda x: (x[1].relevance_score, -x[1
            ].distance), reverse=True)
        self.cache.set(chunk.chunk_id, "structural", structural_relations)
        return structural_relations

    @staticmethod
    def _extract_semantic_features(chunk: CodeChunk) -> dict[str, Any]:
        """Extract semantic features from a chunk for similarity comparison."""
        features = {"identifiers": set(), "keywords": set(), "node_type":
            chunk.node_type, "parent_context": chunk.parent_context,
            "comments": []}
        identifier_pattern = "\\b[a-zA-Z_][a-zA-Z0-9_]*\\b"
        features["identifiers"] = set(re.findall(identifier_pattern, chunk.
            content))
        if chunk.language == "python":
            keywords = {"def", "class", "import", "from", "return", "if",
                "else", "for", "while", "try", "except"}
        elif chunk.language == "javascript":
            keywords = {"function", "class", "const", "let", "var",
                "import", "export", "return", "if", "else"}
        else:
            keywords = set()
        content_words = set(chunk.content.lower().split())
        features["keywords"] = keywords.intersection(content_words)
        comment_pattern = "#.*?$|//.*?$|/\\*.*?\\*/"
        features["comments"] = re.findall(comment_pattern, chunk.content,
            re.MULTILINE | re.DOTALL)
        return features

    @staticmethod
    def _calculate_semantic_similarity(features1: dict[str, Any], features2:
        dict[str, Any]) -> float:
        """Calculate semantic similarity between two feature sets."""
        score = 0.0
        if features1["node_type"] == features2["node_type"]:
            score += 0.3
        if features1["identifiers"] and features2["identifiers"]:
            overlap = len(features1["identifiers"].intersection(features2[
                "identifiers"]))
            total = len(features1["identifiers"].union(features2[
                "identifiers"]))
            if total > 0:
                score += 0.4 * (overlap / total)
        if features1["keywords"] and features2["keywords"]:
            overlap = len(features1["keywords"].intersection(features2[
                "keywords"]))
            total = len(features1["keywords"].union(features2["keywords"]))
            if total > 0:
                score += 0.2 * (overlap / total)
        if features1["parent_context"] == features2["parent_context"]:
            score += 0.1
        return min(score, 1.0)

    @staticmethod
    def _extract_imports(chunk: CodeChunk) -> set[str]:
        """Extract import statements from a chunk."""
        imports = set()
        if chunk.language == "python":
            import_pattern = "(?:from\\s+(\\S+)\\s+)?import\\s+([^;\\n]+)"
            matches = re.findall(import_pattern, chunk.content)
            for module, names in matches:
                if module:
                    imports.add(module)
                imports.update(name.strip() for name in names.split(","))
        elif chunk.language in {"javascript", "typescript"}:
            import_pattern = (
                'import\\s+(?:{[^}]+}|[^;]+)\\s+from\\s+[\\\'"]([^\\\'"]+)[\\\'"]'
                )
            imports.update(re.findall(import_pattern, chunk.content))
        return imports

    @staticmethod
    def _extract_function_calls(chunk: CodeChunk) -> set[str]:
        """Extract function call names from a chunk."""
        call_pattern = "(\\b[a-zA-Z_][a-zA-Z0-9_]*)\\s*\\("
        calls = set(re.findall(call_pattern, chunk.content))
        language_keywords = {"python": {"if", "elif", "while", "for",
            "except", "with", "def", "class"}, "javascript": {"if", "while",
            "for", "function", "catch", "switch"}}
        keywords = language_keywords.get(chunk.language, set())
        return calls - keywords

    @staticmethod
    def _extract_class_references(chunk: CodeChunk) -> set[str]:
        """Extract class references from a chunk."""
        references = set()
        if chunk.language == "python":
            class_pattern = "class\\s+\\w+\\s*\\(([^)]+)\\)"
            matches = re.findall(class_pattern, chunk.content)
            for match in matches:
                references.update(base.strip() for base in match.split(","))
        elif chunk.language in {"javascript", "typescript"}:
            extend_pattern = "class\\s+\\w+\\s+extends\\s+(\\w+)"
            references.update(re.findall(extend_pattern, chunk.content))
        return references

    def _defines_import(self, chunk: CodeChunk, imports: set[str]) -> bool:
        """Check if a chunk defines any of the imported items."""
        defined = self._extract_exports(chunk)
        return bool(imports.intersection(defined["functions"] | defined[
            "classes"] | defined["variables"]))

    def _defines_function(self, chunk: CodeChunk, function_calls: set[str],
        ) -> bool:
        """Check if a chunk defines any of the called functions."""
        defined = self._extract_exports(chunk)
        return bool(function_calls.intersection(defined["functions"]))

    def _defines_class(self, chunk: CodeChunk, class_references: set[str],
        ) -> bool:
        """Check if a chunk defines any of the referenced classes."""
        defined = self._extract_exports(chunk)
        return bool(class_references.intersection(defined["classes"]))

    @staticmethod
    def _extract_exports(chunk: CodeChunk) -> dict[str, set[str]]:
        """Extract what a chunk exports/defines."""
        exports = {"functions": set(), "classes": set(), "variables": set()}
        if chunk.language == "python":
            func_pattern = "def\\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            exports["functions"].update(re.findall(func_pattern, chunk.content),
                )
            class_pattern = "class\\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            exports["classes"].update(re.findall(class_pattern, chunk.content))
            var_pattern = "^([a-zA-Z_][a-zA-Z0-9_]*)\\s*="
            exports["variables"].update(re.findall(var_pattern, chunk.
                content, re.MULTILINE))
        elif chunk.language in {"javascript", "typescript"}:
            func_pattern = "function\\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            exports["functions"].update(re.findall(func_pattern, chunk.content),
                )
            arrow_pattern = (
                "(?:const|let|var)\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*=\\s*(?:\\([^)]*\\)|[^=])\\s*=>"
                )
            exports["functions"].update(re.findall(arrow_pattern, chunk.
                content))
            class_pattern = "class\\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            exports["classes"].update(re.findall(class_pattern, chunk.content))
        return exports

    def _imports_from(self, candidate: CodeChunk, source_chunk: CodeChunk,
        exports: dict[str, set[str]]) -> bool:
        """Check if candidate imports from source chunk."""
        imports = self._extract_imports(candidate)
        source_file_name = source_chunk.file_path.split("/")[-1].replace(".py",
            "").replace(".js", "")
        if source_file_name in imports:
            return True
        all_exports = exports["functions"] | exports["classes"] | exports[
            "variables"]
        return bool(imports.intersection(all_exports))

    def _calls_functions_from(self, candidate: CodeChunk, exports: dict[str,
        set[str]]) -> bool:
        """Check if candidate calls functions from exports."""
        calls = self._extract_function_calls(candidate)
        return bool(calls.intersection(exports["functions"]))

    def _uses_classes_from(self, candidate: CodeChunk, exports: dict[str,
        set[str]]) -> bool:
        """Check if candidate uses classes from exports."""
        references = self._extract_class_references(candidate)
        return bool(references.intersection(exports["classes"]))

    @staticmethod
    def _is_parent_of(candidate: CodeChunk, chunk: CodeChunk) -> bool:
        """Check if candidate is a parent of chunk."""
        return (candidate.start_line <= chunk.start_line and candidate.
            end_line >= chunk.end_line and candidate.chunk_id != chunk.chunk_id
            )

    @staticmethod
    def _is_child_of(candidate: CodeChunk, chunk: CodeChunk) -> bool:
        """Check if candidate is a child of chunk."""
        return (chunk.start_line <= candidate.start_line and chunk.end_line >=
            candidate.end_line and candidate.chunk_id != chunk.chunk_id)

    def _is_sibling_of(self, candidate: CodeChunk, chunk: CodeChunk) -> bool:
        """Check if candidate is a sibling of chunk."""
        return (candidate.parent_context == chunk.parent_context and
            candidate.chunk_id != chunk.chunk_id and not self._is_parent_of
            (candidate, chunk) and not self._is_child_of(candidate, chunk))

    @staticmethod
    def _is_in_same_class(candidate: CodeChunk, chunk: CodeChunk) -> bool:
        """Check if candidate is in the same class as chunk."""
        if not chunk.parent_context or not candidate.parent_context:
            return False
        class_pattern = "class\\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        chunk_classes = set(re.findall(class_pattern, chunk.parent_context))
        candidate_classes = set(re.findall(class_pattern, candidate.
            parent_context))
        return bool(chunk_classes.intersection(candidate_classes))

    @staticmethod
    def _calculate_file_distance(chunk1: CodeChunk, chunk2: CodeChunk) -> int:
        """Calculate distance between chunks across files."""
        if chunk1.file_path == chunk2.file_path:
            return abs(chunk1.start_line - chunk2.start_line)
        return 10000

    @staticmethod
    def _get_file_chunks(_file_path: str, _language: str) -> list[CodeChunk]:
        """Get all chunks from a file."""
        return []

    @lru_cache(maxsize=128)
    def _get_parser(self, language: str):
        """Get a cached parser for the language."""
        if language not in self._parsers:
            self._parsers[language] = get_parser(language)
        return self._parsers[language]


class RelevanceContextStrategy(ContextStrategy):
    """
    Strategy for selecting context based on relevance scores.

    This strategy prioritizes chunks with the highest relevance scores
    while respecting token limits.
    """

    @staticmethod
    def select_context(_chunk: CodeChunk, candidates: list[tuple[CodeChunk,
        ContextMetadata]], max_tokens: int) -> list[CodeChunk]:
        """
        Select the most relevant context chunks.

        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples to select from
            max_tokens: Maximum tokens to include

        Returns:
            Selected chunks ordered by relevance
        """
        sorted_candidates = sorted(candidates, key=lambda x: x[1].
            relevance_score, reverse=True)
        selected = []
        total_tokens = 0
        for candidate_chunk, metadata in sorted_candidates:
            if total_tokens + metadata.token_count <= max_tokens:
                selected.append(candidate_chunk)
                total_tokens += metadata.token_count
            elif total_tokens < max_tokens:
                remaining_tokens = max_tokens - total_tokens
                if remaining_tokens > 100:
                    selected.append(candidate_chunk)
                break
        return selected

    @staticmethod
    def rank_candidates(_chunk: CodeChunk, candidates: list[tuple[CodeChunk,
        ContextMetadata]]) -> list[tuple[CodeChunk, float]]:
        """
        Rank candidate chunks by relevance.

        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples

        Returns:
            List of (chunk, score) tuples sorted by score descending
        """
        ranked = []
        for candidate_chunk, metadata in candidates:
            score = metadata.relevance_score
            if metadata.relationship_type == "dependency":
                score *= 1.2
            elif metadata.relationship_type == "structural":
                score *= 1.1
            if metadata.distance > 0:
                distance_penalty = 1.0 / (1.0 + metadata.distance / 100.0)
                score *= distance_penalty
            ranked.append((candidate_chunk, score))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked


class HybridContextStrategy(ContextStrategy):
    """
    Hybrid strategy that balances different types of context.

    This strategy ensures a mix of dependency, usage, semantic, and structural
    context for comprehensive understanding.
    """

    def __init__(self, weights: (dict[str, float] | None) = None):
        """
        Initialize the hybrid strategy.

        Args:
            weights: Optional weights for different relationship types
        """
        self.weights = weights or {"dependency": 0.35, "usage": 0.25,
            "semantic": 0.25, "structural": 0.15}

    def select_context(self, _chunk: CodeChunk, candidates: list[tuple[
        CodeChunk, ContextMetadata]], max_tokens: int) -> list[CodeChunk]:
        """
        Select a balanced mix of context chunks.

        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples to select from
            max_tokens: Maximum tokens to include

        Returns:
            Selected chunks ordered by relevance
        """
        grouped = defaultdict(list)
        for candidate_chunk, metadata in candidates:
            grouped[metadata.relationship_type].append((candidate_chunk,
                metadata))
        type_budgets = {}
        for rel_type, weight in self.weights.items():
            type_budgets[rel_type] = int(max_tokens * weight)
        selected = []
        for rel_type, budget in type_budgets.items():
            if rel_type not in grouped:
                continue
            group_sorted = sorted(grouped[rel_type], key=lambda x: x[1].
                relevance_score, reverse=True)
            group_tokens = 0
            for candidate_chunk, metadata in group_sorted:
                if group_tokens + metadata.token_count <= budget:
                    selected.append(candidate_chunk)
                    group_tokens += metadata.token_count
        return selected

    def rank_candidates(self, _chunk: CodeChunk, candidates: list[tuple[
        CodeChunk, ContextMetadata]]) -> list[tuple[CodeChunk, float]]:
        """
        Rank candidate chunks by weighted relevance.

        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples

        Returns:
            List of (chunk, score) tuples sorted by score descending
        """
        ranked = []
        for candidate_chunk, metadata in candidates:
            weight = self.weights.get(metadata.relationship_type, 0.1)
            score = metadata.relevance_score * weight
            if metadata.distance < 50:
                score *= 1.1
            ranked.append((candidate_chunk, score))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked


class InMemoryContextCache(ContextCache):
    """In-memory cache implementation for context computations."""

    def __init__(self, ttl: int = 3600):
        """
        Initialize the cache.

        Args:
            ttl: Time-to-live in seconds for cache entries
        """
        self.cache: dict[str, dict[str, tuple[list[tuple[CodeChunk,
            ContextMetadata]], float]]] = {}
        self.ttl = ttl

    def get(self, chunk_id: str, context_type: str) -> (list[tuple[CodeChunk,
        ContextMetadata]] | None):
        """Get cached context if available and not expired."""
        cache_key = f"{chunk_id}_{context_type}"
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.ttl:
                return data
            del self.cache[cache_key]
        return None

    def set(self, chunk_id: str, context_type: str, context: list[tuple[
        CodeChunk, ContextMetadata]]) -> None:
        """Cache context for a chunk."""
        cache_key = f"{chunk_id}_{context_type}"
        self.cache[cache_key] = context, time.time()

    def invalidate(self, chunk_ids: (builtins.set[str] | None) = None) -> None:
        """Invalidate cache entries."""
        if chunk_ids is None:
            self.cache.clear()
        else:
            keys_to_remove = []
            for key in self.cache:
                chunk_id = key.split("_")[0]
                if chunk_id in chunk_ids:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.cache[key]

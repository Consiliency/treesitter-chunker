"""Advanced query implementation for Phase 10 - searching and filtering chunks."""

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any

import numpy as np

from .interfaces.query_advanced import (
    ChunkQueryAdvanced,
    QueryIndexAdvanced,
    QueryOptimizer,
    QueryResult,
    QueryType,
)
from .types import CodeChunk


class NaturalLanguageQueryEngine(ChunkQueryAdvanced):
    """Query chunks using natural language or structured queries."""

    def __init__(self):
        """Initialize the query engine with language models and patterns."""
        self.query_patterns = self._initialize_query_patterns()
        self.code_patterns = self._initialize_code_patterns()
        self.embeddings_cache = {}

    def _initialize_query_patterns(self) -> dict[str, list[re.Pattern]]:
        """Initialize patterns for understanding natural language queries."""
        return {
            "error_handling": [
                re.compile(r"\b(error|exception|try|catch|handle|raise|throw)\b", re.I),
                re.compile(r"\b(error\s+handling|exception\s+handling)\b", re.I),
            ],
            "authentication": [
                re.compile(
                    r"\b(auth|authenticate|login|logout|session|token|credential)\b",
                    re.I,
                ),
                re.compile(r"\b(authentication|authorization|oauth|jwt)\b", re.I),
            ],
            "database": [
                re.compile(r"\b(database|db|sql|query|table|column|index)\b", re.I),
                re.compile(r"\b(select|insert|update|delete|join)\b", re.I),
            ],
            "api": [
                re.compile(
                    r"\b(api|endpoint|route|rest|graphql|request|response)\b",
                    re.I,
                ),
                re.compile(r"\b(get|post|put|delete|patch)\b", re.I),
            ],
            "testing": [
                re.compile(
                    r"\b(test|testing|unit|integration|mock|assert|expect)\b",
                    re.I,
                ),
                re.compile(r"\b(describe|it|should|before|after)\b", re.I),
            ],
            "configuration": [
                re.compile(
                    r"\b(config|configuration|settings|env|environment|option)\b",
                    re.I,
                ),
                re.compile(r"\b(setup|initialize|configure)\b", re.I),
            ],
            "logging": [
                re.compile(
                    r"\b(log|logging|logger|debug|info|warn|error|trace)\b",
                    re.I,
                ),
                re.compile(r"\b(console|file|stream)\b", re.I),
            ],
            "security": [
                re.compile(
                    r"\b(security|secure|encrypt|decrypt|hash|salt|vulnerability)\b",
                    re.I,
                ),
                re.compile(r"\b(password|key|certificate|ssl|tls)\b", re.I),
            ],
            "validation": [
                re.compile(
                    r"\b(validate|validation|verify|check|ensure|assert)\b",
                    re.I,
                ),
                re.compile(r"\b(valid|invalid|format|pattern|constraint)\b", re.I),
            ],
            "caching": [
                re.compile(
                    r"\b(cache|caching|cached|redis|memcache|store|retrieve)\b",
                    re.I,
                ),
                re.compile(r"\b(ttl|expire|invalidate|refresh)\b", re.I),
            ],
        }

    def _initialize_code_patterns(self) -> dict[str, list[re.Pattern]]:
        """Initialize patterns for matching code constructs."""
        return {
            "error_handling": [
                re.compile(r"\btry\s*[:{]"),
                re.compile(r"\bcatch\s*\("),
                re.compile(r"\bexcept\s*\w*\s*:"),
                re.compile(r"\braise\s+\w+"),
                re.compile(r"\bthrow\s+\w+"),
                re.compile(r"\b\.catch\s*\("),
                re.compile(r"\b\.then\s*\(.*\)\.catch\s*\("),
            ],
            "function_definition": [
                re.compile(r"\bdef\s+\w+\s*\("),  # Python
                re.compile(r"\bfunction\s+\w+\s*\("),  # JavaScript
                re.compile(
                    r"\b(public|private|protected)?\s*\w+\s+\w+\s*\(",
                ),  # Java/C#
                re.compile(r"\bfunc\s+\w+\s*\("),  # Go
            ],
            "class_definition": [
                re.compile(r"\bclass\s+\w+"),
                re.compile(r"\binterface\s+\w+"),
                re.compile(r"\bstruct\s+\w+"),
            ],
            "import_statement": [
                re.compile(r"\bimport\s+"),
                re.compile(r"\bfrom\s+\w+\s+import"),
                re.compile(r"\brequire\s*\("),
                re.compile(r"\busing\s+\w+"),
            ],
            "test_code": [
                re.compile(r"\b(test|spec)\s*\("),
                re.compile(r"\bdescribe\s*\("),
                re.compile(r"\bit\s*\("),
                re.compile(r"\b@Test\b"),
                re.compile(r"\bdef\s+test_\w+"),
                re.compile(r"\bassert\w*\s*\("),
                re.compile(r"\bexpect\s*\("),
            ],
        }

    def search(
        self,
        query: str,
        chunks: list[CodeChunk],
        query_type: QueryType = QueryType.NATURAL_LANGUAGE,
        limit: int | None = None,
    ) -> list[QueryResult]:
        """Search chunks using various query types."""
        if query_type == QueryType.NATURAL_LANGUAGE:
            results = self._natural_language_search(query, chunks)
        elif query_type == QueryType.STRUCTURED:
            results = self._structured_search(query, chunks)
        elif query_type == QueryType.REGEX:
            results = self._regex_search(query, chunks)
        elif query_type == QueryType.AST_PATTERN:
            results = self._ast_pattern_search(query, chunks)
        else:
            raise ValueError(f"Unsupported query type: {query_type}")

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)

        # Apply limit
        if limit:
            results = results[:limit]

        return results

    def _natural_language_search(
        self,
        query: str,
        chunks: list[CodeChunk],
    ) -> list[QueryResult]:
        """Search using natural language understanding."""
        query_lower = query.lower()
        results = []

        # Determine query intent
        intents = self._extract_query_intents(query_lower)

        # Special handling for "find X functions" pattern
        if "authentication" in query_lower and "function" in query_lower:
            if "authentication" not in intents:
                intents.append("authentication")

        for chunk in chunks:
            score = 0.0
            highlights = []
            metadata = {"matched_intents": []}

            # Check for intent matches
            for intent in intents:
                if self._chunk_matches_intent(chunk, intent):
                    score += 0.4  # Increased weight for intent match
                    metadata["matched_intents"].append(intent)

            # Text similarity
            text_score, text_highlights = self._calculate_text_similarity(
                query_lower,
                chunk.content.lower(),
            )
            score += text_score * 0.4
            highlights.extend(text_highlights)

            # Semantic relevance based on node type
            if self._is_semantically_relevant(query_lower, chunk):
                score += 0.3

            # Only include chunks with non-zero scores
            if score > 0:
                results.append(
                    QueryResult(
                        chunk=chunk,
                        score=min(1.0, score),
                        highlights=highlights,
                        metadata=metadata,
                    ),
                )

        return results

    def _structured_search(
        self,
        query: str,
        chunks: list[CodeChunk],
    ) -> list[QueryResult]:
        """Search using structured query syntax."""
        # Parse structured query (e.g., "type:function language:python error")
        criteria = self._parse_structured_query(query)
        results = []

        for chunk in chunks:
            if self._chunk_matches_criteria(chunk, criteria):
                # Calculate relevance score based on matches
                score = self._calculate_structured_score(chunk, criteria)
                highlights = self._find_keyword_highlights(
                    chunk.content,
                    criteria.get("keywords", []),
                )

                results.append(
                    QueryResult(
                        chunk=chunk,
                        score=score,
                        highlights=highlights,
                        metadata={"matched_criteria": criteria},
                    ),
                )

        return results

    def _regex_search(self, query: str, chunks: list[CodeChunk]) -> list[QueryResult]:
        """Search using regular expressions."""
        try:
            pattern = re.compile(query, re.MULTILINE | re.DOTALL)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e

        results = []

        for chunk in chunks:
            matches = list(pattern.finditer(chunk.content))
            if matches:
                # Calculate score based on match count and coverage
                score = min(1.0, len(matches) * 0.2)
                highlights = [(m.start(), m.end()) for m in matches]

                results.append(
                    QueryResult(
                        chunk=chunk,
                        score=score,
                        highlights=highlights,
                        metadata={"match_count": len(matches)},
                    ),
                )

        return results

    def _ast_pattern_search(
        self,
        query: str,
        chunks: list[CodeChunk],
    ) -> list[QueryResult]:
        """Search using AST pattern matching."""
        # Parse AST pattern query
        pattern_type, pattern_details = self._parse_ast_pattern(query)
        results = []

        for chunk in chunks:
            if self._chunk_matches_ast_pattern(chunk, pattern_type, pattern_details):
                score = 0.8  # High score for AST matches
                highlights = []  # AST patterns don't have text highlights

                results.append(
                    QueryResult(
                        chunk=chunk,
                        score=score,
                        highlights=highlights,
                        metadata={"ast_pattern": pattern_type},
                    ),
                )

        return results

    def filter(
        self,
        chunks: list[CodeChunk],
        node_types: list[str] | None = None,
        languages: list[str] | None = None,
        min_lines: int | None = None,
        max_lines: int | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
        """Filter chunks by structured criteria."""
        filtered = chunks

        # Filter by node types
        if node_types:
            filtered = [c for c in filtered if c.node_type in node_types]

        # Filter by languages
        if languages:
            filtered = [c for c in filtered if c.language in languages]

        # Filter by line count
        if min_lines is not None:
            filtered = [
                c for c in filtered if (c.end_line - c.start_line + 1) >= min_lines
            ]

        if max_lines is not None:
            filtered = [
                c for c in filtered if (c.end_line - c.start_line + 1) <= max_lines
            ]

        # Filter by metadata
        if metadata_filters:
            filtered = [
                c for c in filtered if self._matches_metadata(c, metadata_filters)
            ]

        return filtered

    def find_similar(
        self,
        chunk: CodeChunk,
        chunks: list[CodeChunk],
        threshold: float = 0.7,
        limit: int | None = None,
    ) -> list[QueryResult]:
        """Find chunks similar to a given chunk."""
        results = []

        for candidate in chunks:
            if candidate.chunk_id == chunk.chunk_id:
                continue  # Skip self

            # Calculate similarity score
            score = self._calculate_chunk_similarity(chunk, candidate)

            if score >= threshold:
                highlights = []  # No highlights for similarity search
                metadata = {
                    "similarity_factors": self._get_similarity_factors(
                        chunk,
                        candidate,
                    ),
                }

                results.append(
                    QueryResult(
                        chunk=candidate,
                        score=score,
                        highlights=highlights,
                        metadata=metadata,
                    ),
                )

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)

        # Apply limit
        if limit:
            results = results[:limit]

        return results

    # Helper methods

    def _extract_query_intents(self, query: str) -> list[str]:
        """Extract intents from natural language query."""
        intents = []

        for intent, patterns in self.query_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    intents.append(intent)
                    break

        return intents

    def _chunk_matches_intent(self, chunk: CodeChunk, intent: str) -> bool:
        """Check if chunk matches a specific intent."""
        if intent not in self.code_patterns:
            return False

        patterns = self.code_patterns[intent]
        content_lower = chunk.content.lower()

        for pattern in patterns:
            if pattern.search(chunk.content):
                return True

        # Also check metadata and node type
        if (
            intent == "error_handling"
            and chunk.node_type in ["try_statement", "catch_clause"]
        ) or (intent == "testing" and "test" in chunk.file_path.lower()):
            return True
        return bool(
            (intent == "configuration" and "config" in chunk.file_path.lower())
            or (
                intent == "authentication"
                and any(
                    auth_term in content_lower
                    for auth_term in [
                        "auth",
                        "login",
                        "logout",
                        "password",
                        "token",
                        "credential",
                    ]
                )
            ),
        )

    def _calculate_text_similarity(
        self,
        query: str,
        text: str,
    ) -> tuple[float, list[tuple[int, int]]]:
        """Calculate text similarity and find highlights."""
        words = query.split()
        score = 0.0
        highlights = []

        for word in words:
            if len(word) < 3:  # Skip short words
                continue

            # Find all occurrences
            start = 0
            while True:
                pos = text.find(word, start)
                if pos == -1:
                    break
                highlights.append((pos, pos + len(word)))
                score += 0.1
                start = pos + 1

        # Use sequence matching for longer queries
        if len(query) > 10:
            matcher = SequenceMatcher(None, query, text)
            ratio = matcher.ratio()
            score += ratio * 0.5

        return min(1.0, score), highlights

    def _is_semantically_relevant(self, query: str, chunk: CodeChunk) -> bool:
        """Check if chunk is semantically relevant to query."""
        # Check for common programming concepts
        relevance_map = {
            "function": ["function_definition", "method_definition"],
            "class": ["class_definition", "class_declaration"],
            "import": ["import_statement", "import_from_statement"],
            "variable": ["variable_declaration", "assignment"],
            "loop": ["for_statement", "while_statement", "do_statement"],
            "condition": ["if_statement", "conditional_expression"],
        }

        for concept, node_types in relevance_map.items():
            if concept in query and chunk.node_type in node_types:
                return True

        return False

    def _parse_structured_query(self, query: str) -> dict[str, Any]:
        """Parse structured query syntax."""
        criteria = {"keywords": []}

        # Parse key:value pairs
        pattern = re.compile(r"(\w+):(\S+)")
        matches = pattern.findall(query)

        for key, value in matches:
            if key == "type":
                criteria["node_type"] = value
            elif key == "language":
                criteria["language"] = value
            elif key == "file":
                criteria["file_pattern"] = value
            else:
                criteria[key] = value

        # Extract keywords (words not part of key:value pairs)
        remaining = pattern.sub("", query).strip()
        if remaining:
            criteria["keywords"] = remaining.split()

        return criteria

    def _chunk_matches_criteria(
        self,
        chunk: CodeChunk,
        criteria: dict[str, Any],
    ) -> bool:
        """Check if chunk matches structured criteria."""
        if "node_type" in criteria and chunk.node_type != criteria["node_type"]:
            return False

        if "language" in criteria and chunk.language != criteria["language"]:
            return False

        if "file_pattern" in criteria:
            pattern = re.compile(criteria["file_pattern"])
            if not pattern.search(chunk.file_path):
                return False

        # Check keywords
        keywords = criteria.get("keywords", [])
        if keywords:
            content_lower = chunk.content.lower()
            if not all(kw.lower() in content_lower for kw in keywords):
                return False

        return True

    def _calculate_structured_score(
        self,
        chunk: CodeChunk,
        criteria: dict[str, Any],
    ) -> float:
        """Calculate relevance score for structured search."""
        score = 0.5  # Base score for matching criteria

        # Boost for exact matches
        if "node_type" in criteria and chunk.node_type == criteria["node_type"]:
            score += 0.2

        # Boost for keyword density
        keywords = criteria.get("keywords", [])
        if keywords:
            content_lower = chunk.content.lower()
            keyword_count = sum(content_lower.count(kw.lower()) for kw in keywords)
            score += min(0.3, keyword_count * 0.05)

        return min(1.0, score)

    def _find_keyword_highlights(
        self,
        content: str,
        keywords: list[str],
    ) -> list[tuple[int, int]]:
        """Find positions of keywords in content."""
        highlights = []
        content_lower = content.lower()

        for keyword in keywords:
            keyword_lower = keyword.lower()
            start = 0
            while True:
                pos = content_lower.find(keyword_lower, start)
                if pos == -1:
                    break
                highlights.append((pos, pos + len(keyword)))
                start = pos + 1

        return highlights

    def _parse_ast_pattern(self, query: str) -> tuple[str, dict[str, Any]]:
        """Parse AST pattern query."""
        # Simple parsing - can be extended for more complex patterns
        parts = query.split()
        pattern_type = parts[0] if parts else ""
        pattern_details = {}

        # Parse additional constraints
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                pattern_details[key] = value

        return pattern_type, pattern_details

    def _chunk_matches_ast_pattern(
        self,
        chunk: CodeChunk,
        pattern_type: str,
        pattern_details: dict[str, Any],
    ) -> bool:
        """Check if chunk matches AST pattern."""
        # Match node type
        if pattern_type and chunk.node_type != pattern_type:
            return False

        # Check additional constraints
        for key, value in pattern_details.items():
            if key == "parent" and chunk.parent_context != value:
                return False
            if key == "has_child":
                # Would need AST traversal to check children
                pass

        return True

    def _matches_metadata(self, chunk: CodeChunk, filters: dict[str, Any]) -> bool:
        """Check if chunk metadata matches filters."""
        for key, value in filters.items():
            chunk_value = chunk.metadata.get(key)

            if isinstance(value, dict) and "min" in value:
                if chunk_value is None or chunk_value < value["min"]:
                    return False
            elif isinstance(value, dict) and "max" in value:
                if chunk_value is None or chunk_value > value["max"]:
                    return False
            elif chunk_value != value:
                return False

        return True

    def _calculate_chunk_similarity(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> float:
        """Calculate similarity between two chunks."""
        score = 0.0

        # Language similarity
        if chunk1.language == chunk2.language:
            score += 0.1

        # Node type similarity
        if chunk1.node_type == chunk2.node_type:
            score += 0.2

        # File proximity
        if chunk1.file_path == chunk2.file_path:
            score += 0.1

        # Parent context similarity
        if chunk1.parent_context and chunk1.parent_context == chunk2.parent_context:
            score += 0.1

        # Content similarity
        content_sim = SequenceMatcher(None, chunk1.content, chunk2.content).ratio()
        score += content_sim * 0.4

        # Size similarity
        size1 = chunk1.end_line - chunk1.start_line
        size2 = chunk2.end_line - chunk2.start_line
        size_ratio = (
            min(size1, size2) / max(size1, size2) if max(size1, size2) > 0 else 0
        )
        score += size_ratio * 0.1

        return min(1.0, score)

    def _get_similarity_factors(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> dict[str, Any]:
        """Get factors contributing to similarity."""
        factors = {}

        if chunk1.language == chunk2.language:
            factors["same_language"] = True

        if chunk1.node_type == chunk2.node_type:
            factors["same_node_type"] = True

        if chunk1.file_path == chunk2.file_path:
            factors["same_file"] = True

        content_sim = SequenceMatcher(None, chunk1.content, chunk2.content).ratio()
        factors["content_similarity"] = round(content_sim, 3)

        return factors


class AdvancedQueryIndex(QueryIndexAdvanced):
    """Advanced index for fast chunk queries with multiple index types."""

    def __init__(self):
        """Initialize the multi-index system."""
        self.chunks: dict[str, CodeChunk] = {}
        self.text_index: dict[str, set[str]] = defaultdict(set)  # term -> chunk_ids
        self.type_index: dict[str, set[str]] = defaultdict(
            set,
        )  # node_type -> chunk_ids
        self.file_index: dict[str, set[str]] = defaultdict(
            set,
        )  # file_path -> chunk_ids
        self.language_index: dict[str, set[str]] = defaultdict(
            set,
        )  # language -> chunk_ids
        self.embeddings: dict[str, np.ndarray] = {}  # chunk_id -> embedding vector
        self.query_engine = NaturalLanguageQueryEngine()

    def build_index(self, chunks: list[CodeChunk]) -> None:
        """Build search index from chunks."""
        # Clear existing indices
        self.chunks.clear()
        self.text_index.clear()
        self.type_index.clear()
        self.file_index.clear()
        self.language_index.clear()
        self.embeddings.clear()

        # Build indices
        for chunk in chunks:
            self.add_chunk(chunk)

    def add_chunk(self, chunk: CodeChunk) -> None:
        """Add a single chunk to the index."""
        chunk_id = chunk.chunk_id
        self.chunks[chunk_id] = chunk

        # Text index - tokenize and index content
        tokens = self._tokenize(chunk.content)
        for token in tokens:
            self.text_index[token].add(chunk_id)

        # Type index
        self.type_index[chunk.node_type].add(chunk_id)

        # File index
        self.file_index[chunk.file_path].add(chunk_id)

        # Language index
        self.language_index[chunk.language].add(chunk_id)

        # Generate and store embedding (simplified - would use real embeddings in production)
        self.embeddings[chunk_id] = self._generate_embedding(chunk)

    def remove_chunk(self, chunk_id: str) -> None:
        """Remove a chunk from the index."""
        if chunk_id not in self.chunks:
            return

        chunk = self.chunks[chunk_id]

        # Remove from text index
        tokens = self._tokenize(chunk.content)
        for token in tokens:
            self.text_index[token].discard(chunk_id)
            if not self.text_index[token]:
                del self.text_index[token]

        # Remove from other indices
        self.type_index[chunk.node_type].discard(chunk_id)
        if not self.type_index[chunk.node_type]:
            del self.type_index[chunk.node_type]

        self.file_index[chunk.file_path].discard(chunk_id)
        if not self.file_index[chunk.file_path]:
            del self.file_index[chunk.file_path]

        self.language_index[chunk.language].discard(chunk_id)
        if not self.language_index[chunk.language]:
            del self.language_index[chunk.language]

        # Remove embedding
        if chunk_id in self.embeddings:
            del self.embeddings[chunk_id]

        # Remove chunk
        del self.chunks[chunk_id]

    def update_chunk(self, chunk: CodeChunk) -> None:
        """Update an existing chunk in the index."""
        # Remove old version
        self.remove_chunk(chunk.chunk_id)
        # Add new version
        self.add_chunk(chunk)

    def query(
        self,
        query: str,
        query_type: QueryType = QueryType.NATURAL_LANGUAGE,
        limit: int = 10,
    ) -> list[QueryResult]:
        """Query the index."""
        # Get candidate chunks based on query tokens
        candidate_ids = self._get_candidate_chunks(query)

        # Convert to chunk list
        candidates = [self.chunks[cid] for cid in candidate_ids if cid in self.chunks]

        # Use query engine for ranking
        results = self.query_engine.search(query, candidates, query_type, limit)

        return results

    def get_statistics(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "total_chunks": len(self.chunks),
            "unique_terms": len(self.text_index),
            "unique_node_types": len(self.type_index),
            "unique_files": len(self.file_index),
            "unique_languages": len(self.language_index),
            "embeddings_count": len(self.embeddings),
            "avg_terms_per_chunk": self._calculate_avg_terms_per_chunk(),
            "index_memory_bytes": self._estimate_memory_usage(),
        }

    # Helper methods

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text for indexing."""
        # Simple tokenization - can be improved with proper NLP
        tokens = set()

        # Split on non-alphanumeric characters
        words = re.findall(r"\w+", text)

        for word in words:
            if len(word) >= 2:  # Skip single characters
                tokens.add(word.lower())

                # Add camelCase parts
                # Handle camelCase by finding transitions from lowercase to uppercase
                camel_parts = re.findall(
                    r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b|\d)|[0-9]+",
                    word,
                )
                for part in camel_parts:
                    if len(part) >= 2:
                        tokens.add(part.lower())

                # Handle snake_case parts
                if "_" in word:
                    snake_parts = word.split("_")
                    for part in snake_parts:
                        if len(part) >= 2:
                            tokens.add(part.lower())

        return tokens

    def _generate_embedding(self, chunk: CodeChunk) -> np.ndarray:
        """Generate embedding vector for chunk."""
        # Simplified embedding - in production would use proper sentence embeddings
        # Using TF-IDF-like approach with fixed vocabulary

        tokens = self._tokenize(chunk.content)

        # Create a simple hash-based embedding
        embedding = np.zeros(128)  # 128-dimensional embedding

        for token in tokens:
            # Hash token to get indices
            hash_val = hash(token)
            indices = [hash_val % 128, (hash_val // 128) % 128]

            for idx in indices:
                embedding[idx] += 1.0

        # Add features for node type and language
        type_hash = hash(chunk.node_type) % 64
        lang_hash = hash(chunk.language) % 64

        embedding[type_hash] += 2.0
        embedding[64 + lang_hash] += 2.0

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def _get_candidate_chunks(self, query: str) -> set[str]:
        """Get candidate chunk IDs based on query."""
        tokens = self._tokenize(query)

        if not tokens:
            # Return all chunks if no tokens
            return set(self.chunks.keys())

        # Get chunks containing any query token
        candidates = set()
        for token in tokens:
            if token in self.text_index:
                candidates.update(self.text_index[token])

        # If too few candidates, expand search
        if len(candidates) < 10:
            # Add chunks with similar tokens
            for token in tokens:
                for term in self.text_index:
                    if token in term or term in token:
                        candidates.update(self.text_index[term])

        return candidates

    def _calculate_avg_terms_per_chunk(self) -> float:
        """Calculate average number of unique terms per chunk."""
        if not self.chunks:
            return 0.0

        total_terms = 0
        for chunk in self.chunks.values():
            tokens = self._tokenize(chunk.content)
            total_terms += len(tokens)

        return total_terms / len(self.chunks)

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage of indices in bytes."""
        # Rough estimation
        memory = 0

        # Text index
        for token, chunk_ids in self.text_index.items():
            memory += len(token) + len(chunk_ids) * 16  # Assume 16 bytes per ID

        # Other indices
        memory += len(self.type_index) * 50 * 16
        memory += len(self.file_index) * 100 * 16
        memory += len(self.language_index) * 20 * 16

        # Embeddings
        memory += len(self.embeddings) * 128 * 8  # 128 floats * 8 bytes

        return memory


class SmartQueryOptimizer(QueryOptimizer):
    """Optimize queries for better performance and results."""

    def __init__(self):
        """Initialize the optimizer with language models and patterns."""
        self.common_typos = self._load_common_typos()
        self.synonyms = self._load_programming_synonyms()
        self.stop_words = {
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
        }

    def _load_common_typos(self) -> dict[str, str]:
        """Load common programming typos."""
        return {
            "fucntion": "function",
            "funciton": "function",
            "calss": "class",
            "improt": "import",
            "retrun": "return",
            "ture": "true",
            "flase": "false",
            "nulll": "null",
            "undefinded": "undefined",
            "cosnt": "const",
            "vra": "var",
            "asyng": "async",
            "awiat": "await",
            "teh": "the",
            "adn": "and",
        }

    def _load_programming_synonyms(self) -> dict[str, list[str]]:
        """Load programming term synonyms."""
        return {
            "function": ["method", "func", "procedure", "routine"],
            "variable": ["var", "field", "attribute", "property"],
            "class": ["type", "struct", "object"],
            "error": ["exception", "fault", "bug", "issue"],
            "test": ["spec", "unittest", "check"],
            "import": ["include", "require", "using"],
            "authentication": ["auth", "login", "signin"],
            "configuration": ["config", "settings", "options"],
            "database": ["db", "datastore", "repository"],
            "api": ["endpoint", "service", "interface"],
        }

    def optimize_query(self, query: str, query_type: QueryType) -> str:
        """Optimize a query for better results."""
        if query_type == QueryType.NATURAL_LANGUAGE:
            return self._optimize_natural_language(query)
        if query_type == QueryType.STRUCTURED:
            return self._optimize_structured(query)
        if query_type == QueryType.REGEX:
            return self._optimize_regex(query)
        return query  # No optimization for other types

    def _optimize_natural_language(self, query: str) -> str:
        """Optimize natural language query."""
        words = query.lower().split()
        optimized_words = []

        for word in words:
            # Skip stop words
            if word in self.stop_words:
                continue

            # Fix typos
            if word in self.common_typos:
                word = self.common_typos[word]

            # Expand with synonyms
            expanded = False
            for base, synonyms in self.synonyms.items():
                if word == base or word in synonyms:
                    # Add base term and first synonym
                    optimized_words.append(base)
                    if synonyms and synonyms[0] != base:
                        optimized_words.append(synonyms[0])
                    expanded = True
                    break

            if not expanded:
                optimized_words.append(word)

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for word in optimized_words:
            if word not in seen:
                seen.add(word)
                result.append(word)

        return " ".join(result)

    def _optimize_structured(self, query: str) -> str:
        """Optimize structured query."""
        # Parse and reconstruct with corrections
        parts = []

        for part in query.split():
            if ":" in part:
                key, value = part.split(":", 1)

                # Normalize keys
                key_map = {
                    "typ": "type",
                    "lang": "language",
                    "fn": "function",
                    "cls": "class",
                }

                if key in key_map:
                    key = key_map[key]

                # Fix value typos
                if value in self.common_typos:
                    value = self.common_typos[value]

                parts.append(f"{key}:{value}")
            else:
                # Fix typos in keywords
                if part in self.common_typos:
                    part = self.common_typos[part]
                parts.append(part)

        return " ".join(parts)

    def _optimize_regex(self, query: str) -> str:
        """Optimize regex pattern."""
        # Add word boundaries for common patterns
        if query.isalnum():
            return rf"\b{query}\b"

        # Escape special characters if pattern looks like literal search
        if not any(c in query for c in r".*+?[]{}()^$|\\"):
            return re.escape(query)

        return query

    def suggest_queries(self, partial_query: str, chunks: list[CodeChunk]) -> list[str]:
        """Suggest query completions based on indexed content."""
        suggestions = []
        partial_lower = partial_query.lower()

        # Extract common terms from chunks
        term_freq = Counter()
        type_freq = Counter()

        for chunk in chunks[:100]:  # Sample first 100 chunks
            # Count node types
            type_freq[chunk.node_type] += 1

            # Count terms
            tokens = set(re.findall(r"\w+", chunk.content.lower()))
            for token in tokens:
                if len(token) >= 3 and token.startswith(partial_lower):
                    term_freq[token] += 1

        # Generate suggestions based on frequency

        # Natural language suggestions
        if not any(c in partial_query for c in ":="):
            # Suggest common terms
            for term, _count in term_freq.most_common(5):
                if term != partial_lower:
                    suggestions.append(term)

            # Suggest query patterns
            if partial_lower.startswith("find"):
                suggestions.extend(
                    [
                        "find all functions",
                        "find error handling",
                        "find test cases",
                    ],
                )
            elif partial_lower.startswith("show"):
                suggestions.extend(
                    [
                        "show me authentication code",
                        "show database queries",
                        "show configuration",
                    ],
                )

        # Structured query suggestions
        if ":" in partial_query:
            key, partial_value = partial_query.rsplit(":", 1)

            if key == "type":
                # Suggest node types
                for node_type, _count in type_freq.most_common(5):
                    if node_type.startswith(partial_value):
                        suggestions.append(f"{key}:{node_type}")

            elif key == "language":
                # Suggest languages
                languages = {chunk.language for chunk in chunks[:50]}
                suggestions.extend(
                    f"{key}:{lang}"
                    for lang in sorted(languages)
                    if lang.startswith(partial_value)
                )

        # Limit suggestions
        return suggestions[:10]

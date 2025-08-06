"""Chunk optimization implementation for adapting chunks to specific use cases."""

import re
from collections import defaultdict

from .interfaces.optimization import (
    ChunkBoundaryAnalyzer as ChunkBoundaryAnalyzerInterface,
)
from .interfaces.optimization import ChunkOptimizer as ChunkOptimizerInterface
from .interfaces.optimization import (
    OptimizationConfig,
    OptimizationMetrics,
    OptimizationStrategy,
)
from .token.counter import TiktokenCounter
from .types import CodeChunk


class ChunkOptimizer(ChunkOptimizerInterface):
    """Optimize chunk boundaries for specific use cases."""

    def __init__(self, config: OptimizationConfig | None = None):
        """Initialize the optimizer with configuration."""
        self.config = config or OptimizationConfig()
        self.token_counter = TiktokenCounter()
        self.boundary_analyzer = ChunkBoundaryAnalyzer()

    def optimize_for_llm(
        self,
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    ) -> tuple[list[CodeChunk], OptimizationMetrics]:
        """Optimize chunks for LLM consumption."""
        if not chunks:
            return [], OptimizationMetrics(0, 0, 0.0, 0.0, 0.0, 0.0)
        original_count = len(chunks)
        original_tokens = [
            self.token_counter.count_tokens(chunk.content, model) for chunk in chunks
        ]
        avg_tokens_before = (
            sum(original_tokens)
            / len(
                original_tokens,
            )
            if original_tokens
            else 0
        )
        optimized_chunks = chunks.copy()
        if strategy == OptimizationStrategy.AGGRESSIVE:
            optimized_chunks = self._aggressive_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )
        elif strategy == OptimizationStrategy.CONSERVATIVE:
            optimized_chunks = self._conservative_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )
        elif strategy == OptimizationStrategy.BALANCED:
            optimized_chunks = self._balanced_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )
        elif strategy == OptimizationStrategy.PRESERVE_STRUCTURE:
            optimized_chunks = self._preserve_structure_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )
        optimized_count = len(optimized_chunks)
        optimized_tokens = [
            self.token_counter.count_tokens(chunk.content, model)
            for chunk in optimized_chunks
        ]
        avg_tokens_after = (
            sum(optimized_tokens)
            / len(
                optimized_tokens,
            )
            if optimized_tokens
            else 0
        )
        coherence_score = self._calculate_coherence_score(optimized_chunks)
        token_efficiency = avg_tokens_after / max_tokens if max_tokens > 0 else 0
        metrics = OptimizationMetrics(
            original_count=original_count,
            optimized_count=optimized_count,
            avg_tokens_before=avg_tokens_before,
            avg_tokens_after=avg_tokens_after,
            coherence_score=coherence_score,
            token_efficiency=token_efficiency,
        )
        return optimized_chunks, metrics

    def merge_small_chunks(
        self,
        chunks: list[CodeChunk],
        min_tokens: int,
        preserve_boundaries: bool = True,
    ) -> list[CodeChunk]:
        """Merge chunks that are too small."""
        if not chunks:
            return []
        merged_chunks = []
        current_group = []
        current_tokens = 0
        for _i, chunk in enumerate(chunks):
            chunk_tokens = self.token_counter.count_tokens(chunk.content)
            if (preserve_boundaries and current_group) and not self._can_merge_chunks(
                current_group[-1],
                chunk,
            ):
                if current_group:
                    merged_chunks.append(
                        self._merge_chunk_group(current_group),
                    )
                current_group = [chunk]
                current_tokens = chunk_tokens
                continue
            current_group.append(chunk)
            current_tokens += chunk_tokens
            if current_tokens >= min_tokens:
                merged_chunks.append(self._merge_chunk_group(current_group))
                current_group = []
                current_tokens = 0
        if current_group:
            if merged_chunks and current_tokens < min_tokens:
                last_merged = merged_chunks[-1]
                last_tokens = self.token_counter.count_tokens(last_merged.content)
                if last_tokens + current_tokens < min_tokens * 2:
                    if not preserve_boundaries or self._can_merge_chunks(
                        last_merged,
                        current_group[0],
                    ):
                        merged_chunks[-1] = self._merge_chunk_group(
                            [last_merged, *current_group],
                        )
                    else:
                        merged_chunks.append(self._merge_chunk_group(current_group))
                else:
                    merged_chunks.append(
                        self._merge_chunk_group(current_group),
                    )
            else:
                merged_chunks.append(self._merge_chunk_group(current_group))
        return merged_chunks

    def split_large_chunks(
        self,
        chunks: list[CodeChunk],
        max_tokens: int,
        split_points: list[str] | None = None,
    ) -> list[CodeChunk]:
        """Split chunks that are too large."""
        if not chunks:
            return []
        if split_points is None:
            split_points = [
                "\n\n",
                "\ndef ",
                "\nclass ",
                "\n    def ",
                "\n        def ",
                "\n}",
                "\n]",
            ]
        split_chunks = []
        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(chunk.content)
            if chunk_tokens <= max_tokens:
                split_chunks.append(chunk)
                continue
            boundaries = self.boundary_analyzer.find_natural_boundaries(
                chunk.content,
                chunk.language,
            )
            sub_chunks = self._split_at_boundaries(chunk, boundaries, max_tokens)
            split_chunks.extend(sub_chunks)
        return split_chunks

    def rebalance_chunks(
        self,
        chunks: list[CodeChunk],
        target_tokens: int,
        variance: float = 0.2,
    ) -> list[CodeChunk]:
        """Rebalance chunks to have similar sizes."""
        if not chunks:
            return []
        min_tokens = int(target_tokens * (1 - variance))
        max_tokens = int(target_tokens * (1 + variance))
        chunks = self.split_large_chunks(chunks, max_tokens)
        chunks = self.merge_small_chunks(chunks, min_tokens)
        rebalanced = []
        buffer_chunk = None
        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(chunk.content)
            if min_tokens <= chunk_tokens <= max_tokens:
                rebalanced.append(chunk)
            elif chunk_tokens < min_tokens:
                if buffer_chunk:
                    combined = self._merge_chunk_group([buffer_chunk, chunk])
                    combined_tokens = self.token_counter.count_tokens(combined.content)
                    if combined_tokens <= max_tokens:
                        buffer_chunk = combined
                    else:
                        rebalanced.append(buffer_chunk)
                        buffer_chunk = chunk
                else:
                    buffer_chunk = chunk
            else:
                if buffer_chunk:
                    rebalanced.append(buffer_chunk)
                    buffer_chunk = None
                rebalanced.append(chunk)
        if buffer_chunk:
            rebalanced.append(buffer_chunk)
        return rebalanced

    def optimize_for_embedding(
        self,
        chunks: list[CodeChunk],
        embedding_model: str,
        max_tokens: int = 512,
    ) -> list[CodeChunk]:
        """Optimize chunks for embedding generation."""
        if not chunks:
            return []
        optimized = []
        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(
                chunk.content,
                embedding_model,
            )
            if chunk_tokens <= max_tokens:
                optimized.append(chunk)
            else:
                sub_chunks = self._split_for_embedding(
                    chunk,
                    max_tokens,
                    embedding_model,
                )
                optimized.extend(sub_chunks)
        return self._ensure_semantic_coherence(optimized, embedding_model, max_tokens)

    def _aggressive_optimization(
        self,
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
    ) -> list[CodeChunk]:
        """Aggressive optimization: maximize merging and splitting."""
        merged = []
        current_group = []
        current_tokens = 0
        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(
                chunk.content,
                model,
            )
            if current_tokens + chunk_tokens <= max_tokens:
                current_group.append(chunk)
                current_tokens += chunk_tokens
            else:
                if current_group:
                    merged.append(self._merge_chunk_group(current_group))
                current_group = [chunk]
                current_tokens = chunk_tokens
        if current_group:
            merged.append(self._merge_chunk_group(current_group))
        return self.split_large_chunks(merged, max_tokens)

    def _conservative_optimization(
        self,
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
    ) -> list[CodeChunk]:
        """Conservative optimization: minimal changes."""
        optimized = []
        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(
                chunk.content,
                model,
            )
            if chunk_tokens <= max_tokens:
                optimized.append(chunk)
            else:
                sub_chunks = self._minimal_split(chunk, max_tokens, model)
                optimized.extend(sub_chunks)
        return optimized

    def _balanced_optimization(
        self,
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
    ) -> list[CodeChunk]:
        """Balanced optimization: smart merging and splitting."""
        target_tokens = int(max_tokens * 0.7)
        variance = 0.3
        chunk_groups = self._identify_related_chunks(chunks)
        optimized = []
        for group in chunk_groups:
            group_tokens = sum(
                self.token_counter.count_tokens(c.content, model) for c in group
            )
            if group_tokens <= max_tokens:
                optimized.append(self._merge_chunk_group(group))
            else:
                rebalanced = self.rebalance_chunks(group, target_tokens, variance)
                optimized.extend(rebalanced)
        return optimized

    def _preserve_structure_optimization(
        self,
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
    ) -> list[CodeChunk]:
        """Preserve structure optimization: maintain original structure as much as possible."""
        optimized = []
        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(
                chunk.content,
                model,
            )
            if chunk_tokens <= max_tokens:
                optimized.append(chunk)
            else:
                sub_chunks = self._structure_preserving_split(chunk, max_tokens, model)
                optimized.extend(sub_chunks)
        return optimized

    def _structure_preserving_split(
        self,
        chunk: CodeChunk,
        max_tokens: int,
        model: str,
    ) -> list[CodeChunk]:
        """Split a chunk while preserving as much structure as possible."""
        structural_patterns = {
            "python": [
                ("\\n(?=class\\s+)", "class"),
                ("\\n(?=def\\s+)", "function"),
                ("\\n(?=async\\s+def\\s+)", "async_function"),
            ],
            "javascript": [
                (
                    "\\n(?=class\\s+)",
                    "class",
                ),
                ("\\n(?=function\\s+)", "function"),
                ("\\n(?=export\\s+)", "export"),
            ],
            "java": [
                ("\\n(?=public\\s+class\\s+)", "class"),
                ("\\n(?=private\\s+class\\s+)", "class"),
                ("\\n(?=public\\s+.*\\s+\\w+\\s*\\()", "method"),
                ("\\n(?=private\\s+.*\\s+\\w+\\s*\\()", "method"),
            ],
        }
        patterns = structural_patterns.get(chunk.language, [])
        content = chunk.content
        boundaries = []
        for pattern, boundary_type in patterns:
            boundaries.extend(
                (match.start(), boundary_type)
                for match in re.finditer(pattern, content)
            )
        if not boundaries:
            return self._minimal_split(chunk, max_tokens, model)
        boundaries.sort(key=lambda x: x[0])
        sub_chunks = []
        start = 0
        for pos, _boundary_type in boundaries:
            if pos > start:
                sub_content = content[start:pos].strip()
                if sub_content:
                    sub_tokens = self.token_counter.count_tokens(sub_content, model)
                    if sub_tokens <= max_tokens:
                        sub_chunks.append(
                            self._create_sub_chunk(chunk, sub_content, 0, 0),
                        )
                    else:
                        sub_chunks.extend(
                            self._minimal_split(
                                self._create_sub_chunk(chunk, sub_content, 0, 0),
                                max_tokens,
                                model,
                            ),
                        )
                start = pos
        if start < len(content):
            sub_content = content[start:].strip()
            if sub_content:
                sub_chunks.append(self._create_sub_chunk(chunk, sub_content, 0, 0))
        return sub_chunks if sub_chunks else [chunk]

    @staticmethod
    def _can_merge_chunks(chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks can be merged based on their properties."""
        if chunk1.file_path != chunk2.file_path:
            return False
        if chunk1.end_line + 1 != chunk2.start_line:
            return False
        related_types = {
            "function": {"function", "method", "async_function"},
            "class": {"class", "class_method", "constructor"},
            "module": {"import", "export", "module"},
        }
        for group in related_types.values():
            if chunk1.node_type in group and chunk2.node_type in group:
                return True
        return bool(chunk2.parent_context.startswith(chunk1.parent_context))

    @classmethod
    def _merge_chunk_group(cls, chunks: list[CodeChunk]) -> CodeChunk:
        """Merge a group of chunks into a single chunk."""
        if not chunks:
            raise ValueError("Cannot merge empty chunk group")
        if len(chunks) == 1:
            return chunks[0]
        chunks = sorted(chunks, key=lambda c: (c.file_path, c.start_line))
        first_chunk = chunks[0]
        last_chunk = chunks[-1]
        combined_content = "\n".join(chunk.content for chunk in chunks)
        merged_metadata = {}
        all_references = []
        all_dependencies = []
        for chunk in chunks:
            merged_metadata.update(chunk.metadata)
            all_references.extend(chunk.references)
            all_dependencies.extend(chunk.dependencies)
        all_references = list(dict.fromkeys(all_references))
        all_dependencies = list(dict.fromkeys(all_dependencies))
        merged_chunk = CodeChunk(
            language=first_chunk.language,
            file_path=first_chunk.file_path,
            node_type=f"merged_{first_chunk.node_type}",
            start_line=first_chunk.start_line,
            end_line=last_chunk.end_line,
            byte_start=first_chunk.byte_start,
            byte_end=last_chunk.byte_end,
            parent_context=first_chunk.parent_context,
            content=combined_content,
            references=all_references,
            dependencies=all_dependencies,
            metadata=merged_metadata,
        )
        return merged_chunk

    def _split_at_boundaries(
        self,
        chunk: CodeChunk,
        boundaries: list[int],
        max_tokens: int,
    ) -> list[CodeChunk]:
        """Split a chunk at natural boundaries."""
        if not boundaries:
            return self._token_based_split(chunk, max_tokens)
        sub_chunks = []
        content = chunk.content
        lines = content.split("\n")
        line_boundaries = []
        byte_count = 0
        for i, line in enumerate(lines):
            line_bytes = len(line.encode()) + 1
            line_boundaries.extend(
                i
                for boundary in boundaries
                if byte_count <= boundary < byte_count + line_bytes
            )
            byte_count += line_bytes
        line_boundaries = sorted(set(line_boundaries))
        start_idx = 0
        for boundary_idx in line_boundaries:
            if boundary_idx > start_idx:
                sub_content = "\n".join(lines[start_idx:boundary_idx])
                if sub_content.strip():
                    sub_chunk = self._create_sub_chunk(
                        chunk,
                        sub_content,
                        start_idx,
                        boundary_idx - 1,
                    )
                    sub_chunks.append(sub_chunk)
                start_idx = boundary_idx
        if start_idx < len(lines):
            sub_content = "\n".join(lines[start_idx:])
            if sub_content.strip():
                sub_chunk = self._create_sub_chunk(
                    chunk,
                    sub_content,
                    start_idx,
                    len(lines) - 1,
                )
                sub_chunks.append(sub_chunk)
        final_chunks = []
        for sub_chunk in sub_chunks:
            sub_tokens = self.token_counter.count_tokens(sub_chunk.content)
            if sub_tokens <= max_tokens:
                final_chunks.append(sub_chunk)
            else:
                final_chunks.extend(self._token_based_split(sub_chunk, max_tokens))
        return final_chunks

    def _token_based_split(self, chunk: CodeChunk, max_tokens: int) -> list[CodeChunk]:
        """Split a chunk based on token count."""
        text_chunks = self.token_counter.split_text_by_tokens(
            chunk.content,
            max_tokens,
            "gpt-4",
        )
        sub_chunks = []
        chunk.content.split("\n")
        current_line = chunk.start_line
        for text in text_chunks:
            text_lines = text.split("\n")
            end_line = current_line + len(text_lines) - 1
            sub_chunk = CodeChunk(
                language=chunk.language,
                file_path=chunk.file_path,
                node_type=f"split_{chunk.node_type}",
                start_line=current_line,
                end_line=end_line,
                byte_start=chunk.byte_start,
                byte_end=chunk.byte_end,
                parent_context=chunk.parent_context,
                content=text,
                parent_chunk_id=chunk.chunk_id,
                references=chunk.references.copy(),
                dependencies=chunk.dependencies.copy(),
                metadata=chunk.metadata.copy(),
            )
            sub_chunks.append(sub_chunk)
            current_line = end_line + 1
        return sub_chunks

    @classmethod
    def _create_sub_chunk(
        cls,
        parent: CodeChunk,
        content: str,
        start_line_offset: int,
        end_line_offset: int,
    ) -> CodeChunk:
        """Create a sub-chunk from a parent chunk."""
        return CodeChunk(
            language=parent.language,
            file_path=parent.file_path,
            node_type=f"sub_{parent.node_type}",
            start_line=parent.start_line + start_line_offset,
            end_line=parent.start_line + end_line_offset,
            byte_start=parent.byte_start,
            byte_end=parent.byte_end,
            parent_context=parent.parent_context,
            content=content,
            parent_chunk_id=parent.chunk_id,
            references=parent.references.copy(),
            dependencies=parent.dependencies.copy(),
            metadata=parent.metadata.copy(),
        )

    def _minimal_split(
        self,
        chunk: CodeChunk,
        max_tokens: int,
        model: str,
    ) -> list[CodeChunk]:
        """Minimally split a chunk, preserving as much structure as possible."""
        method_pattern = "\\n(?=\\s*(def|class|function|public|private|protected)\\s+)"
        parts = re.split(method_pattern, chunk.content)
        if len(parts) > 1:
            sub_chunks = []
            current_content = ""
            for part in parts:
                test_content = current_content + part
                test_tokens = self.token_counter.count_tokens(test_content, model)
                if test_tokens <= max_tokens:
                    current_content = test_content
                else:
                    if current_content:
                        sub_chunks.append(
                            self._create_sub_chunk(chunk, current_content, 0, 0),
                        )
                    current_content = part
            if current_content:
                sub_chunks.append(self._create_sub_chunk(chunk, current_content, 0, 0))
            return sub_chunks if sub_chunks else [chunk]
        return self._token_based_split(chunk, max_tokens)

    def _identify_related_chunks(
        self,
        chunks: list[CodeChunk],
    ) -> list[list[CodeChunk]]:
        """Identify groups of related chunks that should be optimized together."""
        if not chunks:
            return []
        file_groups = defaultdict(list)
        for chunk in chunks:
            file_groups[chunk.file_path].append(chunk)
        all_groups = []
        for file_chunks in file_groups.values():
            file_chunks.sort(key=lambda c: c.start_line)
            current_group = []
            for chunk in file_chunks:
                if not current_group or self._are_chunks_related(
                    current_group[-1],
                    chunk,
                ):
                    current_group.append(chunk)
                else:
                    all_groups.append(current_group)
                    current_group = [chunk]
            if current_group:
                all_groups.append(current_group)
        return all_groups

    @staticmethod
    def _are_chunks_related(chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks are related enough to group together."""
        if chunk1.file_path != chunk2.file_path:
            return False
        if chunk2.start_line - chunk1.end_line > 10:
            return False
        if (
            "class_name" in chunk1.metadata and "class_name" in chunk2.metadata
        ) and chunk1.metadata["class_name"] == chunk2.metadata["class_name"]:
            return True
        if chunk2.chunk_id in chunk1.references or chunk1.chunk_id in chunk2.references:
            return True
        shared_deps = set(chunk1.dependencies) & set(chunk2.dependencies)
        return len(shared_deps) > 0

    def _split_for_embedding(
        self,
        chunk: CodeChunk,
        max_tokens: int,
        model: str,
    ) -> list[CodeChunk]:
        """Split a chunk specifically for embedding generation."""
        content = chunk.content
        split_patterns = [
            ("\\n(?=def\\s+)", "function"),
            ("\\n(?=class\\s+)", "class"),
            ("\\n(?=async\\s+def\\s+)", "async_function"),
            ('\\n(?=\\s*""")', "docstring"),
            ("\\n(?=\\s*#\\s*[A-Z])", "comment_block"),
            ("\\n\\n", "paragraph"),
        ]
        split_points = []
        for pattern, split_type in split_patterns:
            split_points.extend(
                (match.start(), split_type) for match in re.finditer(pattern, content)
            )
        split_points.sort(key=lambda x: x[0])
        sub_chunks = []
        start = 0
        for split_pos, split_type in split_points:
            if split_pos > start:
                sub_content = content[start:split_pos].strip()
                if sub_content:
                    sub_tokens = self.token_counter.count_tokens(sub_content, model)
                    if sub_tokens <= max_tokens:
                        sub_chunks.append(
                            self._create_embedding_chunk(
                                chunk,
                                sub_content,
                                split_type,
                            ),
                        )
                    else:
                        sub_chunks.extend(
                            self._token_based_split(
                                self._create_embedding_chunk(
                                    chunk,
                                    sub_content,
                                    split_type,
                                ),
                                max_tokens,
                            ),
                        )
                start = split_pos
        if start < len(content):
            sub_content = content[start:].strip()
            if sub_content:
                sub_chunks.append(
                    self._create_embedding_chunk(chunk, sub_content, "remainder"),
                )
        return sub_chunks if sub_chunks else [chunk]

    @classmethod
    def _create_embedding_chunk(
        cls,
        parent: CodeChunk,
        content: str,
        chunk_type: str,
    ) -> CodeChunk:
        """Create a chunk optimized for embedding."""
        embedding_chunk = CodeChunk(
            language=parent.language,
            file_path=parent.file_path,
            node_type=f"embedding_{chunk_type}",
            start_line=parent.start_line,
            end_line=parent.end_line,
            byte_start=parent.byte_start,
            byte_end=parent.byte_end,
            parent_context=parent.parent_context,
            content=content,
            parent_chunk_id=parent.chunk_id,
            references=parent.references.copy(),
            dependencies=parent.dependencies.copy(),
            metadata={
                **parent.metadata,
                "embedding_optimized": True,
                "chunk_type": chunk_type,
            },
        )
        return embedding_chunk

    @staticmethod
    def _ensure_semantic_coherence(
        chunks: list[CodeChunk],
        _model: str,
        _max_tokens: int,
    ) -> list[CodeChunk]:
        """Ensure chunks maintain semantic coherence for embeddings."""
        coherent_chunks = []
        for chunk in chunks:
            content = chunk.content.strip()
            incomplete_start_patterns = [
                "^\\s*\\)",
                "^\\s*\\}",
                "^\\s*\\]",
                "^\\s*else",
                "^\\s*elif",
                "^\\s*except",
                "^\\s*finally",
            ]
            incomplete_end_patterns = [
                ":\\s*$",
                ",\\s*$",
                "\\(\\s*$",
                "\\[\\s*$",
                "\\{\\s*$",
            ]
            needs_adjustment = False
            for pattern in incomplete_start_patterns:
                if re.search(pattern, content):
                    needs_adjustment = True
                    break
            if not needs_adjustment:
                for pattern in incomplete_end_patterns:
                    if re.search(pattern, content):
                        needs_adjustment = True
                        break
            if needs_adjustment:
                coherent_chunks.append(chunk)
            else:
                coherent_chunks.append(chunk)
        return coherent_chunks

    @staticmethod
    def _calculate_coherence_score(chunks: list[CodeChunk]) -> float:
        """Calculate how well chunks maintain semantic unity."""
        if not chunks:
            return 0.0
        scores = []
        for chunk in chunks:
            score = 1.0
            content = chunk.content.strip()
            if re.search(r":\\s*$", content):
                score *= 0.8
            if re.search(r"^\s*\)", content):
                score *= 0.7
            if re.search(r"^\s*(else|elif|except|finally)", content):
                score *= 0.6
            if re.match(
                r"^(def|class|async def)\s+\w+.*:\s*\n.*\n\s*$",
                content,
                re.DOTALL,
            ):
                score = min(score * 1.2, 1.0)
            open_braces = content.count("{") - content.count("}")
            open_parens = content.count("(") - content.count(")")
            open_brackets = content.count("[") - content.count("]")
            if open_braces == 0 and open_parens == 0 and open_brackets == 0:
                score = min(score * 1.1, 1.0)
            else:
                score *= 0.9
            scores.append(score)
        return sum(scores) / len(scores) if scores else 0.0


class ChunkBoundaryAnalyzer(ChunkBoundaryAnalyzerInterface):
    """Analyze and suggest optimal chunk boundaries."""

    def __init__(self):
        """Initialize the boundary analyzer."""
        self.language_patterns = {
            "python": {
                "function": "\\n(?=def\\s+\\w+)",
                "class": "\\n(?=class\\s+\\w+)",
                "method": "\\n(?=\\s+def\\s+\\w+)",
                "async_function": "\\n(?=async\\s+def\\s+\\w+)",
                "block_end": "\\n(?=\\S)",
                "import": "\\n(?=(from|import)\\s+)",
            },
            "javascript": {
                "function": "\\n(?=function\\s+\\w+)",
                "arrow_function": "\\n(?=const\\s+\\w+\\s*=\\s*\\()",
                "class": "\\n(?=class\\s+\\w+)",
                "method": "\\n(?=\\s+\\w+\\s*\\()",
                "block_end": "\\n\\}",
                "import": "\\n(?=(import|export)\\s+)",
            },
            "java": {
                "class": "\\n(?=(public|private|protected)?\\s*class\\s+)",
                "method": "\\n(?=(public|private|protected)?\\s*\\w+\\s+\\w+\\s*\\()",
                "block_end": "\\n\\}",
                "import": "\\n(?=import\\s+)",
            },
        }

    def find_natural_boundaries(self, content: str, language: str) -> list[int]:
        """Find natural boundary points in code."""
        boundaries = set()
        patterns = self.language_patterns.get(language, {})
        for pattern in patterns.values():
            for match in re.finditer(pattern, content):
                boundaries.add(match.start())
        for match in re.finditer(r"\n\n", content):
            boundaries.add(match.start())
        for match in re.finditer(r"\n(?=\s*#\s*[A-Z])", content):
            boundaries.add(match.start())
        for match in re.finditer(r"\n(?=\s*/\*)", content):
            boundaries.add(match.start())
        for match in re.finditer(r'\n(?=\s*""")', content):
            boundaries.add(match.start())
        if not boundaries and len(content) > 100:
            lines = content.split("\n")
            if len(lines) > 10:
                for i in range(10, len(lines), 10):
                    pos = len("\n".join(lines[:i]))
                    boundaries.add(pos)
        return sorted(boundaries)

    @staticmethod
    def score_boundary(content: str, position: int, _language: str) -> float:
        """Score how good a boundary point is."""
        if position < 0 or position >= len(content):
            return 0.0
        score = 0.5
        before = content[:position]
        after = content[position:]
        if before.strip():
            open_braces = before.count("{") - before.count("}")
            open_parens = before.count("(") - before.count(")")
            if open_braces == 0 and open_parens == 0:
                score += 0.2
            if re.search(r"[;}\]]\s*$", before):
                score += 0.1
        if after.strip():
            if re.match(r"\s*(def|class|function|public|private)", after):
                score += 0.2
            if re.match(r"\s*(import|from|export)", after):
                score += 0.15
            if re.match(r"\s*#|/\*|//", after):
                score += 0.1
        quote_count = before.count('"') + before.count("'")
        if quote_count % 2 != 0:
            score *= 0.5
        return min(score, 1.0)

    def suggest_merge_points(
        self,
        chunks: list[CodeChunk],
    ) -> list[tuple[int, int, float]]:
        """Suggest which chunks to merge based on their relationships."""
        suggestions = []
        for i in range(len(chunks) - 1):
            for j in range(i + 1, min(i + 5, len(chunks))):
                chunk1 = chunks[i]
                chunk2 = chunks[j]
                score = self._calculate_merge_score(chunk1, chunk2)
                if score > 0.5:
                    suggestions.append((i, j, score))
        suggestions.sort(key=lambda x: x[2], reverse=True)
        return suggestions

    @staticmethod
    def _calculate_merge_score(chunk1: CodeChunk, chunk2: CodeChunk) -> float:
        """Calculate score for merging two chunks."""
        score = 0.0
        if chunk1.file_path != chunk2.file_path:
            return 0.0
        line_distance = chunk2.start_line - chunk1.end_line
        if line_distance == 1:
            score += 0.4
        elif line_distance <= 5:
            score += 0.2
        elif line_distance <= 10:
            score += 0.1
        else:
            return 0.0
        if chunk1.parent_context == chunk2.parent_context:
            score += 0.2
        related_types = {
            ("function", "function"),
            ("class", "method"),
            ("class", "constructor"),
            ("import", "import"),
        }
        if (chunk1.node_type, chunk2.node_type) in related_types:
            score += 0.2
        if chunk2.chunk_id in chunk1.references or chunk1.chunk_id in chunk2.references:
            score += 0.3
        shared_deps = set(chunk1.dependencies) & set(chunk2.dependencies)
        if shared_deps:
            score += min(0.2, len(shared_deps) * 0.05)
        return min(score, 1.0)

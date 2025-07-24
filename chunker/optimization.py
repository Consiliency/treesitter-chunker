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

        # Calculate original metrics
        original_count = len(chunks)
        original_tokens = [
            self.token_counter.count_tokens(chunk.content, model) for chunk in chunks
        ]
        avg_tokens_before = (
            sum(original_tokens) / len(original_tokens) if original_tokens else 0
        )

        # Apply optimization based on strategy
        optimized_chunks = chunks.copy()

        if strategy == OptimizationStrategy.AGGRESSIVE:
            # Aggressive: maximize merging and splitting
            optimized_chunks = self._aggressive_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )
        elif strategy == OptimizationStrategy.CONSERVATIVE:
            # Conservative: minimal changes, only split oversized chunks
            optimized_chunks = self._conservative_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )
        elif strategy == OptimizationStrategy.BALANCED:
            # Balanced: smart merging and splitting while preserving structure
            optimized_chunks = self._balanced_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )
        elif strategy == OptimizationStrategy.PRESERVE_STRUCTURE:
            # Preserve structure: maintain original code structure, only split if absolutely necessary
            optimized_chunks = self._preserve_structure_optimization(
                optimized_chunks,
                model,
                max_tokens,
            )

        # Calculate optimized metrics
        optimized_count = len(optimized_chunks)
        optimized_tokens = [
            self.token_counter.count_tokens(chunk.content, model)
            for chunk in optimized_chunks
        ]
        avg_tokens_after = (
            sum(optimized_tokens) / len(optimized_tokens) if optimized_tokens else 0
        )

        # Calculate coherence score (how well chunks maintain semantic unity)
        coherence_score = self._calculate_coherence_score(optimized_chunks)

        # Calculate token efficiency (percentage of token limit used)
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

        for i, chunk in enumerate(chunks):
            chunk_tokens = self.token_counter.count_tokens(chunk.content)

            if preserve_boundaries and current_group:
                # Check if this chunk can be merged with the current group
                if not self._can_merge_chunks(current_group[-1], chunk):
                    # Can't merge, finalize current group
                    if current_group:
                        merged_chunks.append(self._merge_chunk_group(current_group))
                    current_group = [chunk]
                    current_tokens = chunk_tokens
                    continue

            # Add to current group
            current_group.append(chunk)
            current_tokens += chunk_tokens

            # Check if we've reached the minimum size
            if current_tokens >= min_tokens:
                merged_chunks.append(self._merge_chunk_group(current_group))
                current_group = []
                current_tokens = 0

        # Handle remaining chunks
        if current_group:
            if merged_chunks and current_tokens < min_tokens:
                # Try to merge with the last chunk if it's small
                last_merged = merged_chunks[-1]
                last_tokens = self.token_counter.count_tokens(last_merged.content)
                if last_tokens + current_tokens < min_tokens * 2:
                    # Check if we can merge respecting boundaries
                    if not preserve_boundaries or self._can_merge_chunks(
                        last_merged,
                        current_group[0],
                    ):
                        # Merge with last chunk
                        merged_chunks[-1] = self._merge_chunk_group(
                            [last_merged] + current_group,
                        )
                    else:
                        # Can't merge, add as separate chunk
                        merged_chunks.append(self._merge_chunk_group(current_group))
                else:
                    merged_chunks.append(self._merge_chunk_group(current_group))
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

            # Find natural boundaries in the chunk
            boundaries = self.boundary_analyzer.find_natural_boundaries(
                chunk.content,
                chunk.language,
            )

            # Split the chunk at natural boundaries
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

        # First pass: split large chunks
        chunks = self.split_large_chunks(chunks, max_tokens)

        # Second pass: merge small chunks
        chunks = self.merge_small_chunks(chunks, min_tokens)

        # Third pass: redistribute content for better balance
        rebalanced = []
        buffer_chunk = None

        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(chunk.content)

            if min_tokens <= chunk_tokens <= max_tokens:
                # Chunk is within target range
                rebalanced.append(chunk)
            elif chunk_tokens < min_tokens:
                # Too small, try to combine with buffer
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
                # Still too large after splitting, add as is
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

        # For embeddings, we want semantically coherent chunks that fit within limits
        optimized = []

        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(
                chunk.content,
                embedding_model,
            )

            if chunk_tokens <= max_tokens:
                optimized.append(chunk)
            else:
                # Split into semantically meaningful sub-chunks
                sub_chunks = self._split_for_embedding(
                    chunk,
                    max_tokens,
                    embedding_model,
                )
                optimized.extend(sub_chunks)

        # Ensure chunks have good semantic boundaries
        return self._ensure_semantic_coherence(optimized, embedding_model, max_tokens)

    def _aggressive_optimization(
        self,
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
    ) -> list[CodeChunk]:
        """Aggressive optimization: maximize merging and splitting."""
        # First, merge all possible chunks
        merged = []
        current_group = []
        current_tokens = 0

        for chunk in chunks:
            chunk_tokens = self.token_counter.count_tokens(chunk.content, model)

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

        # Then split any chunks that are still too large
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
            chunk_tokens = self.token_counter.count_tokens(chunk.content, model)

            if chunk_tokens <= max_tokens:
                optimized.append(chunk)
            else:
                # Only split if absolutely necessary
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
        # Target size is 70% of max to leave room for context
        target_tokens = int(max_tokens * 0.7)
        variance = 0.3

        # First, identify related chunks that should stay together
        chunk_groups = self._identify_related_chunks(chunks)

        optimized = []
        for group in chunk_groups:
            group_tokens = sum(
                self.token_counter.count_tokens(c.content, model) for c in group
            )

            if group_tokens <= max_tokens:
                # Merge related chunks if they fit
                optimized.append(self._merge_chunk_group(group))
            else:
                # Rebalance the group
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
            chunk_tokens = self.token_counter.count_tokens(chunk.content, model)

            if chunk_tokens <= max_tokens:
                # Chunk is fine as is
                optimized.append(chunk)
            else:
                # Only split if absolutely necessary, and try to preserve logical units
                # Use the most conservative splitting approach
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
        # First try to split at major structural boundaries only
        structural_patterns = {
            "python": [
                (r"\n(?=class\s+)", "class"),
                (r"\n(?=def\s+)", "function"),
                (r"\n(?=async\s+def\s+)", "async_function"),
            ],
            "javascript": [
                (r"\n(?=class\s+)", "class"),
                (r"\n(?=function\s+)", "function"),
                (r"\n(?=export\s+)", "export"),
            ],
            "java": [
                (r"\n(?=public\s+class\s+)", "class"),
                (r"\n(?=private\s+class\s+)", "class"),
                (r"\n(?=public\s+.*\s+\w+\s*\()", "method"),
                (r"\n(?=private\s+.*\s+\w+\s*\()", "method"),
            ],
        }

        patterns = structural_patterns.get(chunk.language, [])
        content = chunk.content

        # Find structural boundaries
        boundaries = []
        for pattern, boundary_type in patterns:
            for match in re.finditer(pattern, content):
                boundaries.append((match.start(), boundary_type))

        if not boundaries:
            # No structural boundaries found, fall back to minimal split
            return self._minimal_split(chunk, max_tokens, model)

        # Sort boundaries by position
        boundaries.sort(key=lambda x: x[0])

        # Try to split at structural boundaries
        sub_chunks = []
        start = 0

        for pos, boundary_type in boundaries:
            if pos > start:
                sub_content = content[start:pos].strip()
                if sub_content:
                    sub_tokens = self.token_counter.count_tokens(sub_content, model)
                    if sub_tokens <= max_tokens:
                        sub_chunks.append(
                            self._create_sub_chunk(chunk, sub_content, 0, 0),
                        )
                    else:
                        # Even a structural unit is too large, need to split it
                        sub_chunks.extend(
                            self._minimal_split(
                                self._create_sub_chunk(chunk, sub_content, 0, 0),
                                max_tokens,
                                model,
                            ),
                        )
                start = pos

        # Add remaining content
        if start < len(content):
            sub_content = content[start:].strip()
            if sub_content:
                sub_chunks.append(self._create_sub_chunk(chunk, sub_content, 0, 0))

        return sub_chunks if sub_chunks else [chunk]

    def _can_merge_chunks(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks can be merged based on their properties."""
        # Same file and consecutive lines
        if chunk1.file_path != chunk2.file_path:
            return False

        # Check if chunks are adjacent
        if chunk1.end_line + 1 != chunk2.start_line:
            return False

        # Check if they have similar node types or are related
        related_types = {
            "function": {"function", "method", "async_function"},
            "class": {"class", "class_method", "constructor"},
            "module": {"import", "export", "module"},
        }

        for group in related_types.values():
            if chunk1.node_type in group and chunk2.node_type in group:
                return True

        # Check if one is a child of the other based on parent context
        if chunk2.parent_context.startswith(chunk1.parent_context):
            return True

        return False

    def _merge_chunk_group(self, chunks: list[CodeChunk]) -> CodeChunk:
        """Merge a group of chunks into a single chunk."""
        if not chunks:
            raise ValueError("Cannot merge empty chunk group")

        if len(chunks) == 1:
            return chunks[0]

        # Sort by start line to ensure correct order
        chunks = sorted(chunks, key=lambda c: (c.file_path, c.start_line))

        first_chunk = chunks[0]
        last_chunk = chunks[-1]

        # Combine content
        combined_content = "\n".join(chunk.content for chunk in chunks)

        # Merge metadata
        merged_metadata = {}
        all_references = []
        all_dependencies = []

        for chunk in chunks:
            merged_metadata.update(chunk.metadata)
            all_references.extend(chunk.references)
            all_dependencies.extend(chunk.dependencies)

        # Remove duplicates while preserving order
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
            # No natural boundaries, fall back to token-based splitting
            return self._token_based_split(chunk, max_tokens)

        sub_chunks = []
        content = chunk.content
        lines = content.split("\n")

        # Convert byte boundaries to line boundaries
        line_boundaries = []
        byte_count = 0
        for i, line in enumerate(lines):
            line_bytes = len(line.encode()) + 1  # +1 for newline
            for boundary in boundaries:
                if byte_count <= boundary < byte_count + line_bytes:
                    line_boundaries.append(i)
            byte_count += line_bytes

        # Remove duplicates and sort
        line_boundaries = sorted(set(line_boundaries))

        # Split at boundaries
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

        # Add remaining content
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

        # Ensure all sub-chunks respect max_tokens
        final_chunks = []
        for sub_chunk in sub_chunks:
            sub_tokens = self.token_counter.count_tokens(sub_chunk.content)
            if sub_tokens <= max_tokens:
                final_chunks.append(sub_chunk)
            else:
                # Need to split further
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
        lines = chunk.content.split("\n")
        current_line = chunk.start_line

        for text in text_chunks:
            # Calculate line numbers for this sub-chunk
            text_lines = text.split("\n")
            end_line = current_line + len(text_lines) - 1

            sub_chunk = CodeChunk(
                language=chunk.language,
                file_path=chunk.file_path,
                node_type=f"split_{chunk.node_type}",
                start_line=current_line,
                end_line=end_line,
                byte_start=chunk.byte_start,  # Approximate
                byte_end=chunk.byte_end,  # Approximate
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

    def _create_sub_chunk(
        self,
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
            byte_start=parent.byte_start,  # Approximate
            byte_end=parent.byte_end,  # Approximate
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
        # Try to split at method boundaries first
        method_pattern = r"\n(?=\s*(def|class|function|public|private|protected)\s+)"
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
                            self._create_sub_chunk(
                                chunk,
                                current_content,
                                0,
                                0,  # Line numbers would need calculation
                            ),
                        )
                    current_content = part

            if current_content:
                sub_chunks.append(
                    self._create_sub_chunk(
                        chunk,
                        current_content,
                        0,
                        0,
                    ),
                )

            return sub_chunks if sub_chunks else [chunk]

        # Fall back to token-based splitting
        return self._token_based_split(chunk, max_tokens)

    def _identify_related_chunks(
        self,
        chunks: list[CodeChunk],
    ) -> list[list[CodeChunk]]:
        """Identify groups of related chunks that should be optimized together."""
        if not chunks:
            return []

        # Group by file first
        file_groups = defaultdict(list)
        for chunk in chunks:
            file_groups[chunk.file_path].append(chunk)

        all_groups = []

        for file_chunks in file_groups.values():
            # Sort by start line
            file_chunks.sort(key=lambda c: c.start_line)

            # Group related chunks within the file
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

    def _are_chunks_related(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if two chunks are related enough to group together."""
        # Same file
        if chunk1.file_path != chunk2.file_path:
            return False

        # Close proximity (within 10 lines)
        if chunk2.start_line - chunk1.end_line > 10:
            return False

        # Check for relationships in metadata
        if "class_name" in chunk1.metadata and "class_name" in chunk2.metadata:
            if chunk1.metadata["class_name"] == chunk2.metadata["class_name"]:
                return True

        # Check for cross-references
        if chunk2.chunk_id in chunk1.references or chunk1.chunk_id in chunk2.references:
            return True

        # Check for shared dependencies
        shared_deps = set(chunk1.dependencies) & set(chunk2.dependencies)
        if len(shared_deps) > 0:
            return True

        return False

    def _split_for_embedding(
        self,
        chunk: CodeChunk,
        max_tokens: int,
        model: str,
    ) -> list[CodeChunk]:
        """Split a chunk specifically for embedding generation."""
        # For embeddings, we want to preserve semantic units
        # Try to split at:
        # 1. Function/method boundaries
        # 2. Class boundaries
        # 3. Logical blocks (if/else, loops)
        # 4. Comment blocks

        content = chunk.content

        # Find all potential split points
        split_patterns = [
            (r"\n(?=def\s+)", "function"),
            (r"\n(?=class\s+)", "class"),
            (r"\n(?=async\s+def\s+)", "async_function"),
            (r'\n(?=\s*""")', "docstring"),
            (r"\n(?=\s*#\s*[A-Z])", "comment_block"),
            (r"\n\n", "paragraph"),
        ]

        split_points = []
        for pattern, split_type in split_patterns:
            for match in re.finditer(pattern, content):
                split_points.append((match.start(), split_type))

        # Sort split points
        split_points.sort(key=lambda x: x[0])

        # Create chunks at split points
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
                        # Still too large, need to split further
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

        # Add remaining content
        if start < len(content):
            sub_content = content[start:].strip()
            if sub_content:
                sub_chunks.append(
                    self._create_embedding_chunk(
                        chunk,
                        sub_content,
                        "remainder",
                    ),
                )

        return sub_chunks if sub_chunks else [chunk]

    def _create_embedding_chunk(
        self,
        parent: CodeChunk,
        content: str,
        chunk_type: str,
    ) -> CodeChunk:
        """Create a chunk optimized for embedding."""
        embedding_chunk = CodeChunk(
            language=parent.language,
            file_path=parent.file_path,
            node_type=f"embedding_{chunk_type}",
            start_line=parent.start_line,  # Would need proper calculation
            end_line=parent.end_line,  # Would need proper calculation
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

    def _ensure_semantic_coherence(
        self,
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
    ) -> list[CodeChunk]:
        """Ensure chunks maintain semantic coherence for embeddings."""
        coherent_chunks = []

        for chunk in chunks:
            # Check if chunk starts or ends mid-statement
            content = chunk.content.strip()

            # Check for incomplete starts
            incomplete_start_patterns = [
                r"^\s*\)",  # Starts with closing paren
                r"^\s*\}",  # Starts with closing brace
                r"^\s*\]",  # Starts with closing bracket
                r"^\s*else",  # Starts with else without if
                r"^\s*elif",  # Starts with elif without if
                r"^\s*except",  # Starts with except without try
                r"^\s*finally",  # Starts with finally without try
            ]

            # Check for incomplete ends
            incomplete_end_patterns = [
                r":\s*$",  # Ends with colon (incomplete block)
                r",\s*$",  # Ends with comma (incomplete list)
                r"\(\s*$",  # Ends with opening paren
                r"\[\s*$",  # Ends with opening bracket
                r"\{\s*$",  # Ends with opening brace
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
                # Try to find better boundaries
                # This is simplified - in practice would need more sophisticated analysis
                coherent_chunks.append(chunk)
            else:
                coherent_chunks.append(chunk)

        return coherent_chunks

    def _calculate_coherence_score(self, chunks: list[CodeChunk]) -> float:
        """Calculate how well chunks maintain semantic unity."""
        if not chunks:
            return 0.0

        scores = []

        for chunk in chunks:
            score = 1.0
            content = chunk.content.strip()

            # Penalize incomplete structures
            if re.search(r":\s*$", content):  # Ends with colon
                score *= 0.8
            if re.search(r"^\s*\)", content):  # Starts with closing paren
                score *= 0.7
            if re.search(
                r"^\s*(else|elif|except|finally)",
                content,
            ):  # Orphaned control flow
                score *= 0.6

            # Reward complete structures
            if re.match(
                r"^(def|class|async def)\s+\w+.*:\s*\n.*\n\s*$",
                content,
                re.DOTALL,
            ):
                score = min(score * 1.2, 1.0)

            # Check for balanced braces/parens
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
                "function": r"\n(?=def\s+\w+)",
                "class": r"\n(?=class\s+\w+)",
                "method": r"\n(?=\s+def\s+\w+)",
                "async_function": r"\n(?=async\s+def\s+\w+)",
                "block_end": r"\n(?=\S)",  # End of indented block
                "import": r"\n(?=(from|import)\s+)",
            },
            "javascript": {
                "function": r"\n(?=function\s+\w+)",
                "arrow_function": r"\n(?=const\s+\w+\s*=\s*\()",
                "class": r"\n(?=class\s+\w+)",
                "method": r"\n(?=\s+\w+\s*\()",
                "block_end": r"\n\}",
                "import": r"\n(?=(import|export)\s+)",
            },
            "java": {
                "class": r"\n(?=(public|private|protected)?\s*class\s+)",
                "method": r"\n(?=(public|private|protected)?\s*\w+\s+\w+\s*\()",
                "block_end": r"\n\}",
                "import": r"\n(?=import\s+)",
            },
        }

    def find_natural_boundaries(self, content: str, language: str) -> list[int]:
        """Find natural boundary points in code."""
        boundaries = set()

        # Get language-specific patterns
        patterns = self.language_patterns.get(language, {})

        # Find matches for each pattern
        for pattern_type, pattern in patterns.items():
            for match in re.finditer(pattern, content):
                boundaries.add(match.start())

        # Always add paragraph boundaries (double newlines) - works for any language
        for match in re.finditer(r"\n\n", content):
            boundaries.add(match.start())

        # Add major comment block boundaries (common patterns)
        for match in re.finditer(r"\n(?=\s*#\s*[A-Z])", content):
            boundaries.add(match.start())

        # Add C-style comment boundaries
        for match in re.finditer(r"\n(?=\s*/\*)", content):
            boundaries.add(match.start())

        # Add docstring boundaries
        for match in re.finditer(r'\n(?=\s*""")', content):
            boundaries.add(match.start())

        # If no boundaries found, add some basic ones
        if not boundaries and len(content) > 100:
            # Add boundaries at regular intervals as last resort
            lines = content.split("\n")
            if len(lines) > 10:
                # Add boundary every 10 lines
                for i in range(10, len(lines), 10):
                    pos = len("\n".join(lines[:i]))
                    boundaries.add(pos)

        return sorted(list(boundaries))

    def score_boundary(self, content: str, position: int, language: str) -> float:
        """Score how good a boundary point is."""
        if position < 0 or position >= len(content):
            return 0.0

        score = 0.5  # Base score

        # Check what comes before and after the boundary
        before = content[:position]
        after = content[position:]

        # Higher score for complete structures before boundary
        if before.strip():
            # Check for balanced braces/parens before boundary
            open_braces = before.count("{") - before.count("}")
            open_parens = before.count("(") - before.count(")")

            if open_braces == 0 and open_parens == 0:
                score += 0.2

            # Check if before ends with complete statement
            if re.search(r"[;}\]]\s*$", before):
                score += 0.1

        # Higher score for clean starts after boundary
        if after.strip():
            # Check for clean function/class start
            if re.match(r"\s*(def|class|function|public|private)", after):
                score += 0.2

            # Check for import statement
            if re.match(r"\s*(import|from|export)", after):
                score += 0.15

            # Check for comment block start
            if re.match(r"\s*#|/\*|//", after):
                score += 0.1

        # Penalize breaking in the middle of strings or comments
        # Simple heuristic: count quotes before position
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
            for j in range(i + 1, min(i + 5, len(chunks))):  # Look ahead up to 5 chunks
                chunk1 = chunks[i]
                chunk2 = chunks[j]

                # Calculate merge score
                score = self._calculate_merge_score(chunk1, chunk2)

                if score > 0.5:  # Only suggest merges with reasonable scores
                    suggestions.append((i, j, score))

        # Sort by score descending
        suggestions.sort(key=lambda x: x[2], reverse=True)

        return suggestions

    def _calculate_merge_score(self, chunk1: CodeChunk, chunk2: CodeChunk) -> float:
        """Calculate score for merging two chunks."""
        score = 0.0

        # Same file
        if chunk1.file_path != chunk2.file_path:
            return 0.0

        # Proximity bonus
        line_distance = chunk2.start_line - chunk1.end_line
        if line_distance == 1:
            score += 0.4  # Adjacent chunks
        elif line_distance <= 5:
            score += 0.2  # Very close
        elif line_distance <= 10:
            score += 0.1  # Close
        else:
            return 0.0  # Too far apart

        # Same parent context
        if chunk1.parent_context == chunk2.parent_context:
            score += 0.2

        # Related node types
        related_types = {
            ("function", "function"),
            ("class", "method"),
            ("class", "constructor"),
            ("import", "import"),
        }

        if (chunk1.node_type, chunk2.node_type) in related_types:
            score += 0.2

        # Cross-references
        if chunk2.chunk_id in chunk1.references or chunk1.chunk_id in chunk2.references:
            score += 0.3

        # Shared dependencies
        shared_deps = set(chunk1.dependencies) & set(chunk2.dependencies)
        if shared_deps:
            score += min(0.2, len(shared_deps) * 0.05)

        return min(score, 1.0)

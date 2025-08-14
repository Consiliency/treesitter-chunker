"""Adaptive chunking strategy that adjusts chunk size based on complexity."""

from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from chunker.analysis import ComplexityAnalyzer, CouplingAnalyzer, SemanticAnalyzer
from chunker.interfaces.base import ChunkingStrategy
from chunker.types import CodeChunk


@dataclass
class AdaptiveMetrics:
    """Metrics used for adaptive chunking decisions."""

    complexity_score: float
    coupling_score: float
    semantic_cohesion: float
    line_count: int
    token_density: float
    nesting_depth: int

    @property
    def overall_score(self) -> float:
        """Calculate overall score for chunk size decisions."""
        return (
            self.complexity_score * 0.3
            + self.coupling_score * 0.2
            + (1.0 - self.semantic_cohesion) * 0.2
            + self.token_density * 0.2
            + self.nesting_depth * 0.1
        )


class AdaptiveChunker(ChunkingStrategy):
    """Dynamically adjusts chunk boundaries based on code complexity.

    Features:
    - Smaller chunks for complex code
    - Larger chunks for simple, cohesive code
    - Respects natural boundaries
    - Balances chunk sizes within constraints
    """

    def __init__(self):
        self.complexity_analyzer = ComplexityAnalyzer()
        self.coupling_analyzer = CouplingAnalyzer()
        self.semantic_analyzer = SemanticAnalyzer()
        self._complex_context_depth = 0
        self.config = {
            "base_chunk_size": 50,
            "min_chunk_size": 10,
            "max_chunk_size": 200,
            "complexity_factor": 0.5,
            "cohesion_factor": 0.3,
            "density_factor": 0.2,
            "high_complexity_threshold": 15.0,
            "low_complexity_threshold": 5.0,
            "high_cohesion_threshold": 0.8,
            "low_cohesion_threshold": 0.4,
            "preserve_boundaries": True,
            "balance_sizes": True,
            "adaptive_aggressiveness": 0.7,
        }
        self.natural_boundaries = {
            "function_definition",
            "method_definition",
            "class_definition",
            "if_statement",
            "for_statement",
            "while_statement",
            "try_statement",
            "switch_statement",
            "match_expression",
            "block_statement",
            "compound_statement",
        }

    @staticmethod
    def can_handle(_file_path: str, _language: str) -> bool:
        """Adaptive chunking can handle any language with AST support."""
        return True

    def chunk(
        self,
        ast: Node,
        source: bytes,
        file_path: str,
        language: str,
    ) -> list[CodeChunk]:
        """Create adaptively-sized chunks based on code complexity."""
        file_metrics = self._analyze_file(ast, source)
        chunks = self._create_adaptive_chunks(
            ast,
            source,
            file_path,
            language,
            file_metrics,
        )
        if self.config["balance_sizes"]:
            chunks = self._balance_chunk_sizes(chunks, source)
        return chunks

    def configure(self, config: dict[str, Any]) -> None:
        """Update configuration settings."""
        self.config.update(config)

    def _analyze_file(self, ast: Node, source: bytes) -> dict[str, Any]:
        """Analyze the entire file to establish baseline metrics."""
        file_complexity = self.complexity_analyzer.calculate_complexity(ast, source)
        file_coupling = self.coupling_analyzer.analyze_coupling(ast, source)
        total_lines = ast.end_point[0] - ast.start_point[0] + 1
        total_tokens = self._count_tokens(ast)
        return {
            "total_lines": total_lines,
            "total_tokens": total_tokens,
            "avg_complexity": file_complexity["score"] / max(1, total_lines / 50),
            "avg_coupling": file_coupling["score"] / max(1, total_lines / 50),
            "complexity_distribution": self._analyze_complexity_distribution(
                ast,
                source,
            ),
        }

    def _analyze_complexity_distribution(
        self,
        ast: Node,
        source: bytes,
    ) -> dict[str, float]:
        """Analyze how complexity is distributed across the file."""
        distribution = {"low": 0, "medium": 0, "high": 0}

        def analyze_node(node: Node):
            if node.type in self.natural_boundaries:
                metrics = self._calculate_node_metrics(node, source)
                if metrics.complexity_score < self.config["low_complexity_threshold"]:
                    distribution["low"] += 1
                elif (
                    metrics.complexity_score > self.config["high_complexity_threshold"]
                ):
                    distribution["high"] += 1
                else:
                    distribution["medium"] += 1
            for child in node.children:
                analyze_node(child)

        analyze_node(ast)
        total = sum(distribution.values()) or 1
        return {k: (v / total) for k, v in distribution.items()}

    def _create_adaptive_chunks(
        self,
        ast: Node,
        source: bytes,
        file_path: str,
        language: str,
        file_metrics: dict[str, Any],
    ) -> list[CodeChunk]:
        """Create chunks with sizes adapted to code complexity."""
        chunks = []
        self._current_file_metrics = file_metrics
        self._adaptive_traverse(
            ast,
            source,
            file_path,
            language,
            file_metrics,
            chunks,
            parent_context="",
            depth=0,
        )
        self._current_file_metrics = None
        return chunks

    def _adaptive_traverse(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        language: str,
        file_metrics: dict[str, Any],
        chunks: list[CodeChunk],
        parent_context: str,
        depth: int,
    ):
        """Traverse AST and create adaptive chunks."""
        metrics = self._calculate_node_metrics(node, source)
        ideal_size = self._calculate_ideal_chunk_size(metrics, file_metrics)
        if self._complex_context_depth > 0:
            ideal_size = min(ideal_size, 4)
        # For complex natural-boundary nodes, bias toward smaller target sizes
        if node.type in self.natural_boundaries and metrics.complexity_score >= 10.0:
            ideal_size = max(self.config["min_chunk_size"], int(ideal_size * 0.5))
        line_count = node.end_point[0] - node.start_point[0] + 1
        should_chunk = self._should_create_chunk(
            node,
            metrics,
            ideal_size,
            line_count,
            depth,
        )
        # Special handling for natural boundaries to enforce desired behavior:
        # - Complex functions/classes: split inside (no single giant chunk)
        # - Simple functions/classes: one chunk, do not emit children chunks
        if node.type in self.natural_boundaries:
            if metrics.complexity_score >= 10.0:
                # Treat as container: traverse children to create smaller chunks
                self._complex_context_depth += 1
                try:
                    for child in node.children:
                        self._adaptive_traverse(
                            child,
                            source,
                            file_path,
                            language,
                            file_metrics,
                            chunks,
                            parent_context,
                            depth + 1,
                        )
                finally:
                    self._complex_context_depth -= 1
                return
            # For simple boundaries, always emit a single chunk and stop
            if True:
                # Emit a single chunk for simple boundary and stop
                chunk = self._create_chunk(
                    node,
                    source,
                    file_path,
                    language,
                    parent_context,
                    metrics,
                )
                chunks.append(chunk)
                return

        if should_chunk:
            chunk = self._create_chunk(
                node,
                source,
                file_path,
                language,
                parent_context,
                metrics,
            )
            chunks.append(chunk)
            parent_context = f"{node.type}: {chunk.metadata.get('name', '')}"
            remaining_size = ideal_size - line_count
            if remaining_size > self.config["min_chunk_size"]:
                return
        accumulated_lines = 0
        current_group = []
        for child in node.children:
            child_lines = child.end_point[0] - child.start_point[0] + 1
            if (
                accumulated_lines + child_lines > ideal_size
                and accumulated_lines > 0
                and self._is_good_split_point(child)
            ):
                if current_group:
                    group_chunk = self._create_group_chunk(
                        current_group,
                        source,
                        file_path,
                        language,
                        parent_context,
                    )
                    if group_chunk:  # Only add if valid
                        chunks.append(group_chunk)
                    else:
                        # If group chunk creation failed, process each node individually
                        for child in current_group:
                            self._adaptive_traverse(
                                child,
                                source,
                                file_path,
                                language,
                                file_metrics,
                                chunks,
                                parent_context,
                                depth + 1,
                            )
                current_group = []
                accumulated_lines = 0
            # Force standalone traversal for large/complex children; otherwise allow grouping
            force_standalone = child_lines > ideal_size * 0.7
            if not force_standalone and self._complex_context_depth > 0:
                force_standalone = child_lines >= 3
            if not force_standalone and child.type in self.natural_boundaries:
                # Inspect child complexity to decide grouping
                child_metrics = self._calculate_node_metrics(child, source)
                if (
                    child_metrics.complexity_score
                    >= self.config["high_complexity_threshold"]
                    or child_lines >= self.config["min_chunk_size"]
                ):
                    force_standalone = True
            # Enhanced boundary preservation: don't group function/class definitions together
            if (
                not force_standalone
                and self.config.get("preserve_boundaries", True)
                and child.type in self.natural_boundaries
                and any(n.type in self.natural_boundaries for n in current_group)
            ):
                force_standalone = True
            if force_standalone:
                if current_group:
                    group_chunk = self._create_group_chunk(
                        current_group,
                        source,
                        file_path,
                        language,
                        parent_context,
                    )
                    if group_chunk:  # Only add if valid
                        chunks.append(group_chunk)
                    else:
                        # If group chunk creation failed, process each node individually
                        for child in current_group:
                            self._adaptive_traverse(
                                child,
                                source,
                                file_path,
                                language,
                                file_metrics,
                                chunks,
                                parent_context,
                                depth + 1,
                            )
                    current_group = []
                    accumulated_lines = 0
                self._adaptive_traverse(
                    child,
                    source,
                    file_path,
                    language,
                    file_metrics,
                    chunks,
                    parent_context,
                    depth + 1,
                )
            else:
                current_group.append(child)
                accumulated_lines += child_lines
        if current_group:
            group_chunk = self._create_group_chunk(
                current_group,
                source,
                file_path,
                language,
                parent_context,
            )
            if group_chunk:  # Only add if valid
                chunks.append(group_chunk)
            else:
                # If group chunk creation failed (e.g., boundary preservation),
                # process each node individually
                for child in current_group:
                    self._adaptive_traverse(
                        child,
                        source,
                        file_path,
                        language,
                        file_metrics,
                        chunks,
                        parent_context,
                        depth + 1,
                    )

    def _calculate_node_metrics(
        self,
        node: Node,
        source: bytes,
    ) -> AdaptiveMetrics:
        """Calculate comprehensive metrics for a node."""
        complexity = self.complexity_analyzer.calculate_complexity(
            node,
            source,
        )
        coupling = self.coupling_analyzer.analyze_coupling(node, source)
        semantics = self.semantic_analyzer.analyze_semantics(node, source)
        line_count = node.end_point[0] - node.start_point[0] + 1
        token_count = self._count_tokens(node)
        token_density = token_count / max(1, line_count)
        return AdaptiveMetrics(
            complexity_score=complexity["score"],
            coupling_score=coupling["score"],
            semantic_cohesion=semantics["cohesion_score"],
            line_count=line_count,
            token_density=token_density,
            nesting_depth=complexity["max_nesting"],
        )

    def _calculate_ideal_chunk_size(
        self,
        metrics: AdaptiveMetrics,
        file_metrics: dict[str, Any],
    ) -> int:
        """Calculate ideal chunk size based on metrics."""
        base_size = self.config["base_chunk_size"]
        complexity_ratio = metrics.complexity_score / max(
            1,
            file_metrics["avg_complexity"],
        )
        complexity_adjustment = (
            1.0 - (complexity_ratio - 1.0) * self.config["complexity_factor"]
        )
        cohesion_adjustment = (
            1.0 + (metrics.semantic_cohesion - 0.5) * self.config["cohesion_factor"]
        )
        density_ratio = metrics.token_density / 10.0
        density_adjustment = 1.0 - (density_ratio - 1.0) * self.config["density_factor"]
        aggressiveness = self.config["adaptive_aggressiveness"]
        total_adjustment = (
            complexity_adjustment * aggressiveness
            + cohesion_adjustment * aggressiveness
            + density_adjustment * aggressiveness
            + (1.0 - aggressiveness) * 3.0
        ) / 3.0
        ideal_size = int(base_size * total_adjustment)
        return max(
            self.config["min_chunk_size"],
            min(self.config["max_chunk_size"], ideal_size),
        )

    def _should_create_chunk(
        self,
        node: Node,
        metrics: AdaptiveMetrics,
        ideal_size: int,
        line_count: int,
        _depth: int,
    ) -> bool:
        """Determine if a node should become a chunk."""
        # Boundary preservation: don't chunk blocks containing multiple function definitions
        if self.config.get("preserve_boundaries", True) and node.type == "block":
            boundary_children = [
                c for c in node.children if c.type in self.natural_boundaries
            ]
            if len(boundary_children) > 1:
                return False

        # Strong bias: complex code should be in smaller chunks
        if metrics.complexity_score >= 10.0:
            # Do not emit very large complex chunks; let traversal/grouping split them
            if line_count > ideal_size:
                return False
            # Prefer emitting when it is already small enough
            if line_count >= max(3, int(ideal_size * 0.4)):
                return True
        if (
            self.config.get(
                "preserve_boundaries",
                True,
            )
            and node.type == "module"
        ):
            return False
        if (
            node.type in self.natural_boundaries
            and line_count >= self.config["min_chunk_size"]
        ):
            return True
        # For simple code, prefer larger chunks
        if metrics.complexity_score < 5.0 and line_count >= ideal_size * 0.85:
            return True
        if line_count >= ideal_size * 0.7:
            return True
        if (
            metrics.complexity_score > self.config["high_complexity_threshold"]
            and line_count >= self.config["min_chunk_size"] // 2
        ):
            return True
        return bool(
            metrics.semantic_cohesion > self.config["high_cohesion_threshold"]
            and line_count >= ideal_size * 0.5,
        )

    def _is_good_split_point(self, node: Node) -> bool:
        """Check if this node is a good point to split chunks."""
        if node.type in self.natural_boundaries:
            return True
        split_preferred = {
            "import_statement",
            "import_from_statement",
            "type_alias",
            "type_definition",
            "comment",
            "decorator_list",
            # Common statement-level split points
            "expression_statement",
            "assignment",
            "augmented_assignment",
            "return_statement",
            "pass_statement",
            "if_statement",
            "elif_clause",
            "else_clause",
            "for_statement",
            "while_statement",
            "try_statement",
            "except_clause",
            "finally_clause",
            "with_statement",
        }
        return node.type in split_preferred

    def _create_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        language: str,
        parent_context: str,
        metrics: AdaptiveMetrics,
    ) -> CodeChunk:
        """Create a chunk with adaptive metadata."""
        content = source[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        chunk = CodeChunk(
            language=language,
            file_path=file_path,
            node_type=node.type,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            byte_start=node.start_byte,
            byte_end=node.end_byte,
            parent_context=parent_context,
            content=content,
        )
        chunk.metadata = {
            "adaptive_metrics": {
                "complexity": metrics.complexity_score,
                "coupling": metrics.coupling_score,
                "cohesion": metrics.semantic_cohesion,
                "density": metrics.token_density,
                "ideal_size": self._calculate_ideal_chunk_size(
                    metrics,
                    getattr(self, "_current_file_metrics", {}),
                ),
            },
            "name": self._extract_name(node),
        }
        return chunk

    def _create_group_chunk(
        self,
        nodes: list[Node],
        source: bytes,
        file_path: str,
        language: str,
        parent_context: str,
    ) -> CodeChunk:
        """Create a chunk from a group of nodes."""
        if not nodes:
            return None

        # Enhanced boundary preservation: don't group multiple natural boundaries
        if self.config.get("preserve_boundaries", True):
            boundary_nodes = [n for n in nodes if n.type in self.natural_boundaries]
            if len(boundary_nodes) > 1:
                # If we have multiple boundary nodes, only create individual chunks
                return None

        first_node = nodes[0]
        last_node = nodes[-1]
        start_byte = first_node.start_byte
        end_byte = last_node.end_byte
        content = source[start_byte:end_byte].decode("utf-8", errors="replace")
        total_complexity = 0
        total_lines = 0
        for node in nodes:
            metrics = self._calculate_node_metrics(node, source)
            total_complexity += metrics.complexity_score
            total_lines += metrics.line_count
        avg_complexity = total_complexity / len(nodes) if nodes else 0
        chunk = CodeChunk(
            language=language,
            file_path=file_path,
            node_type="adaptive_group",
            start_line=first_node.start_point[0] + 1,
            end_line=last_node.end_point[0] + 1,
            byte_start=start_byte,
            byte_end=end_byte,
            parent_context=parent_context,
            content=content,
        )
        chunk.metadata = {
            "group_size": len(nodes),
            "node_types": [n.type for n in nodes],
            "avg_complexity": avg_complexity,
        }
        return chunk

    def _balance_chunk_sizes(
        self,
        chunks: list[CodeChunk],
        source: bytes,
    ) -> list[CodeChunk]:
        """Balance chunk sizes to avoid extreme variations."""
        if not chunks:
            return chunks
        sizes = [(c.end_line - c.start_line + 1) for c in chunks]
        avg_size = sum(sizes) / len(sizes)
        balanced = []
        merged_indices = set()
        for i, chunk in enumerate(chunks):
            if i in merged_indices:
                continue
            size = sizes[i]
            if size > avg_size * 2 and size > self.config["max_chunk_size"] * 0.8:
                split_chunks = self._split_large_chunk(chunk, source, avg_size)
                balanced.extend(split_chunks)
            elif size < avg_size * 0.3 and size < self.config["min_chunk_size"] * 2:
                if i < len(chunks) - 1 and (i + 1) not in merged_indices:
                    next_chunk = chunks[i + 1]
                    next_size = sizes[i + 1]
                    if (
                        next_size < avg_size * 0.5
                        and size + next_size < self.config["max_chunk_size"]
                    ):
                        merged = self._merge_chunks(chunk, next_chunk)
                        balanced.append(merged)
                        merged_indices.add(i + 1)
                    else:
                        balanced.append(chunk)
                else:
                    balanced.append(chunk)
            else:
                balanced.append(chunk)
        return balanced

    @staticmethod
    def _split_large_chunk(
        chunk: CodeChunk,
        _source: bytes,
        _target_size: float,
    ) -> list[CodeChunk]:
        """Split a large chunk into smaller pieces."""
        return [chunk]

    @classmethod
    def _merge_chunks(cls, chunk1: CodeChunk, chunk2: CodeChunk) -> CodeChunk:
        """Merge two adjacent chunks."""
        merged = CodeChunk(
            language=chunk1.language,
            file_path=chunk1.file_path,
            node_type="adaptive_merged",
            start_line=chunk1.start_line,
            end_line=chunk2.end_line,
            byte_start=chunk1.byte_start,
            byte_end=chunk2.byte_end,
            parent_context=chunk1.parent_context,
            content=chunk1.content + "\n\n" + chunk2.content,
        )
        merged.metadata = {
            "merged_from": [
                chunk1.chunk_id,
                chunk2.chunk_id,
            ],
            "original_types": [chunk1.node_type, chunk2.node_type],
        }
        merged.dependencies = list(set(chunk1.dependencies + chunk2.dependencies))
        merged.references = list(set(chunk1.references + chunk2.references))
        return merged

    @staticmethod
    def _count_tokens(node: Node) -> int:
        """Count approximate number of tokens in a node."""
        token_count = 0

        def count(n: Node):
            nonlocal token_count
            if n.type in {"identifier", "string", "number", "operator"}:
                token_count += 1
            for child in n.children:
                count(child)

        count(node)
        return token_count

    @staticmethod
    def _extract_name(node: Node) -> str:
        """Extract name from a node if available."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
        return ""

"""Adaptive chunking strategy that adjusts chunk size based on complexity."""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from tree_sitter import Node

from ..interfaces.base import ChunkingStrategy
from ..types import CodeChunk
from ..analysis import ComplexityAnalyzer, CouplingAnalyzer, SemanticAnalyzer


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
            self.complexity_score * 0.3 +
            self.coupling_score * 0.2 +
            (1.0 - self.semantic_cohesion) * 0.2 +  # Lower cohesion = higher score
            self.token_density * 0.2 +
            self.nesting_depth * 0.1
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
        
        self.config = {
            # Base chunk size parameters
            'base_chunk_size': 50,  # Base number of lines
            'min_chunk_size': 10,
            'max_chunk_size': 200,
            
            # Adaptation factors
            'complexity_factor': 0.5,  # How much complexity affects size
            'cohesion_factor': 0.3,    # How much cohesion affects size
            'density_factor': 0.2,     # How much token density affects size
            
            # Thresholds
            'high_complexity_threshold': 15.0,
            'low_complexity_threshold': 5.0,
            'high_cohesion_threshold': 0.8,
            'low_cohesion_threshold': 0.4,
            
            # Behavior options
            'preserve_boundaries': True,  # Respect natural code boundaries
            'balance_sizes': True,       # Try to balance chunk sizes
            'adaptive_aggressiveness': 0.7,  # 0-1, how aggressive adaptation is
        }
        
        # Natural boundary nodes that we prefer not to split
        self.natural_boundaries = {
            'function_definition', 'method_definition', 'class_definition',
            'if_statement', 'for_statement', 'while_statement',
            'try_statement', 'switch_statement', 'match_expression',
            'block_statement', 'compound_statement',
        }
    
    def can_handle(self, file_path: str, language: str) -> bool:
        """Adaptive chunking can handle any language with AST support."""
        return True
    
    def chunk(self, ast: Node, source: bytes, file_path: str, language: str) -> List[CodeChunk]:
        """Create adaptively-sized chunks based on code complexity."""
        # First pass: Analyze the entire file
        file_metrics = self._analyze_file(ast, source)
        
        # Second pass: Create adaptive chunks
        chunks = self._create_adaptive_chunks(ast, source, file_path, language, file_metrics)
        
        # Third pass: Balance chunk sizes if configured
        if self.config['balance_sizes']:
            chunks = self._balance_chunk_sizes(chunks, source)
        
        return chunks
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Update configuration settings."""
        self.config.update(config)
    
    def _analyze_file(self, ast: Node, source: bytes) -> Dict[str, Any]:
        """Analyze the entire file to establish baseline metrics."""
        # Get overall file metrics
        file_complexity = self.complexity_analyzer.calculate_complexity(ast, source)
        file_coupling = self.coupling_analyzer.analyze_coupling(ast, source)
        
        # Calculate file-level statistics
        total_lines = ast.end_point[0] - ast.start_point[0] + 1
        total_tokens = self._count_tokens(ast)
        
        return {
            'total_lines': total_lines,
            'total_tokens': total_tokens,
            'avg_complexity': file_complexity['score'] / max(1, total_lines / 50),
            'avg_coupling': file_coupling['score'] / max(1, total_lines / 50),
            'complexity_distribution': self._analyze_complexity_distribution(ast, source),
        }
    
    def _analyze_complexity_distribution(self, ast: Node, source: bytes) -> Dict[str, float]:
        """Analyze how complexity is distributed across the file."""
        distribution = {'low': 0, 'medium': 0, 'high': 0}
        
        def analyze_node(node: Node):
            if node.type in self.natural_boundaries:
                metrics = self._calculate_node_metrics(node, source)
                if metrics.complexity_score < self.config['low_complexity_threshold']:
                    distribution['low'] += 1
                elif metrics.complexity_score > self.config['high_complexity_threshold']:
                    distribution['high'] += 1
                else:
                    distribution['medium'] += 1
            
            for child in node.children:
                analyze_node(child)
        
        analyze_node(ast)
        
        total = sum(distribution.values()) or 1
        return {k: v / total for k, v in distribution.items()}
    
    def _create_adaptive_chunks(self, ast: Node, source: bytes, file_path: str,
                               language: str, file_metrics: Dict[str, Any]) -> List[CodeChunk]:
        """Create chunks with sizes adapted to code complexity."""
        chunks = []
        
        # Use a sliding window approach with adaptive boundaries
        self._adaptive_traverse(
            ast, source, file_path, language, file_metrics, chunks, 
            parent_context="", depth=0
        )
        
        return chunks
    
    def _adaptive_traverse(self, node: Node, source: bytes, file_path: str,
                          language: str, file_metrics: Dict[str, Any],
                          chunks: List[CodeChunk], parent_context: str,
                          depth: int):
        """Traverse AST and create adaptive chunks."""
        # Calculate metrics for current node
        metrics = self._calculate_node_metrics(node, source)
        
        # Determine ideal chunk size for this complexity
        ideal_size = self._calculate_ideal_chunk_size(metrics, file_metrics)
        
        # Check if this node should be a chunk
        line_count = node.end_point[0] - node.start_point[0] + 1
        
        should_chunk = self._should_create_chunk(
            node, metrics, ideal_size, line_count, depth
        )
        
        if should_chunk:
            # Create chunk from this node
            chunk = self._create_chunk(
                node, source, file_path, language, parent_context, metrics
            )
            chunks.append(chunk)
            
            # Update parent context for children
            parent_context = f"{node.type}: {chunk.metadata.get('name', '')}"
            
            # Process children based on remaining size budget
            remaining_size = ideal_size - line_count
            if remaining_size > self.config['min_chunk_size']:
                # Node is small enough, include children in same chunk
                return
        
        # Process children
        child_chunks = []
        accumulated_lines = 0
        current_group = []
        
        for child in node.children:
            child_lines = child.end_point[0] - child.start_point[0] + 1
            
            # Check if we should start a new chunk group
            if (accumulated_lines + child_lines > ideal_size and 
                accumulated_lines > 0 and
                self._is_good_split_point(child)):
                
                # Create chunk from accumulated nodes
                if current_group:
                    group_chunk = self._create_group_chunk(
                        current_group, source, file_path, language, parent_context
                    )
                    chunks.append(group_chunk)
                
                # Reset accumulator
                current_group = []
                accumulated_lines = 0
            
            # Add to current group or process separately
            if child_lines > ideal_size * 0.7 or child.type in self.natural_boundaries:
                # Process large or boundary nodes separately
                if current_group:
                    # First, create chunk from current group
                    group_chunk = self._create_group_chunk(
                        current_group, source, file_path, language, parent_context
                    )
                    chunks.append(group_chunk)
                    current_group = []
                    accumulated_lines = 0
                
                # Then process the child
                self._adaptive_traverse(
                    child, source, file_path, language, file_metrics,
                    chunks, parent_context, depth + 1
                )
            else:
                # Accumulate small nodes
                current_group.append(child)
                accumulated_lines += child_lines
        
        # Handle remaining group
        if current_group:
            group_chunk = self._create_group_chunk(
                current_group, source, file_path, language, parent_context
            )
            chunks.append(group_chunk)
    
    def _calculate_node_metrics(self, node: Node, source: bytes) -> AdaptiveMetrics:
        """Calculate comprehensive metrics for a node."""
        # Get analysis results
        complexity = self.complexity_analyzer.calculate_complexity(node, source)
        coupling = self.coupling_analyzer.analyze_coupling(node, source)
        semantics = self.semantic_analyzer.analyze_semantics(node, source)
        
        # Calculate additional metrics
        line_count = node.end_point[0] - node.start_point[0] + 1
        token_count = self._count_tokens(node)
        token_density = token_count / max(1, line_count)
        
        return AdaptiveMetrics(
            complexity_score=complexity['score'],
            coupling_score=coupling['score'],
            semantic_cohesion=semantics['cohesion_score'],
            line_count=line_count,
            token_density=token_density,
            nesting_depth=complexity['max_nesting'],
        )
    
    def _calculate_ideal_chunk_size(self, metrics: AdaptiveMetrics, 
                                   file_metrics: Dict[str, Any]) -> int:
        """Calculate ideal chunk size based on metrics."""
        base_size = self.config['base_chunk_size']
        
        # Adjust based on complexity
        complexity_ratio = metrics.complexity_score / max(1, file_metrics['avg_complexity'])
        complexity_adjustment = 1.0 - (complexity_ratio - 1.0) * self.config['complexity_factor']
        
        # Adjust based on cohesion
        cohesion_adjustment = 1.0 + (metrics.semantic_cohesion - 0.5) * self.config['cohesion_factor']
        
        # Adjust based on density
        density_ratio = metrics.token_density / 10.0  # Assume 10 tokens/line as normal
        density_adjustment = 1.0 - (density_ratio - 1.0) * self.config['density_factor']
        
        # Apply adjustments with aggressiveness factor
        aggressiveness = self.config['adaptive_aggressiveness']
        total_adjustment = (
            complexity_adjustment * aggressiveness +
            cohesion_adjustment * aggressiveness +
            density_adjustment * aggressiveness +
            (1.0 - aggressiveness) * 3.0  # Baseline
        ) / 3.0
        
        # Calculate final size
        ideal_size = int(base_size * total_adjustment)
        
        # Clamp to configured bounds
        return max(
            self.config['min_chunk_size'],
            min(self.config['max_chunk_size'], ideal_size)
        )
    
    def _should_create_chunk(self, node: Node, metrics: AdaptiveMetrics,
                            ideal_size: int, line_count: int, depth: int) -> bool:
        """Determine if a node should become a chunk."""
        # Always chunk major boundaries
        if node.type in self.natural_boundaries:
            if line_count >= self.config['min_chunk_size']:
                return True
        
        # Check size relative to ideal
        if line_count >= ideal_size * 0.7:
            return True
        
        # High complexity nodes should be chunked even if small
        if metrics.complexity_score > self.config['high_complexity_threshold']:
            if line_count >= self.config['min_chunk_size'] // 2:
                return True
        
        # Very cohesive nodes can be larger
        if metrics.semantic_cohesion > self.config['high_cohesion_threshold']:
            if line_count >= ideal_size * 0.5:
                return True
        
        return False
    
    def _is_good_split_point(self, node: Node) -> bool:
        """Check if this node is a good point to split chunks."""
        # Prefer splitting at natural boundaries
        if node.type in self.natural_boundaries:
            return True
        
        # Also good to split at import groups, type definitions, etc.
        split_preferred = {
            'import_statement', 'import_from_statement',
            'type_alias', 'type_definition',
            'comment', 'decorator_list',
        }
        
        return node.type in split_preferred
    
    def _create_chunk(self, node: Node, source: bytes, file_path: str,
                     language: str, parent_context: str,
                     metrics: AdaptiveMetrics) -> CodeChunk:
        """Create a chunk with adaptive metadata."""
        content = source[node.start_byte:node.end_byte].decode('utf-8', errors='replace')
        
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
        
        # Add adaptive metadata
        chunk.metadata = {
            'adaptive_metrics': {
                'complexity': metrics.complexity_score,
                'coupling': metrics.coupling_score,
                'cohesion': metrics.semantic_cohesion,
                'density': metrics.token_density,
                'ideal_size': self._calculate_ideal_chunk_size(metrics, {}),
            },
            'name': self._extract_name(node),
        }
        
        return chunk
    
    def _create_group_chunk(self, nodes: List[Node], source: bytes,
                           file_path: str, language: str,
                           parent_context: str) -> CodeChunk:
        """Create a chunk from a group of nodes."""
        if not nodes:
            return None
        
        # Calculate combined metrics
        first_node = nodes[0]
        last_node = nodes[-1]
        
        # Extract content including gaps between nodes
        start_byte = first_node.start_byte
        end_byte = last_node.end_byte
        content = source[start_byte:end_byte].decode('utf-8', errors='replace')
        
        # Calculate average metrics
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
            node_type='adaptive_group',
            start_line=first_node.start_point[0] + 1,
            end_line=last_node.end_point[0] + 1,
            byte_start=start_byte,
            byte_end=end_byte,
            parent_context=parent_context,
            content=content,
        )
        
        chunk.metadata = {
            'group_size': len(nodes),
            'node_types': [n.type for n in nodes],
            'avg_complexity': avg_complexity,
        }
        
        return chunk
    
    def _balance_chunk_sizes(self, chunks: List[CodeChunk], source: bytes) -> List[CodeChunk]:
        """Balance chunk sizes to avoid extreme variations."""
        if not chunks:
            return chunks
        
        # Calculate size statistics
        sizes = [c.end_line - c.start_line + 1 for c in chunks]
        avg_size = sum(sizes) / len(sizes)
        
        # Identify outliers
        balanced = []
        for i, chunk in enumerate(chunks):
            size = sizes[i]
            
            # Split very large chunks
            if size > avg_size * 2 and size > self.config['max_chunk_size'] * 0.8:
                split_chunks = self._split_large_chunk(chunk, source, avg_size)
                balanced.extend(split_chunks)
            
            # Consider merging very small chunks
            elif size < avg_size * 0.3 and size < self.config['min_chunk_size'] * 2:
                # Look for adjacent small chunks to merge
                if i < len(chunks) - 1:
                    next_chunk = chunks[i + 1]
                    next_size = sizes[i + 1]
                    
                    if (next_size < avg_size * 0.5 and 
                        size + next_size < self.config['max_chunk_size']):
                        # Merge with next chunk
                        merged = self._merge_chunks(chunk, next_chunk)
                        balanced.append(merged)
                        # Skip the next chunk
                        chunks[i + 1] = None
                    else:
                        balanced.append(chunk)
                else:
                    balanced.append(chunk)
            else:
                if chunk is not None:  # Skip merged chunks
                    balanced.append(chunk)
        
        return [c for c in balanced if c is not None]
    
    def _split_large_chunk(self, chunk: CodeChunk, source: bytes,
                          target_size: float) -> List[CodeChunk]:
        """Split a large chunk into smaller pieces."""
        # For now, just return the original chunk
        # A more sophisticated implementation would analyze the chunk content
        # and find good split points
        return [chunk]
    
    def _merge_chunks(self, chunk1: CodeChunk, chunk2: CodeChunk) -> CodeChunk:
        """Merge two adjacent chunks."""
        # Create merged chunk
        merged = CodeChunk(
            language=chunk1.language,
            file_path=chunk1.file_path,
            node_type='adaptive_merged',
            start_line=chunk1.start_line,
            end_line=chunk2.end_line,
            byte_start=chunk1.byte_start,
            byte_end=chunk2.byte_end,
            parent_context=chunk1.parent_context,
            content=chunk1.content + "\n\n" + chunk2.content,
        )
        
        # Merge metadata
        merged.metadata = {
            'merged_from': [chunk1.chunk_id, chunk2.chunk_id],
            'original_types': [chunk1.node_type, chunk2.node_type],
        }
        
        # Merge dependencies and references
        merged.dependencies = list(set(chunk1.dependencies + chunk2.dependencies))
        merged.references = list(set(chunk1.references + chunk2.references))
        
        return merged
    
    def _count_tokens(self, node: Node) -> int:
        """Count approximate number of tokens in a node."""
        # Simple approximation: count identifiers, literals, and operators
        token_count = 0
        
        def count(n: Node):
            nonlocal token_count
            if n.type in ['identifier', 'string', 'number', 'operator']:
                token_count += 1
            for child in n.children:
                count(child)
        
        count(node)
        return token_count
    
    def _extract_name(self, node: Node) -> str:
        """Extract name from a node if available."""
        for child in node.children:
            if child.type == 'identifier':
                return child.text.decode()
        return ""
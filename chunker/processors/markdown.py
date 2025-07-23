"""Markdown processor for structure-aware chunking.

This processor handles Markdown files with special consideration for:
- Headers as natural boundaries
- Code blocks (never split)
- Tables (never split)
- Lists (preserve continuity)
- Front matter (YAML/TOML)
- Nested structures (blockquotes, nested lists)
"""

import re
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
import logging

from . import SpecializedProcessor, ProcessorConfig
from ..types import CodeChunk

logger = logging.getLogger(__name__)


@dataclass
class MarkdownElement:
    """Represents a structural element in Markdown."""
    type: str  # header, code_block, table, list, paragraph, etc.
    level: int  # For headers: 1-6, for lists: nesting level
    start: int  # Start position in content
    end: int    # End position in content
    content: str  # The actual content
    metadata: Dict[str, Any] = field(default_factory=dict)


class MarkdownProcessor(SpecializedProcessor):
    """Specialized processor for Markdown files.
    
    This processor understands Markdown structure and chunks content
    intelligently, preserving document structure and readability.
    """
    
    # Regex patterns for Markdown elements
    PATTERNS = {
        'front_matter': re.compile(r'^---\n(.*?)\n---\n', re.DOTALL | re.MULTILINE),
        'header': re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE),
        'code_block': re.compile(r'^```(?:\w+)?\n(.*?)\n```$', re.DOTALL | re.MULTILINE),
        'table': re.compile(r'^\|(.+)\|\n\|(?:-+\|)+\n(?:\|.+\|\n)*', re.MULTILINE),
        'list_item': re.compile(r'^(\s*)([-*+]|\d+\.)\s+(.+)$', re.MULTILINE),
        'blockquote': re.compile(r'^(>+)\s+(.+)$', re.MULTILINE),
        'horizontal_rule': re.compile(r'^(?:---+|___+|\*\*\*+)$', re.MULTILINE),
        'link_reference': re.compile(r'^\[([^\]]+)\]:\s+(.+)$', re.MULTILINE),
    }
    
    # Elements that should never be split
    ATOMIC_ELEMENTS = {'code_block', 'table', 'front_matter'}
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """Initialize Markdown processor.
        
        Args:
            config: Processor configuration
        """
        super().__init__(config)
        self.elements: List[MarkdownElement] = []
        
    def can_handle(self, file_path: str, content: Optional[str] = None) -> bool:
        """Check if this processor can handle the file.
        
        Args:
            file_path: Path to the file
            content: Optional file content for detection
            
        Returns:
            True if this is a Markdown file
        """
        # Convert to string if Path object
        file_path_str = str(file_path)
        
        # Check file extension
        if file_path_str.endswith(('.md', '.markdown', '.mdown', '.mkd')):
            return True
            
        # Check for Markdown-like content patterns if content provided
        if content and any(pattern.search(content) for pattern in [
            self.PATTERNS['header'],
            self.PATTERNS['code_block'],
            self.PATTERNS['list_item']
        ]):
            return True
            
        return False
    
    def can_process(self, file_path: str, content: str) -> bool:
        """Alias for can_handle to maintain compatibility."""
        return self.can_handle(file_path, content)
        
    def process(self, content: str, file_path: str) -> List[CodeChunk]:
        """Process Markdown content into chunks.
        
        Args:
            content: Markdown content to process
            file_path: Path to the source file
            
        Returns:
            List of code chunks
        """
        # Extract structure
        structure = self.extract_structure(content)
        
        # Find boundaries
        boundaries = self.find_boundaries(content)
        
        # Create chunks based on boundaries
        chunks = self._create_chunks(content, boundaries, file_path)
        
        # Apply overlap if configured
        # Check if we have overlap configuration
        overlap_size = getattr(self.config, 'overlap_size', 0)
        if overlap_size > 0:
            chunks = self._apply_overlap(chunks, content)
            
        return chunks
        
    def extract_structure(self, content: str) -> Dict[str, Any]:
        """Extract structural information from Markdown.
        
        Args:
            content: Markdown content
            
        Returns:
            Dictionary with structural information
        """
        self.elements = []
        structure = {
            'headers': [],
            'code_blocks': [],
            'tables': [],
            'lists': [],
            'front_matter': None,
            'toc': []  # Table of contents structure
        }
        
        # Extract front matter first (if present)
        front_matter_match = self.PATTERNS['front_matter'].search(content)
        if front_matter_match:
            element = MarkdownElement(
                type='front_matter',
                level=0,
                start=front_matter_match.start(),
                end=front_matter_match.end(),
                content=front_matter_match.group(0),
                metadata={'raw': front_matter_match.group(1)}
            )
            self.elements.append(element)
            structure['front_matter'] = element
            
        # Extract headers and build TOC
        for match in self.PATTERNS['header'].finditer(content):
            level = len(match.group(1))
            element = MarkdownElement(
                type='header',
                level=level,
                start=match.start(),
                end=match.end(),
                content=match.group(0),
                metadata={'title': match.group(2).strip()}
            )
            self.elements.append(element)
            structure['headers'].append(element)
            
            # Add to TOC
            structure['toc'].append({
                'level': level,
                'title': match.group(2).strip(),
                'position': match.start()
            })
            
        # Extract code blocks
        for match in self.PATTERNS['code_block'].finditer(content):
            element = MarkdownElement(
                type='code_block',
                level=0,
                start=match.start(),
                end=match.end(),
                content=match.group(0),
                metadata={'code': match.group(1)}
            )
            self.elements.append(element)
            structure['code_blocks'].append(element)
            
        # Extract tables
        for match in self.PATTERNS['table'].finditer(content):
            element = MarkdownElement(
                type='table',
                level=0,
                start=match.start(),
                end=match.end(),
                content=match.group(0)
            )
            self.elements.append(element)
            structure['tables'].append(element)
            
        # Extract lists (with nesting levels)
        list_stack = []
        for match in self.PATTERNS['list_item'].finditer(content):
            indent = len(match.group(1))
            level = indent // 2 + 1  # Approximate nesting level
            
            element = MarkdownElement(
                type='list_item',
                level=level,
                start=match.start(),
                end=match.end(),
                content=match.group(0),
                metadata={
                    'marker': match.group(2),
                    'text': match.group(3)
                }
            )
            self.elements.append(element)
            structure['lists'].append(element)
            
        # Sort elements by position
        self.elements.sort(key=lambda e: e.start)
        
        return structure
        
    def find_boundaries(self, content: str) -> List[Tuple[int, int, str]]:
        """Find natural chunk boundaries in Markdown.
        
        Args:
            content: Markdown content
            
        Returns:
            List of (start, end, boundary_type) tuples
        """
        boundaries = []
        
        # First, identify all atomic elements that cannot be split
        atomic_regions = []
        for element in self.elements:
            if element.type in self.ATOMIC_ELEMENTS:
                atomic_regions.append((element.start, element.end))
                
        # Merge overlapping atomic regions
        atomic_regions = self._merge_overlapping_regions(atomic_regions)
        
        # Headers are natural boundaries (except within atomic regions)
        header_positions = []
        for element in self.elements:
            if element.type == 'header':
                # Check if header is within an atomic region
                in_atomic = any(
                    start <= element.start < end 
                    for start, end in atomic_regions
                )
                if not in_atomic:
                    header_positions.append(element.start)
                    
        # Double newlines are paragraph boundaries
        paragraph_boundaries = [
            m.start() for m in re.finditer(r'\n\n+', content)
        ]
        
        # Combine all boundary positions
        all_boundaries = sorted(set(header_positions + paragraph_boundaries + [0, len(content)]))
        
        # Create boundary segments, respecting atomic regions
        for i in range(len(all_boundaries) - 1):
            start = all_boundaries[i]
            end = all_boundaries[i + 1]
            
            # Determine boundary type
            boundary_type = 'paragraph'
            for element in self.elements:
                if element.start == start and element.type == 'header':
                    boundary_type = f'header_{element.level}'
                    break
                    
            # Check if this segment intersects with atomic regions
            segments = self._split_by_atomic_regions(start, end, atomic_regions)
            
            for seg_start, seg_end, is_atomic in segments:
                if is_atomic:
                    # Find the type of atomic element
                    for element in self.elements:
                        if element.type in self.ATOMIC_ELEMENTS and \
                           element.start <= seg_start < element.end:
                            boundary_type = element.type
                            break
                            
                boundaries.append((seg_start, seg_end, boundary_type))
                
        return boundaries
        
    def _merge_overlapping_regions(self, regions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Merge overlapping regions.
        
        Args:
            regions: List of (start, end) tuples
            
        Returns:
            Merged list of non-overlapping regions
        """
        if not regions:
            return []
            
        sorted_regions = sorted(regions)
        merged = [sorted_regions[0]]
        
        for start, end in sorted_regions[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                # Overlapping, merge
                merged[-1] = (last_start, max(last_end, end))
            else:
                # Non-overlapping, add new
                merged.append((start, end))
                
        return merged
        
    def _split_by_atomic_regions(
        self, 
        start: int, 
        end: int, 
        atomic_regions: List[Tuple[int, int]]
    ) -> List[Tuple[int, int, bool]]:
        """Split a region by atomic regions.
        
        Args:
            start: Start position
            end: End position
            atomic_regions: List of atomic (start, end) regions
            
        Returns:
            List of (start, end, is_atomic) tuples
        """
        segments = []
        current = start
        
        for atomic_start, atomic_end in atomic_regions:
            if atomic_end <= start or atomic_start >= end:
                # No intersection
                continue
                
            if atomic_start > current:
                # Add non-atomic segment before this atomic region
                segments.append((current, atomic_start, False))
                
            # Add atomic segment
            seg_start = max(atomic_start, start)
            seg_end = min(atomic_end, end)
            segments.append((seg_start, seg_end, True))
            current = seg_end
            
        # Add final non-atomic segment if needed
        if current < end:
            segments.append((current, end, False))
            
        # If no atomic regions intersected, return the whole segment
        if not segments:
            segments = [(start, end, False)]
            
        return segments
        
    def _create_chunks(
        self, 
        content: str, 
        boundaries: List[Tuple[int, int, str]], 
        file_path: str
    ) -> List[CodeChunk]:
        """Create chunks from boundaries.
        
        Args:
            content: Original content
            boundaries: List of boundary segments
            file_path: Source file path
            
        Returns:
            List of code chunks
        """
        chunks = []
        current_chunk_segments = []
        current_size = 0
        
        for start, end, boundary_type in boundaries:
            segment_content = content[start:end]
            segment_size = len(segment_content.split())  # Word count as proxy for tokens
            
            # Check if this is an atomic segment
            is_atomic = boundary_type in self.ATOMIC_ELEMENTS
            
            # Handle atomic elements specially - they should always be in their own chunk
            if is_atomic:
                # First, save any previous segments as a chunk
                if current_chunk_segments:
                    chunk = self._create_chunk_from_segments(
                        current_chunk_segments, content, file_path
                    )
                    if chunk and self.validate_chunk(chunk):
                        chunks.append(chunk)
                
                # Create chunk for atomic element
                chunk = self._create_chunk_from_segments(
                    [(start, end, boundary_type)], content, file_path
                )
                if chunk:
                    # For atomic elements, skip size validation since they must be kept intact
                    chunks.append(chunk)
                else:
                    logger.warning(f"Failed to create chunk for atomic element: {boundary_type}")
                    
                # Reset for next chunk
                current_chunk_segments = []
                current_size = 0
            
            # If adding this segment would exceed max size and we have content
            elif current_size + segment_size > self.config.chunk_size and current_chunk_segments:
                # Create chunk from current segments
                chunk = self._create_chunk_from_segments(
                    current_chunk_segments, content, file_path
                )
                if chunk and self.validate_chunk(chunk):
                    chunks.append(chunk)
                    
                # Start new chunk
                current_chunk_segments = [(start, end, boundary_type)]
                current_size = segment_size
            else:
                # Add to current chunk
                current_chunk_segments.append((start, end, boundary_type))
                current_size += segment_size
                
        # Handle remaining segments
        if current_chunk_segments:
            chunk = self._create_chunk_from_segments(
                current_chunk_segments, content, file_path
            )
            if chunk and self.validate_chunk(chunk):
                chunks.append(chunk)
                
        return chunks
        
    def _create_chunk_from_segments(
        self,
        segments: List[Tuple[int, int, str]],
        content: str,
        file_path: str
    ) -> Optional[CodeChunk]:
        """Create a chunk from segment list.
        
        Args:
            segments: List of (start, end, type) tuples
            content: Original content
            file_path: Source file path
            
        Returns:
            CodeChunk or None if segments are empty
        """
        if not segments:
            return None
            
        # Get overall start/end
        start = segments[0][0]
        end = segments[-1][1]
        
        # Extract content
        chunk_content = content[start:end]
        
        # Count lines
        start_line = content[:start].count('\n') + 1
        end_line = content[:end].count('\n') + 1
        
        # Determine chunk type based on dominant segment type
        segment_types = [seg[2] for seg in segments]
        chunk_type = self._determine_chunk_type(segment_types)
        
        # Extract metadata
        metadata = {
            'segment_count': len(segments),
            'segment_types': list(set(segment_types)),
            'dominant_type': chunk_type
        }
        
        # Add header context if chunk starts with header
        if segments[0][2].startswith('header_'):
            for element in self.elements:
                if element.type == 'header' and element.start == segments[0][0]:
                    metadata['header'] = element.metadata['title']
                    metadata['header_level'] = element.level
                    break
                    
        return CodeChunk(
            content=chunk_content,
            start_line=start_line,
            end_line=end_line,
            node_type=chunk_type,  # Using node_type instead of chunk_type
            language='markdown',
            file_path=file_path,
            byte_start=start,
            byte_end=end,
            parent_context='',  # No parent context for markdown chunks
            metadata={
                **metadata,
                'tokens': len(chunk_content.split())  # Add token count to metadata
            }
        )
        
    def _determine_chunk_type(self, segment_types: List[str]) -> str:
        """Determine overall chunk type from segment types.
        
        Args:
            segment_types: List of segment type strings
            
        Returns:
            Overall chunk type
        """
        # Priority order for chunk types
        priority = {
            'code_block': 1,
            'table': 2,
            'front_matter': 3,
        }
        
        # Check for high-priority types
        for seg_type in segment_types:
            if seg_type in priority:
                return seg_type
                
        # Check for headers
        header_types = [t for t in segment_types if t.startswith('header_')]
        if header_types:
            # Return the highest level header
            levels = [int(t.split('_')[1]) for t in header_types]
            return f'section_h{min(levels)}'
            
        # Default to documentation
        return 'documentation'
        
    def _apply_overlap(self, chunks: List[CodeChunk], content: str) -> List[CodeChunk]:
        """Apply overlap between chunks for context preservation.
        
        Args:
            chunks: List of chunks
            content: Original content
            
        Returns:
            List of chunks with overlap applied
        """
        if len(chunks) <= 1:
            return chunks
            
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            new_chunk = chunk
            
            if i > 0:
                # Add overlap from previous chunk
                prev_chunk = chunks[i - 1]
                overlap_content = self._extract_overlap(
                    prev_chunk.content, 
                    getattr(self.config, 'overlap_size', 0),
                    from_end=True
                )
                
                if overlap_content:
                    # Prepend overlap with separator
                    new_content = f"{overlap_content}\n[...]\n{chunk.content}"
                    new_chunk = CodeChunk(
                        content=new_content,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        node_type=chunk.node_type,
                        language=chunk.language,
                        file_path=chunk.file_path,
                        byte_start=chunk.byte_start,
                        byte_end=chunk.byte_end,
                        parent_context=chunk.parent_context,
                        metadata={
                            **chunk.metadata,
                            'has_overlap': True,
                            'overlap_tokens': len(overlap_content.split()),
                            'tokens': len(new_content.split())
                        }
                    )
                    
            overlapped_chunks.append(new_chunk)
            
        return overlapped_chunks
        
    def _extract_overlap(self, content: str, overlap_size: int, from_end: bool = True) -> str:
        """Extract overlap content from chunk.
        
        Args:
            content: Chunk content
            overlap_size: Number of tokens to overlap
            from_end: Extract from end (True) or beginning (False)
            
        Returns:
            Overlap content
        """
        words = content.split()
        
        if len(words) <= overlap_size:
            return content
            
        if from_end:
            overlap_words = words[-overlap_size:]
        else:
            overlap_words = words[:overlap_size]
            
        return ' '.join(overlap_words)
        
    def validate_chunk(self, chunk: CodeChunk) -> bool:
        """Validate chunk quality.
        
        Args:
            chunk: Chunk to validate
            
        Returns:
            True if valid
        """
        # Basic validation from parent
        # Basic validation - chunk should have content
        if not chunk.content.strip():
            return False
            
        # Markdown-specific validation
        content = chunk.content.strip()
        
        # Don't create chunks that are just whitespace or formatting
        if not content or content in ['---', '```', '|||']:
            return False
            
        # Ensure atomic elements are complete
        if chunk.node_type in self.ATOMIC_ELEMENTS:
            if chunk.node_type == 'code_block':
                # Must have opening and closing ```
                if not (content.startswith('```') and content.endswith('```')):
                    logger.warning(f"Invalid code block chunk: missing delimiters")
                    logger.debug(f"Content starts with: {content[:20]}")
                    logger.debug(f"Content ends with: {content[-20:]}")
                    return False
            elif chunk.node_type == 'table':
                # Must have header row and separator
                lines = content.split('\n')
                if len(lines) < 2 or '|' not in lines[0] or '|' not in lines[1]:
                    logger.warning(f"Invalid table chunk: missing structure")
                    return False
                    
        return True
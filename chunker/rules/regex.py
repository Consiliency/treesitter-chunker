"""Regex-based chunking rules for pattern matching."""

from typing import Optional, List, Pattern, Dict, Any
import re

from tree_sitter import Node
from ..types import CodeChunk
from ..interfaces.rules import RegexRule, RuleMatch
from .custom import BaseRegexRule


class RegionMarkerRule(BaseRegexRule):
    """Extract regions marked with start/end comments like #region/#endregion."""
    
    def __init__(self, start_marker: str = "region", end_marker: str = "endregion", 
                 priority: int = 75):
        # Build pattern to match content between region markers
        # Support various comment styles
        pattern = rf'(?:#|//|/\*)\s*{start_marker}\s*(.*?)\n([\s\S]*?)(?:#|//|/\*)\s*{end_marker}'
        
        super().__init__(
            name="region_markers",
            description=f"Extract regions between {start_marker} and {end_marker} markers",
            pattern=pattern,
            priority=priority,
            cross_boundaries=True,
            multiline=True
        )
        self.start_marker = start_marker
        self.end_marker = end_marker
    
    def extract_chunk(self, node: Node, source: bytes, file_path: str) -> Optional[CodeChunk]:
        """Override to include region name in chunk metadata."""
        chunk = super().extract_chunk(node, source, file_path)
        if chunk:
            # Try to extract region name from the match
            text = source[node.start_byte:node.end_byte].decode('utf-8', errors='replace')
            match = self._pattern.search(text)
            if match and match.group(1):
                chunk.node_type = f"region_{match.group(1).strip().replace(' ', '_')}"
        return chunk


class PatternBoundaryRule(BaseRegexRule):
    """Extract chunks based on custom regex patterns for boundaries."""
    
    def __init__(self, name: str, pattern: str, description: str = None,
                 priority: int = 50, extract_match_only: bool = False):
        """
        Initialize pattern boundary rule.
        
        Args:
            name: Rule name
            pattern: Regex pattern for boundaries
            description: Rule description
            priority: Rule priority
            extract_match_only: If True, extract only the match; if False, extract between matches
        """
        super().__init__(
            name=name,
            description=description or f"Extract chunks based on pattern: {pattern}",
            pattern=pattern,
            priority=priority,
            cross_boundaries=True,
            multiline=True
        )
        self.extract_match_only = extract_match_only
    
    def find_all_matches(self, source: bytes, file_path: str) -> List[RuleMatch]:
        """Find all pattern matches or regions between patterns."""
        if self.extract_match_only:
            return super().find_all_matches(source, file_path)
        
        # Extract regions between pattern matches
        matches = []
        text = source.decode('utf-8', errors='replace')
        pattern_matches = list(self._pattern.finditer(text))
        
        if not pattern_matches:
            return matches
        
        # Create chunks between consecutive matches
        for i in range(len(pattern_matches) - 1):
            start_match = pattern_matches[i]
            end_match = pattern_matches[i + 1]
            
            # Region starts after first match
            start_pos = start_match.end()
            end_pos = end_match.start()
            
            if start_pos < end_pos:
                start_byte = len(text[:start_pos].encode('utf-8'))
                end_byte = len(text[:end_pos].encode('utf-8'))
                
                lines_before = text[:start_pos].count('\n')
                start_col = start_pos - text.rfind('\n', 0, start_pos) - 1
                
                lines_in_region = text[start_pos:end_pos].count('\n')
                end_col = end_pos - text.rfind('\n', 0, end_pos) - 1
                
                matches.append(RuleMatch(
                    rule_name=self._name,
                    start_byte=start_byte,
                    end_byte=end_byte,
                    start_point=(lines_before, start_col),
                    end_point=(lines_before + lines_in_region, end_col),
                    metadata={
                        'region_content': text[start_pos:end_pos],
                        'start_marker': start_match.group(0),
                        'end_marker': end_match.group(0)
                    }
                ))
        
        return matches


class AnnotationRule(BaseRegexRule):
    """Extract code sections marked with specific annotations."""
    
    def __init__(self, annotation_pattern: str = r'@chunk(?:\s+(\w+))?',
                 priority: int = 65):
        """
        Initialize annotation rule.
        
        Args:
            annotation_pattern: Pattern for annotations (default: @chunk)
            priority: Rule priority
        """
        # Match annotation and the following code block
        full_pattern = rf'{annotation_pattern}\s*\n((?:(?!{annotation_pattern})[\s\S])*?)(?=\n\s*(?:{annotation_pattern}|$))'
        
        super().__init__(
            name="annotation_chunks",
            description="Extract code marked with chunk annotations",
            pattern=full_pattern,
            priority=priority,
            cross_boundaries=True,
            multiline=True
        )
        self.annotation_pattern = annotation_pattern


class FoldingMarkerRule(BaseRegexRule):
    """Extract sections based on editor folding markers."""
    
    def __init__(self, priority: int = 45):
        """Initialize folding marker rule."""
        # Common folding markers: {{{ }}} or <editor-fold> </editor-fold>
        pattern = r'(?:(?://|#)\s*(?:\{\{\{|<editor-fold(?:\s+[^>]*)?>).*?\n)([\s\S]*?)(?:(?://|#)\s*(?:\}\}\}|</editor-fold>))'
        
        super().__init__(
            name="folding_markers",
            description="Extract code sections marked with editor folding markers",
            pattern=pattern,
            priority=priority,
            cross_boundaries=True,
            multiline=True
        )


class SeparatorLineRule(BaseRegexRule):
    """Extract chunks separated by specific line patterns."""
    
    def __init__(self, separator_pattern: str = r'^-{3,}$|^={3,}$|^#{3,}$',
                 min_lines: int = 1, priority: int = 30):
        """
        Initialize separator line rule.
        
        Args:
            separator_pattern: Pattern for separator lines
            min_lines: Minimum lines in chunk to extract
            priority: Rule priority
        """
        super().__init__(
            name="separator_chunks",
            description="Extract chunks separated by divider lines",
            pattern=separator_pattern,
            priority=priority,
            cross_boundaries=True,
            multiline=True
        )
        self.min_lines = min_lines
        self.extract_match_only = False  # We want content between separators
    
    def find_all_matches(self, source: bytes, file_path: str) -> List[RuleMatch]:
        """Find regions between separator lines."""
        matches = []
        text = source.decode('utf-8', errors='replace')
        lines = text.split('\n')
        
        separator_indices = []
        for i, line in enumerate(lines):
            if self._pattern.match(line.strip()):
                separator_indices.append(i)
        
        if not separator_indices:
            return matches
        
        # Add implicit separators at start and end
        if separator_indices[0] != 0:
            separator_indices.insert(0, -1)
        if separator_indices[-1] != len(lines) - 1:
            separator_indices.append(len(lines))
        
        # Extract chunks between separators
        for i in range(len(separator_indices) - 1):
            start_line = separator_indices[i] + 1
            end_line = separator_indices[i + 1]
            
            # Check minimum lines requirement
            if end_line - start_line < self.min_lines:
                continue
            
            # Calculate byte positions
            start_byte = sum(len(line) + 1 for line in lines[:start_line])
            end_byte = sum(len(line) + 1 for line in lines[:end_line])
            
            # Adjust for last line not having newline
            if end_line == len(lines):
                end_byte -= 1
            
            content = '\n'.join(lines[start_line:end_line])
            
            matches.append(RuleMatch(
                rule_name=self._name,
                start_byte=start_byte,
                end_byte=end_byte,
                start_point=(start_line, 0),
                end_point=(end_line - 1, len(lines[end_line - 1]) if end_line > 0 else 0),
                metadata={
                    'content': content,
                    'line_count': end_line - start_line
                }
            ))
        
        return matches


def create_custom_regex_rule(name: str, pattern: str, **kwargs) -> BaseRegexRule:
    """
    Factory function to create custom regex rules.
    
    Args:
        name: Rule name
        pattern: Regex pattern
        **kwargs: Additional arguments for BaseRegexRule
        
    Returns:
        Custom regex rule instance
    """
    return BaseRegexRule(
        name=name,
        description=kwargs.get('description', f'Custom regex rule: {name}'),
        pattern=pattern,
        priority=kwargs.get('priority', 50),
        cross_boundaries=kwargs.get('cross_boundaries', True),
        multiline=kwargs.get('multiline', True)
    )
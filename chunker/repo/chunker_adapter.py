"""Adapter to provide Chunker interface for repo processor."""

from pathlib import Path
import tempfile
from typing import List

from ..chunker import chunk_file
from ..parser import get_parser
from ..types import CodeChunk


class Chunker:
    """Adapter class to provide the expected Chunker interface."""
    
    def chunk(self, content: str, language: str) -> List[CodeChunk]:
        """Chunk content by writing to temp file and using chunk_file."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False) as tf:
            tf.write(content)
            temp_path = Path(tf.name)
        
        try:
            # Get parser and chunk the file
            parser = get_parser(language)
            chunks = chunk_file(temp_path, parser)
            return chunks
        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)
"""
Support for Python language.
"""

from typing import Set
from .base import LanguageConfig, ChunkRule


class PythonConfig(LanguageConfig):
    """Language configuration for Python."""
    
    @property
    def language_id(self) -> str:
        return "python"
    
    @property
    def chunk_types(self) -> Set[str]:
        """Python-specific chunk types."""
        return {
            # Functions and methods  
            "function_definition",  # includes async functions
            
            # Classes
            "class_definition",
            
            # Decorators (for decorated functions/classes)
            "decorated_definition",
        }
    
    @property
    def file_extensions(self) -> Set[str]:
        return {".py", ".pyw", ".pyi"}
    
    def __init__(self):
        super().__init__()
        
        # Add rules for more complex scenarios
        self.add_chunk_rule(ChunkRule(
            node_types={"lambda"},
            include_children=False,
            priority=5,
            metadata={"type": "lambda_function"}
        ))
        
        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("string")  # Docstrings handled separately
        
        # TODO: Add more sophisticated rules for:
        # - Nested functions/classes
        # - Comprehensions that might be worth chunking
        # - Import statements grouping


# Register the Python configuration
from . import language_config_registry
language_config_registry.register(PythonConfig(), aliases=["py", "python3"])
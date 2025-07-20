"""Tree-sitter grammar repository implementation."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from ..interfaces.grammar import GrammarInfo, GrammarRepository, GrammarStatus

logger = logging.getLogger(__name__)


# Well-known Tree-sitter grammar repositories
KNOWN_GRAMMARS = {
    'python': {
        'url': 'https://github.com/tree-sitter/tree-sitter-python',
        'extensions': ['.py', '.pyw'],
        'description': 'Python programming language',
    },
    'javascript': {
        'url': 'https://github.com/tree-sitter/tree-sitter-javascript',
        'extensions': ['.js', '.mjs'],
        'description': 'JavaScript programming language',
    },
    'typescript': {
        'url': 'https://github.com/tree-sitter/tree-sitter-typescript',
        'extensions': ['.ts'],
        'description': 'TypeScript programming language',
    },
    'rust': {
        'url': 'https://github.com/tree-sitter/tree-sitter-rust',
        'extensions': ['.rs'],
        'description': 'Rust programming language',
    },
    'go': {
        'url': 'https://github.com/tree-sitter/tree-sitter-go',
        'extensions': ['.go'],
        'description': 'Go programming language',
    },
    'ruby': {
        'url': 'https://github.com/tree-sitter/tree-sitter-ruby',
        'extensions': ['.rb', '.rake', '.gemspec'],
        'description': 'Ruby programming language',
    },
    'java': {
        'url': 'https://github.com/tree-sitter/tree-sitter-java',
        'extensions': ['.java'],
        'description': 'Java programming language',
    },
    'c': {
        'url': 'https://github.com/tree-sitter/tree-sitter-c',
        'extensions': ['.c', '.h'],
        'description': 'C programming language',
    },
    'cpp': {
        'url': 'https://github.com/tree-sitter/tree-sitter-cpp',
        'extensions': ['.cpp', '.cc', '.cxx', '.hpp', '.hh', '.hxx'],
        'description': 'C++ programming language',
    },
    'csharp': {
        'url': 'https://github.com/tree-sitter/tree-sitter-c-sharp',
        'extensions': ['.cs'],
        'description': 'C# programming language',
    },
    'php': {
        'url': 'https://github.com/tree-sitter/tree-sitter-php',
        'extensions': ['.php'],
        'description': 'PHP programming language',
    },
    'swift': {
        'url': 'https://github.com/alex-pinkus/tree-sitter-swift',
        'extensions': ['.swift'],
        'description': 'Swift programming language',
    },
    'kotlin': {
        'url': 'https://github.com/fwcd/tree-sitter-kotlin',
        'extensions': ['.kt', '.kts'],
        'description': 'Kotlin programming language',
    },
    'scala': {
        'url': 'https://github.com/tree-sitter/tree-sitter-scala',
        'extensions': ['.scala'],
        'description': 'Scala programming language',
    },
    'haskell': {
        'url': 'https://github.com/tree-sitter/tree-sitter-haskell',
        'extensions': ['.hs'],
        'description': 'Haskell programming language',
    },
    'lua': {
        'url': 'https://github.com/MunifTanjim/tree-sitter-lua',
        'extensions': ['.lua'],
        'description': 'Lua programming language',
    },
    'bash': {
        'url': 'https://github.com/tree-sitter/tree-sitter-bash',
        'extensions': ['.sh', '.bash'],
        'description': 'Bash shell scripting',
    },
    'json': {
        'url': 'https://github.com/tree-sitter/tree-sitter-json',
        'extensions': ['.json'],
        'description': 'JSON data format',
    },
    'yaml': {
        'url': 'https://github.com/ikatyang/tree-sitter-yaml',
        'extensions': ['.yml', '.yaml'],
        'description': 'YAML data format',
    },
    'toml': {
        'url': 'https://github.com/ikatyang/tree-sitter-toml',
        'extensions': ['.toml'],
        'description': 'TOML configuration format',
    },
    'html': {
        'url': 'https://github.com/tree-sitter/tree-sitter-html',
        'extensions': ['.html', '.htm'],
        'description': 'HTML markup language',
    },
    'css': {
        'url': 'https://github.com/tree-sitter/tree-sitter-css',
        'extensions': ['.css'],
        'description': 'CSS stylesheet language',
    },
    'sql': {
        'url': 'https://github.com/DerekStride/tree-sitter-sql',
        'extensions': ['.sql'],
        'description': 'SQL query language',
    },
    'dockerfile': {
        'url': 'https://github.com/camdencheek/tree-sitter-dockerfile',
        'extensions': ['Dockerfile'],
        'description': 'Docker container definitions',
    },
    'markdown': {
        'url': 'https://github.com/MDeiml/tree-sitter-markdown',
        'extensions': ['.md', '.markdown'],
        'description': 'Markdown documentation format',
    },
}

# Popular languages for quick access
POPULAR_LANGUAGES = [
    'python', 'javascript', 'typescript', 'rust', 'go',
    'java', 'c', 'cpp', 'ruby', 'php', 'swift', 'kotlin'
]


class TreeSitterGrammarRepository(GrammarRepository):
    """Repository of known Tree-sitter grammar sources."""
    
    def __init__(self, custom_repo_file: Optional[Path] = None):
        """Initialize grammar repository.
        
        Args:
            custom_repo_file: Path to custom repository JSON file
        """
        self._grammars = KNOWN_GRAMMARS.copy()
        self._extension_map: Dict[str, str] = {}
        
        # Build extension mapping
        self._build_extension_map()
        
        # Load custom repositories if provided
        if custom_repo_file and custom_repo_file.exists():
            self._load_custom_repos(custom_repo_file)
    
    def search(self, query: str) -> List[GrammarInfo]:
        """Search for grammars.
        
        Args:
            query: Search query
            
        Returns:
            List of matching grammars
        """
        query_lower = query.lower()
        results = []
        
        for name, info in self._grammars.items():
            # Search in name and description
            if (query_lower in name.lower() or 
                query_lower in info.get('description', '').lower()):
                
                grammar = GrammarInfo(
                    name=name,
                    repository_url=info['url'],
                    status=GrammarStatus.NOT_FOUND
                )
                results.append(grammar)
        
        return results
    
    def get_popular_grammars(self, limit: int = 20) -> List[GrammarInfo]:
        """Get most popular grammars.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of popular grammars
        """
        results = []
        
        for name in POPULAR_LANGUAGES[:limit]:
            if name in self._grammars:
                info = self._grammars[name]
                grammar = GrammarInfo(
                    name=name,
                    repository_url=info['url'],
                    status=GrammarStatus.NOT_FOUND
                )
                results.append(grammar)
        
        return results
    
    def get_grammar_by_extension(self, extension: str) -> Optional[GrammarInfo]:
        """Find grammar for a file extension.
        
        Args:
            extension: File extension (e.g., '.py')
            
        Returns:
            Grammar info or None
        """
        # Normalize extension
        if not extension.startswith('.'):
            extension = '.' + extension
        
        language = self._extension_map.get(extension)
        if not language:
            return None
        
        info = self._grammars.get(language)
        if not info:
            return None
        
        return GrammarInfo(
            name=language,
            repository_url=info['url'],
            status=GrammarStatus.NOT_FOUND
        )
    
    def refresh_repository(self) -> bool:
        """Refresh repository data.
        
        Returns:
            True if successful
        """
        # In a real implementation, this might fetch from a remote source
        # For now, just rebuild the extension map
        self._build_extension_map()
        return True
    
    def get_grammar_info(self, name: str) -> Optional[GrammarInfo]:
        """Get information about a specific grammar.
        
        Args:
            name: Language name
            
        Returns:
            Grammar info or None
        """
        info = self._grammars.get(name)
        if not info:
            return None
        
        return GrammarInfo(
            name=name,
            repository_url=info['url'],
            status=GrammarStatus.NOT_FOUND
        )
    
    def list_all_grammars(self) -> List[str]:
        """List all known grammar names.
        
        Returns:
            List of grammar names
        """
        return sorted(self._grammars.keys())
    
    def _build_extension_map(self) -> None:
        """Build mapping from file extensions to languages."""
        self._extension_map.clear()
        
        for language, info in self._grammars.items():
            for ext in info.get('extensions', []):
                # First grammar wins for duplicate extensions
                if ext not in self._extension_map:
                    self._extension_map[ext] = language
    
    def _load_custom_repos(self, repo_file: Path) -> None:
        """Load custom repository definitions.
        
        Args:
            repo_file: Path to JSON file with custom repos
        """
        try:
            with open(repo_file, 'r') as f:
                custom_repos = json.load(f)
            
            # Merge with existing grammars
            self._grammars.update(custom_repos)
            
            # Rebuild extension map
            self._build_extension_map()
            
            logger.info(f"Loaded {len(custom_repos)} custom grammar repositories")
            
        except Exception as e:
            logger.error(f"Failed to load custom repositories: {e}")


# Singleton instance
_repository_instance: Optional[TreeSitterGrammarRepository] = None


def get_grammar_repository() -> GrammarRepository:
    """Get the grammar repository instance.
    
    Returns:
        Grammar repository
    """
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = TreeSitterGrammarRepository()
    return _repository_instance
# Tree-sitter Chunker Cookbook

This cookbook contains practical recipes for common use cases with Tree-sitter Chunker. Each recipe is self-contained and can be adapted to your specific needs.

## Table of Contents

1. [Code Search and Indexing](#code-search-and-indexing)
2. [Documentation Generation](#documentation-generation)
3. [Code Quality Analysis](#code-quality-analysis)
4. [AI/ML Integration](#aiml-integration)
5. [Plugin Development Recipes](#plugin-development-recipes)
6. [Export Format Recipes](#export-format-recipes)
7. [Performance Optimization](#performance-optimization)
8. [Configuration Recipes](#configuration-recipes)
9. [Language-Specific Recipes](#language-specific-recipes)
10. [Build Tool Integration](#build-tool-integration)
11. [Advanced Patterns](#advanced-patterns)

## Code Search and Indexing

### Build a Function Search Engine

Create a fast, searchable database of all functions in your codebase.

```python
import sqlite3
from pathlib import Path
from chunker.chunker import chunk_file
from chunker.parser import list_languages
from chunker.exceptions import LanguageNotFoundError
from datetime import datetime
import re

class CodeSearchEngine:
    """A SQLite-based searchable index of code chunks."""
    
    def __init__(self, db_path="code_index.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        
    def _create_tables(self):
        """Create database schema."""
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                language TEXT NOT NULL,
                node_type TEXT NOT NULL,
                name TEXT,
                start_line INTEGER,
                end_line INTEGER,
                parent_context TEXT,
                content TEXT,
                signature TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_name ON chunks(name);
            CREATE INDEX IF NOT EXISTS idx_type ON chunks(node_type);
            CREATE INDEX IF NOT EXISTS idx_file ON chunks(file_path);
            CREATE INDEX IF NOT EXISTS idx_parent ON chunks(parent_context);
        ''')
        self.conn.commit()
    
    def index_directory(self, directory):
        """Index all supported files in a directory."""
        path = Path(directory)
        language_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.rs': 'rust',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp'
        }
        
        indexed_count = 0
        for ext, language in language_extensions.items():
            for file_path in path.rglob(f"*{ext}"):
                if self._should_skip(file_path):
                    continue
                    
                try:
                    chunks = chunk_file(str(file_path), language)
                    for chunk in chunks:
                        self._index_chunk(chunk, file_path)
                        indexed_count += 1
                except Exception as e:
                    print(f"Error indexing {file_path}: {e}")
        
        self.conn.commit()
        print(f"Indexed {indexed_count} code chunks")
        return indexed_count
    
    def _should_skip(self, file_path):
        """Check if file should be skipped."""
        skip_dirs = {'__pycache__', 'node_modules', '.git', 'venv', '.venv'}
        return any(part in skip_dirs for part in file_path.parts)
    
    def _index_chunk(self, chunk, file_path):
        """Index a single chunk."""
        name = self._extract_name(chunk)
        signature = chunk.content.split('\n')[0].strip()
        
        self.conn.execute('''
            INSERT INTO chunks 
            (file_path, language, node_type, name, start_line, 
             end_line, parent_context, content, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(file_path),
            chunk.language,
            chunk.node_type,
            name,
            chunk.start_line,
            chunk.end_line,
            chunk.parent_context,
            chunk.content,
            signature
        ))
    
    def _extract_name(self, chunk):
        """Extract function/class name from chunk."""
        patterns = {
            'python': r'(?:def|class)\s+(\w+)',
            'javascript': r'(?:function|class|const|let|var)\s+(\w+)',
            'rust': r'(?:fn|struct|impl|trait)\s+(\w+)',
            'c': r'(?:\w+\s+)?(\w+)\s*\(',
            'cpp': r'(?:class|struct|(?:\w+\s+)?(\w+)\s*\()'
        }
        
        pattern = patterns.get(chunk.language, r'(\w+)')
        match = re.search(pattern, chunk.content)
        return match.group(1) if match else None
    
    def search(self, query, limit=20):
        """Search for chunks by name or content."""
        cursor = self.conn.execute('''
            SELECT * FROM chunks
            WHERE name LIKE ? OR content LIKE ?
            ORDER BY 
                CASE 
                    WHEN name = ? THEN 0
                    WHEN name LIKE ? THEN 1
                    ELSE 2
                END,
                name
            LIMIT ?
        ''', (
            f'%{query}%', f'%{query}%',
            query, f'{query}%',
            limit
        ))
        
        return [dict(row) for row in cursor]
    
    def find_by_type(self, node_type):
        """Find all chunks of a specific type."""
        cursor = self.conn.execute(
            'SELECT * FROM chunks WHERE node_type = ? ORDER BY file_path, start_line',
            (node_type,)
        )
        return [dict(row) for row in cursor]
    
    def find_in_file(self, file_path):
        """Find all chunks in a specific file."""
        cursor = self.conn.execute(
            'SELECT * FROM chunks WHERE file_path = ? ORDER BY start_line',
            (str(file_path),)
        )
        return [dict(row) for row in cursor]
    
    def get_statistics(self):
        """Get index statistics."""
        stats = {}
        
        # Total chunks
        cursor = self.conn.execute('SELECT COUNT(*) as count FROM chunks')
        stats['total_chunks'] = cursor.fetchone()['count']
        
        # By language
        cursor = self.conn.execute('''
            SELECT language, COUNT(*) as count 
            FROM chunks 
            GROUP BY language
        ''')
        stats['by_language'] = {row['language']: row['count'] for row in cursor}
        
        # By type
        cursor = self.conn.execute('''
            SELECT node_type, COUNT(*) as count 
            FROM chunks 
            GROUP BY node_type
            ORDER BY count DESC
        ''')
        stats['by_type'] = {row['node_type']: row['count'] for row in cursor}
        
        return stats

# Usage example
if __name__ == "__main__":
    # Create search engine
    engine = CodeSearchEngine()
    
    # Index your project
    engine.index_directory("./src")
    
    # Search for functions
    results = engine.search("process")
    for result in results[:5]:
        print(f"{result['file_path']}:{result['start_line']} - {result['name']}")
        print(f"  {result['signature']}")
    
    # Get statistics
    stats = engine.get_statistics()
    print(f"\nTotal chunks: {stats['total_chunks']}")
    print("By language:", stats['by_language'])
```

### Create a Symbol Navigator

Build an interactive symbol navigator for your codebase.

```python
from chunker.chunker import chunk_file
from pathlib import Path
from collections import defaultdict
import json

class SymbolNavigator:
    """Navigate code symbols hierarchically."""
    
    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.symbol_tree = {}
        self.build_tree()
    
    def build_tree(self):
        """Build hierarchical symbol tree."""
        for py_file in self.root_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                chunks = chunk_file(str(py_file), "python")
                rel_path = py_file.relative_to(self.root_dir)
                
                file_symbols = {
                    'path': str(rel_path),
                    'classes': {},
                    'functions': [],
                    'total_lines': 0
                }
                
                # First pass: collect classes
                for chunk in chunks:
                    if chunk.node_type == "class_definition":
                        class_name = self._extract_name(chunk)
                        file_symbols['classes'][class_name] = {
                            'line': chunk.start_line,
                            'end_line': chunk.end_line,
                            'methods': [],
                            'docstring': self._extract_docstring(chunk)
                        }
                
                # Second pass: collect methods and functions
                for chunk in chunks:
                    if chunk.node_type == "function_definition":
                        func_info = {
                            'name': self._extract_name(chunk),
                            'line': chunk.start_line,
                            'end_line': chunk.end_line,
                            'is_async': 'async def' in chunk.content.split('\n')[0],
                            'decorators': self._extract_decorators(chunk)
                        }
                        
                        if chunk.parent_context:
                            # It's a method
                            class_name = chunk.parent_context.split(':')[1]
                            if class_name in file_symbols['classes']:
                                file_symbols['classes'][class_name]['methods'].append(func_info)
                        else:
                            # It's a standalone function
                            file_symbols['functions'].append(func_info)
                
                # Calculate total lines
                if chunks:
                    file_symbols['total_lines'] = max(c.end_line for c in chunks)
                
                self.symbol_tree[str(rel_path)] = file_symbols
                
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
    
    def _extract_name(self, chunk):
        """Extract name from chunk."""
        import re
        match = re.search(r'(?:def|class)\s+(\w+)', chunk.content)
        return match.group(1) if match else "unknown"
    
    def _extract_docstring(self, chunk):
        """Extract first line of docstring."""
        lines = chunk.content.split('\n')
        for i, line in enumerate(lines[1:3]):
            if '"""' in line or "'''" in line:
                return line.strip().strip('"""').strip("'''")
        return None
    
    def _extract_decorators(self, chunk):
        """Extract decorator names."""
        decorators = []
        lines = chunk.content.split('\n')
        for line in lines:
            if line.strip().startswith('@'):
                decorator = line.strip().lstrip('@').split('(')[0]
                decorators.append(decorator)
            elif line.strip().startswith('def '):
                break
        return decorators
    
    def print_tree(self):
        """Print symbol tree in a nice format."""
        for file_path, symbols in sorted(self.symbol_tree.items()):
            print(f"\n📄 {file_path} ({symbols['total_lines']} lines)")
            
            # Print classes
            for class_name, class_info in symbols['classes'].items():
                print(f"  📦 {class_name} (line {class_info['line']})")
                if class_info['docstring']:
                    print(f"     📝 {class_info['docstring']}")
                
                for method in sorted(class_info['methods'], key=lambda x: x['line']):
                    icon = "⚡" if method['is_async'] else "🔧"
                    print(f"    {icon} {method['name']} (line {method['line']})")
                    if method['decorators']:
                        print(f"       🏷️  {', '.join(method['decorators'])}")
            
            # Print standalone functions
            for func in sorted(symbols['functions'], key=lambda x: x['line']):
                icon = "⚡" if func['is_async'] else "🔧"
                print(f"  {icon} {func['name']} (line {func['line']})")
                if func['decorators']:
                    print(f"     🏷️  {', '.join(func['decorators'])}")
    
    def export_json(self, output_file):
        """Export symbol tree as JSON."""
        with open(output_file, 'w') as f:
            json.dump(self.symbol_tree, f, indent=2)
    
    def find_symbol(self, symbol_name):
        """Find all occurrences of a symbol."""
        results = []
        
        for file_path, symbols in self.symbol_tree.items():
            # Check classes
            if symbol_name in symbols['classes']:
                results.append({
                    'file': file_path,
                    'type': 'class',
                    'line': symbols['classes'][symbol_name]['line']
                })
            
            # Check methods
            for class_name, class_info in symbols['classes'].items():
                for method in class_info['methods']:
                    if method['name'] == symbol_name:
                        results.append({
                            'file': file_path,
                            'type': 'method',
                            'class': class_name,
                            'line': method['line']
                        })
            
            # Check functions
            for func in symbols['functions']:
                if func['name'] == symbol_name:
                    results.append({
                        'file': file_path,
                        'type': 'function',
                        'line': func['line']
                    })
        
        return results

# Usage
navigator = SymbolNavigator("./src")
navigator.print_tree()

# Find specific symbol
results = navigator.find_symbol("__init__")
print(f"\nFound {len(results)} occurrences of '__init__':")
for r in results:
    print(f"  {r['file']}:{r['line']} ({r['type']})")
```

## Documentation Generation

### Generate API Documentation with Type Hints

Extract comprehensive API documentation including type hints and examples.

```python
import ast
from chunker.chunker import chunk_file
from pathlib import Path
from typing import List, Dict, Any
import re

class APIDocGenerator:
    """Generate rich API documentation from Python code."""
    
    def __init__(self):
        self.docs = []
    
    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Process a Python file and extract API documentation."""
        chunks = chunk_file(file_path, "python")
        file_docs = []
        
        for chunk in chunks:
            if chunk.node_type in ["function_definition", "class_definition"]:
                try:
                    doc = self._extract_documentation(chunk, file_path)
                    if doc:
                        file_docs.append(doc)
                except Exception as e:
                    print(f"Error processing {chunk.node_type} at line {chunk.start_line}: {e}")
        
        return file_docs
    
    def _extract_documentation(self, chunk, file_path):
        """Extract comprehensive documentation from a chunk."""
        try:
            tree = ast.parse(chunk.content)
            if not tree.body:
                return None
                
            node = tree.body[0]
            
            doc = {
                'name': node.name if hasattr(node, 'name') else 'unknown',
                'type': chunk.node_type,
                'file': file_path,
                'line': chunk.start_line,
                'end_line': chunk.end_line,
                'parent': chunk.parent_context,
                'docstring': ast.get_docstring(node),
                'source': chunk.content
            }
            
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                doc.update(self._extract_function_details(node))
            elif isinstance(node, ast.ClassDef):
                doc.update(self._extract_class_details(node, chunk))
            
            return doc
            
        except Exception as e:
            return None
    
    def _extract_function_details(self, node):
        """Extract function-specific details."""
        details = {
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'parameters': self._extract_parameters(node),
            'returns': self._extract_return_type(node),
            'raises': self._extract_raises(node),
            'yields': self._check_yields(node),
            'examples': self._extract_examples(ast.get_docstring(node))
        }
        return details
    
    def _extract_class_details(self, node, chunk):
        """Extract class-specific details."""
        details = {
            'bases': [ast.unparse(base) for base in node.bases],
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'methods': self._count_methods(node),
            'class_variables': self._extract_class_variables(node),
            'is_dataclass': any(self._get_decorator_name(d) == 'dataclass' 
                               for d in node.decorator_list)
        }
        return details
    
    def _get_decorator_name(self, decorator):
        """Get decorator name as string."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
            return decorator.func.id
        else:
            return ast.unparse(decorator)
    
    def _extract_parameters(self, func_node):
        """Extract function parameters with type hints."""
        params = []
        args = func_node.args
        
        # Regular arguments
        for i, arg in enumerate(args.args):
            param = {
                'name': arg.arg,
                'type': ast.unparse(arg.annotation) if arg.annotation else None,
                'default': None
            }
            
            # Check for defaults
            defaults_start = len(args.args) - len(args.defaults)
            if i >= defaults_start:
                default_index = i - defaults_start
                param['default'] = ast.unparse(args.defaults[default_index])
            
            params.append(param)
        
        # *args
        if args.vararg:
            params.append({
                'name': f"*{args.vararg.arg}",
                'type': ast.unparse(args.vararg.annotation) if args.vararg.annotation else None,
                'default': None
            })
        
        # **kwargs
        if args.kwarg:
            params.append({
                'name': f"**{args.kwarg.arg}",
                'type': ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else None,
                'default': None
            })
        
        return params
    
    def _extract_return_type(self, func_node):
        """Extract return type annotation."""
        if func_node.returns:
            return ast.unparse(func_node.returns)
        return None
    
    def _extract_raises(self, node):
        """Extract exceptions that might be raised."""
        raises = []
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc:
                    if isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                        raises.append(child.exc.func.id)
                    elif isinstance(child.exc, ast.Name):
                        raises.append(child.exc.id)
        return list(set(raises))
    
    def _check_yields(self, node):
        """Check if function is a generator."""
        for child in ast.walk(node):
            if isinstance(child, ast.Yield) or isinstance(child, ast.YieldFrom):
                return True
        return False
    
    def _extract_examples(self, docstring):
        """Extract code examples from docstring."""
        if not docstring:
            return []
        
        examples = []
        in_example = False
        current_example = []
        
        for line in docstring.split('\n'):
            if '>>>' in line:
                in_example = True
                current_example.append(line)
            elif in_example and line.strip() and not line.startswith(' '):
                # End of example
                if current_example:
                    examples.append('\n'.join(current_example))
                current_example = []
                in_example = False
            elif in_example:
                current_example.append(line)
        
        if current_example:
            examples.append('\n'.join(current_example))
        
        return examples
    
    def _count_methods(self, class_node):
        """Count methods in a class."""
        return sum(1 for node in class_node.body 
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    
    def _extract_class_variables(self, class_node):
        """Extract class variables with type annotations."""
        variables = []
        for node in class_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                variables.append({
                    'name': node.target.id,
                    'type': ast.unparse(node.annotation),
                    'value': ast.unparse(node.value) if node.value else None
                })
        return variables
    
    def generate_markdown(self, docs: List[Dict[str, Any]]) -> str:
        """Generate comprehensive Markdown documentation."""
        md = ["# API Documentation\n"]
        md.append("*Generated with Tree-sitter Chunker*\n")
        
        # Group by file
        by_file = {}
        for doc in docs:
            by_file.setdefault(doc['file'], []).append(doc)
        
        # Generate table of contents
        md.append("## Table of Contents\n")
        for file_path in sorted(by_file.keys()):
            file_name = Path(file_path).name
            md.append(f"- [{file_name}](#{file_name.replace('.', '').lower()})")
        md.append("")
        
        # Generate documentation for each file
        for file_path, file_docs in sorted(by_file.items()):
            file_name = Path(file_path).name
            md.append(f"\n## {file_name}\n")
            md.append(f"*{file_path}*\n")
            
            # Sort by type (classes first) and line number
            sorted_docs = sorted(file_docs, 
                               key=lambda x: (0 if x['type'] == 'class_definition' else 1, x['line']))
            
            for doc in sorted_docs:
                if doc['type'] == 'class_definition':
                    md.extend(self._format_class_doc(doc))
                else:
                    md.extend(self._format_function_doc(doc))
        
        return '\n'.join(md)
    
    def _format_class_doc(self, doc):
        """Format class documentation."""
        lines = [f"\n### class `{doc['name']}`\n"]
        
        if doc.get('bases'):
            lines.append(f"*Inherits from: {', '.join(doc['bases'])}*\n")
        
        if doc.get('decorators'):
            lines.append(f"**Decorators:** `{', '.join(doc['decorators'])}`\n")
        
        if doc.get('docstring'):
            lines.append(doc['docstring'] + '\n')
        
        if doc.get('class_variables'):
            lines.append("**Class Variables:**")
            for var in doc['class_variables']:
                lines.append(f"- `{var['name']}: {var['type']}`" + 
                           (f" = `{var['value']}`" if var['value'] else ""))
            lines.append("")
        
        lines.append(f"**Methods:** {doc.get('methods', 0)}\n")
        
        return lines
    
    def _format_function_doc(self, doc):
        """Format function documentation."""
        name = doc['name']
        if doc.get('parent'):
            name = f"{doc['parent'].split(':')[1]}.{name}"
        
        lines = [f"\n### {'async ' if doc.get('is_async') else ''}function `{name}`\n"]
        
        if doc.get('decorators'):
            lines.append(f"**Decorators:** `{', '.join(doc['decorators'])}`\n")
        
        # Signature
        if doc.get('parameters'):
            params = []
            for p in doc['parameters']:
                param_str = p['name']
                if p['type']:
                    param_str += f": {p['type']}"
                if p['default']:
                    param_str += f" = {p['default']}"
                params.append(param_str)
            
            returns = f" -> {doc['returns']}" if doc.get('returns') else ""
            lines.append(f"```python\n{name}({', '.join(params)}){returns}\n```\n")
        
        if doc.get('docstring'):
            lines.append(doc['docstring'] + '\n')
        
        if doc.get('raises'):
            lines.append(f"**Raises:** {', '.join(f'`{e}`' for e in doc['raises'])}\n")
        
        if doc.get('yields'):
            lines.append("**Yields:** This is a generator function\n")
        
        if doc.get('examples'):
            lines.append("**Examples:**")
            for example in doc['examples']:
                lines.append("```python")
                lines.append(example)
                lines.append("```")
            lines.append("")
        
        return lines

# Usage
generator = APIDocGenerator()

# Process a file or directory
all_docs = []
for py_file in Path("src").rglob("*.py"):
    docs = generator.process_file(str(py_file))
    all_docs.extend(docs)

# Generate markdown
markdown = generator.generate_markdown(all_docs)

# Save documentation
with open("API_DOCUMENTATION.md", "w") as f:
    f.write(markdown)

print(f"Generated documentation for {len(all_docs)} items")
```

### Generate README from Code Structure

Automatically generate project documentation from your codebase.

```python
from chunker.chunker import chunk_file
from chunker.parser import list_languages
from pathlib import Path
import re

class ReadmeGenerator:
    """Generate README.md from code analysis."""
    
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.project_name = self.project_path.name
        
    def generate(self):
        """Generate complete README."""
        sections = []
        
        # Title and description
        sections.append(self._generate_header())
        
        # Project structure
        sections.append(self._generate_structure())
        
        # API overview
        sections.append(self._generate_api_overview())
        
        # Installation
        sections.append(self._generate_installation())
        
        # Usage examples
        sections.append(self._generate_usage_examples())
        
        # Contributing
        sections.append(self._generate_contributing())
        
        return '\n\n'.join(filter(None, sections))
    
    def _generate_header(self):
        """Generate header section."""
        header = [f"# {self.project_name}"]
        
        # Try to extract description from main module
        init_file = self.project_path / "__init__.py"
        if init_file.exists():
            with open(init_file) as f:
                content = f.read()
                if content.strip().startswith('"""'):
                    docstring = content.split('"""')[1].strip()
                    header.append(f"\n{docstring}")
        
        # Add badges (placeholder)
        header.append("\n![Python](https://img.shields.io/badge/python-3.8+-blue.svg)")
        header.append("![License](https://img.shields.io/badge/license-MIT-green.svg)")
        
        return '\n'.join(header)
    
    def _generate_structure(self):
        """Generate project structure overview."""
        lines = ["## Project Structure\n"]
        
        # Find main modules
        modules = {}
        for py_file in self.project_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            rel_path = py_file.relative_to(self.project_path)
            if rel_path.parts[0] not in ['tests', 'docs', 'examples']:
                module_path = str(rel_path.parent).replace('/', '.')
                if module_path == '.':
                    module_path = 'root'
                modules.setdefault(module_path, []).append(py_file.stem)
        
        lines.append("```")
        lines.append(f"{self.project_name}/")
        for module, files in sorted(modules.items()):
            if module != 'root':
                lines.append(f"├── {module.replace('.', '/')}/")
                for file in sorted(files):
                    if file != '__init__':
                        lines.append(f"│   ├── {file}.py")
            else:
                for file in sorted(files):
                    if file != '__init__':
                        lines.append(f"├── {file}.py")
        lines.append("```")
        
        return '\n'.join(lines)
    
    def _generate_api_overview(self):
        """Generate API overview from code analysis."""
        lines = ["## API Overview\n"]
        
        # Analyze main modules
        api_items = []
        for py_file in self.project_path.rglob("*.py"):
            if any(skip in str(py_file) for skip in ['__pycache__', 'tests', '_test']):
                continue
            
            try:
                chunks = chunk_file(str(py_file), "python")
                module_name = py_file.stem
                
                # Find public classes and functions
                for chunk in chunks:
                    if chunk.node_type in ["class_definition", "function_definition"]:
                        if not chunk.parent_context:  # Top-level only
                            name = self._extract_name(chunk)
                            if name and not name.startswith('_'):
                                docstring = self._extract_first_line_docstring(chunk)
                                api_items.append({
                                    'module': module_name,
                                    'name': name,
                                    'type': 'class' if 'class' in chunk.node_type else 'function',
                                    'docstring': docstring
                                })
            except:
                continue
        
        # Group by module
        by_module = {}
        for item in api_items:
            by_module.setdefault(item['module'], []).append(item)
        
        for module, items in sorted(by_module.items()):
            if items:
                lines.append(f"### {module}\n")
                for item in sorted(items, key=lambda x: (x['type'], x['name'])):
                    icon = "🔷" if item['type'] == 'class' else "🔸"
                    desc = f" - {item['docstring']}" if item['docstring'] else ""
                    lines.append(f"- {icon} **{item['name']}**{desc}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_installation(self):
        """Generate installation instructions."""
        lines = ["## Installation\n"]
        
        # Check for setup.py or pyproject.toml
        if (self.project_path / "setup.py").exists() or (self.project_path / "pyproject.toml").exists():
            lines.append("```bash")
            lines.append(f"pip install {self.project_name}")
            lines.append("```")
            lines.append("\nFor development:")
            lines.append("```bash")
            lines.append(f"git clone https://github.com/yourusername/{self.project_name}.git")
            lines.append(f"cd {self.project_name}")
            lines.append("pip install -e .[dev]")
            lines.append("```")
        else:
            lines.append("```bash")
            lines.append(f"git clone https://github.com/yourusername/{self.project_name}.git")
            lines.append(f"cd {self.project_name}")
            lines.append("pip install -r requirements.txt")
            lines.append("```")
        
        return '\n'.join(lines)
    
    def _generate_usage_examples(self):
        """Generate usage examples from code."""
        lines = ["## Usage\n"]
        
        # Look for main entry points
        main_funcs = []
        for py_file in self.project_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                chunks = chunk_file(str(py_file), "python")
                for chunk in chunks:
                    if chunk.node_type == "function_definition":
                        name = self._extract_name(chunk)
                        if name in ['main', 'run', 'start'] or py_file.stem == '__main__':
                            main_funcs.append({
                                'file': py_file,
                                'name': name,
                                'chunk': chunk
                            })
            except:
                continue
        
        if main_funcs:
            lines.append("### Basic Usage\n")
            lines.append("```python")
            lines.append(f"from {self.project_name} import ...")
            lines.append("```")
        
        # Look for example files
        example_files = list(self.project_path.glob("examples/*.py"))
        if example_files:
            lines.append("\n### Examples\n")
            for example in example_files[:3]:  # Show first 3
                lines.append(f"See `{example.relative_to(self.project_path)}` for a complete example.")
        
        return '\n'.join(lines)
    
    def _generate_contributing(self):
        """Generate contributing section."""
        lines = ["## Contributing\n"]
        lines.append("Contributions are welcome! Please feel free to submit a Pull Request.")
        
        # Check for tests
        if (self.project_path / "tests").exists() or list(self.project_path.glob("test_*.py")):
            lines.append("\nPlease make sure to update tests as appropriate:")
            lines.append("```bash")
            lines.append("pytest")
            lines.append("```")
        
        return '\n'.join(lines)
    
    def _extract_name(self, chunk):
        """Extract name from chunk."""
        match = re.search(r'(?:def|class)\s+(\w+)', chunk.content)
        return match.group(1) if match else None
    
    def _extract_first_line_docstring(self, chunk):
        """Extract first line of docstring."""
        lines = chunk.content.split('\n')
        for i, line in enumerate(lines[1:3]):
            if '"""' in line or "'''" in line:
                # Extract just the first sentence
                docstring = line.strip().strip('"""').strip("'''")
                if '. ' in docstring:
                    docstring = docstring.split('. ')[0] + '.'
                return docstring
        return None

# Usage
generator = ReadmeGenerator("./my_project")
readme_content = generator.generate()

with open("README_generated.md", "w") as f:
    f.write(readme_content)

print("README.md generated successfully!")
```

## Code Quality Analysis

### Complexity Analysis

Analyze code complexity using various metrics.

```python
from chunker.chunker import chunk_file
from chunker.parser import get_parser
import ast
from dataclasses import dataclass
from typing import List
import statistics

@dataclass
class ComplexityReport:
    """Code complexity metrics for a function."""
    name: str
    file: str
    line: int
    end_line: int
    complexity: int  # Cyclomatic complexity
    cognitive_complexity: int
    lines_of_code: int
    max_nesting: int
    parameter_count: int
    return_points: int

class ComplexityAnalyzer:
    """Comprehensive code complexity analyzer."""
    
    def analyze_file(self, file_path: str) -> List[ComplexityReport]:
        """Analyze all functions in a file."""
        chunks = chunk_file(file_path, "python")
        reports = []
        
        for chunk in chunks:
            if chunk.node_type == "function_definition":
                report = self._analyze_function(chunk, file_path)
                if report:
                    reports.append(report)
        
        return reports
    
    def _analyze_function(self, chunk, file_path):
        """Analyze a single function."""
        try:
            tree = ast.parse(chunk.content)
            if not tree.body:
                return None
                
            func = tree.body[0]
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return None
            
            return ComplexityReport(
                name=func.name,
                file=file_path,
                line=chunk.start_line,
                end_line=chunk.end_line,
                complexity=self._cyclomatic_complexity(func),
                cognitive_complexity=self._cognitive_complexity(func),
                lines_of_code=chunk.end_line - chunk.start_line + 1,
                max_nesting=self._max_nesting_depth(func),
                parameter_count=len(func.args.args),
                return_points=self._count_returns(func)
            )
        except Exception as e:
            print(f"Error analyzing function at line {chunk.start_line}: {e}")
            return None
    
    def _cyclomatic_complexity(self, node):
        """Calculate McCabe cyclomatic complexity."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            # Decision points
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            # Boolean operators
            elif isinstance(child, ast.BoolOp):
                # Each 'and'/'or' adds a branch
                complexity += len(child.values) - 1
            # Comprehensions
            elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                complexity += sum(1 for _ in child.generators)
        
        return complexity
    
    def _cognitive_complexity(self, node, nesting=0):
        """Calculate cognitive complexity (how hard to understand)."""
        complexity = 0
        
        for child in node.body:
            if isinstance(child, ast.If):
                # If statements increase complexity, more with nesting
                complexity += 1 + nesting
                # Check for else
                if child.orelse:
                    complexity += 1
                # Recurse
                complexity += self._cognitive_complexity(child, nesting + 1)
                
            elif isinstance(child, (ast.For, ast.While)):
                complexity += 1 + nesting
                complexity += self._cognitive_complexity(child, nesting + 1)
                
            elif isinstance(child, ast.Try):
                complexity += 1 + nesting
                for handler in child.handlers:
                    complexity += 1
                    complexity += self._cognitive_complexity(handler, nesting + 1)
                    
            elif isinstance(child, ast.With):
                complexity += 1 + nesting
                complexity += self._cognitive_complexity(child, nesting + 1)
                
            elif hasattr(child, 'body'):
                complexity += self._cognitive_complexity(child, nesting)
        
        return complexity
    
    def _max_nesting_depth(self, node, depth=0):
        """Calculate maximum nesting depth."""
        max_depth = depth
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                if hasattr(child, 'body'):
                    for nested in child.body:
                        child_depth = self._max_nesting_depth(nested, depth + 1)
                        max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def _count_returns(self, node):
        """Count number of return statements."""
        return sum(1 for child in ast.walk(node) 
                  if isinstance(child, (ast.Return, ast.Yield, ast.YieldFrom)))
    
    def generate_report(self, reports: List[ComplexityReport]):
        """Generate a complexity report."""
        if not reports:
            print("No functions analyzed.")
            return
        
        print("Code Complexity Report")
        print("=" * 100)
        print(f"{'Function':<30} {'CC':<5} {'Cog':<5} {'LOC':<5} {'Nest':<5} {'Params':<7} {'Returns':<7} {'Status'}")
        print("-" * 100)
        
        # Sort by cyclomatic complexity
        for r in sorted(reports, key=lambda x: x.complexity, reverse=True):
            # Determine status
            if r.complexity > 10:
                status = "🔴 High"
            elif r.complexity > 5:
                status = "🟡 Medium"
            else:
                status = "🟢 Low"
            
            print(f"{r.name:<30} {r.complexity:<5} {r.cognitive_complexity:<5} "
                  f"{r.lines_of_code:<5} {r.max_nesting:<5} {r.parameter_count:<7} "
                  f"{r.return_points:<7} {status}")
        
        # Summary statistics
        print("\nSummary Statistics:")
        print(f"  Total functions: {len(reports)}")
        print(f"  Average cyclomatic complexity: {statistics.mean(r.complexity for r in reports):.2f}")
        print(f"  Average cognitive complexity: {statistics.mean(r.cognitive_complexity for r in reports):.2f}")
        print(f"  High complexity functions (CC > 10): {sum(1 for r in reports if r.complexity > 10)}")
        print(f"  Total lines of code: {sum(r.lines_of_code for r in reports)}")
    
    def find_complex_functions(self, reports: List[ComplexityReport], threshold=10):
        """Find functions exceeding complexity threshold."""
        complex_funcs = [r for r in reports if r.complexity > threshold]
        
        if complex_funcs:
            print(f"\nFunctions exceeding complexity threshold ({threshold}):")
            for r in sorted(complex_funcs, key=lambda x: x.complexity, reverse=True):
                print(f"  {r.file}:{r.line} - {r.name} (CC: {r.complexity})")
                print(f"    Suggestions:")
                if r.max_nesting > 3:
                    print(f"    - Reduce nesting (current: {r.max_nesting} levels)")
                if r.parameter_count > 5:
                    print(f"    - Consider using configuration object (current: {r.parameter_count} params)")
                if r.lines_of_code > 50:
                    print(f"    - Split into smaller functions (current: {r.lines_of_code} lines)")
        
        return complex_funcs

# Usage
analyzer = ComplexityAnalyzer()

# Analyze a single file
reports = analyzer.analyze_file("complex_module.py")
analyzer.generate_report(reports)

# Find overly complex functions
complex_functions = analyzer.find_complex_functions(reports, threshold=10)

# Analyze entire project
all_reports = []
for py_file in Path("src").rglob("*.py"):
    reports = analyzer.analyze_file(str(py_file))
    all_reports.extend(reports)

analyzer.generate_report(all_reports)
```

### Code Duplication Detection

Find duplicate or similar code blocks.

```python
from chunker.chunker import chunk_file
from pathlib import Path
import hashlib
from difflib import SequenceMatcher
from collections import defaultdict
from typing import List, Tuple

class DuplicationDetector:
    """Detect duplicate and similar code blocks."""
    
    def __init__(self, similarity_threshold=0.85):
        self.similarity_threshold = similarity_threshold
        self.chunks_by_hash = defaultdict(list)
        self.all_chunks = []
    
    def analyze_directory(self, directory):
        """Analyze all Python files in directory."""
        for py_file in Path(directory).rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                chunks = chunk_file(str(py_file), "python")
                for chunk in chunks:
                    if chunk.node_type in ["function_definition", "method_definition"]:
                        # Normalize content for comparison
                        normalized = self._normalize_code(chunk.content)
                        chunk_hash = hashlib.md5(normalized.encode()).hexdigest()
                        
                        self.chunks_by_hash[chunk_hash].append(chunk)
                        self.all_chunks.append(chunk)
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
    
    def _normalize_code(self, code):
        """Normalize code for comparison (remove comments, normalize whitespace)."""
        lines = []
        for line in code.split('\n'):
            # Remove comments
            if '#' in line:
                line = line[:line.index('#')]
            # Normalize whitespace
            line = ' '.join(line.split())
            if line:
                lines.append(line)
        return '\n'.join(lines)
    
    def find_exact_duplicates(self):
        """Find exact duplicate functions."""
        duplicates = []
        
        for chunk_hash, chunks in self.chunks_by_hash.items():
            if len(chunks) > 1:
                duplicates.append({
                    'hash': chunk_hash,
                    'chunks': chunks,
                    'count': len(chunks)
                })
        
        return sorted(duplicates, key=lambda x: x['count'], reverse=True)
    
    def find_similar_code(self):
        """Find similar (but not identical) code blocks."""
        similar_groups = []
        checked_pairs = set()
        
        for i, chunk1 in enumerate(self.all_chunks):
            similar_chunks = []
            
            for j, chunk2 in enumerate(self.all_chunks[i+1:], i+1):
                pair_key = (i, j)
                if pair_key in checked_pairs:
                    continue
                    
                similarity = self._calculate_similarity(chunk1.content, chunk2.content)
                if similarity >= self.similarity_threshold:
                    similar_chunks.append({
                        'chunk': chunk2,
                        'similarity': similarity
                    })
                    checked_pairs.add(pair_key)
            
            if similar_chunks:
                similar_groups.append({
                    'original': chunk1,
                    'similar': similar_chunks
                })
        
        return similar_groups
    
    def _calculate_similarity(self, code1, code2):
        """Calculate similarity between two code blocks."""
        # Normalize for comparison
        norm1 = self._normalize_code(code1)
        norm2 = self._normalize_code(code2)
        
        # Use sequence matcher for similarity
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def generate_report(self):
        """Generate duplication report."""
        exact_duplicates = self.find_exact_duplicates()
        similar_code = self.find_similar_code()
        
        print("Code Duplication Report")
        print("=" * 80)
        
        # Exact duplicates
        if exact_duplicates:
            print(f"\n🔴 Exact Duplicates Found: {len(exact_duplicates)} groups")
            print("-" * 80)
            
            for dup_group in exact_duplicates:
                print(f"\nDuplicate group ({dup_group['count']} instances):")
                for chunk in dup_group['chunks']:
                    print(f"  - {chunk.file_path}:{chunk.start_line}-{chunk.end_line}")
                    name = chunk.content.split('\n')[0].strip()
                    print(f"    {name}")
                
                # Show the duplicate code
                print("\n  Code:")
                preview = dup_group['chunks'][0].content.split('\n')[:5]
                for line in preview:
                    print(f"    {line}")
                if len(dup_group['chunks'][0].content.split('\n')) > 5:
                    print("    ...")
        else:
            print("\n✅ No exact duplicates found")
        
        # Similar code
        if similar_code:
            print(f"\n🟡 Similar Code Blocks: {len(similar_code)} groups")
            print("-" * 80)
            
            for group in similar_code[:10]:  # Show top 10
                orig = group['original']
                print(f"\nOriginal: {orig.file_path}:{orig.start_line}")
                
                for similar in group['similar']:
                    chunk = similar['chunk']
                    similarity = similar['similarity']
                    print(f"  Similar ({similarity:.0%}): {chunk.file_path}:{chunk.start_line}")
        
        # Summary
        total_chunks = len(self.all_chunks)
        duplicate_chunks = sum(len(g['chunks']) for g in exact_duplicates)
        
        print(f"\n📊 Summary:")
        print(f"  Total functions analyzed: {total_chunks}")
        print(f"  Exact duplicate functions: {duplicate_chunks}")
        print(f"  Duplication rate: {duplicate_chunks/total_chunks*100:.1f}%")
        
        # Calculate saved lines
        saved_lines = 0
        for dup_group in exact_duplicates:
            if len(dup_group['chunks']) > 1:
                chunk = dup_group['chunks'][0]
                lines = chunk.end_line - chunk.start_line + 1
                saved_lines += lines * (len(dup_group['chunks']) - 1)
        
        if saved_lines > 0:
            print(f"  Potential lines saved by removing duplicates: {saved_lines}")
    
    def suggest_refactoring(self, duplicates):
        """Suggest refactoring for duplicate code."""
        suggestions = []
        
        for dup_group in duplicates:
            if len(dup_group['chunks']) >= 3:
                # Multiple duplicates - suggest extracting to shared module
                suggestions.append({
                    'type': 'extract_to_module',
                    'chunks': dup_group['chunks'],
                    'reason': f"{len(dup_group['chunks'])} duplicate implementations found"
                })
            elif len(dup_group['chunks']) == 2:
                # Two duplicates - check if they're in related modules
                chunk1, chunk2 = dup_group['chunks']
                if Path(chunk1.file_path).parent == Path(chunk2.file_path).parent:
                    suggestions.append({
                        'type': 'extract_to_base',
                        'chunks': dup_group['chunks'],
                        'reason': "Duplicates in same module - consider extracting"
                    })
        
        return suggestions

# Usage
detector = DuplicationDetector(similarity_threshold=0.85)

# Analyze codebase
detector.analyze_directory("./src")

# Generate report
detector.generate_report()

# Get suggestions
duplicates = detector.find_exact_duplicates()
suggestions = detector.suggest_refactoring(duplicates)

if suggestions:
    print("\n💡 Refactoring Suggestions:")
    for suggestion in suggestions:
        print(f"\n- {suggestion['type']}:")
        print(f"  Reason: {suggestion['reason']}")
        print("  Affected files:")
        for chunk in suggestion['chunks']:
            print(f"    - {chunk.file_path}:{chunk.start_line}")
```

## Plugin Development Recipes

### Creating a Custom Language Plugin

Create a plugin for a language not yet supported.

```python
from chunker.languages.plugin_base import LanguagePlugin
from chunker import get_plugin_manager, chunk_file
from typing import Set, Optional, Dict, Any
from tree_sitter import Node
import re

class SwiftPlugin(LanguagePlugin):
    """Plugin for Swift language support."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.function_pattern = re.compile(r'func\s+(\w+)')
        self.class_pattern = re.compile(r'class\s+(\w+)')
        self.struct_pattern = re.compile(r'struct\s+(\w+)')
    
    @property
    def language_name(self) -> str:
        return "swift"
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {".swift"}
    
    @property
    def default_chunk_types(self) -> Set[str]:
        return {
            "function_declaration",
            "init_declaration",
            "class_declaration",
            "struct_declaration",
            "enum_declaration",
            "protocol_declaration",
            "extension_declaration"
        }
    
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        """Extract the name from a Swift node."""
        content = source[node.start_byte:node.end_byte].decode('utf-8')
        first_line = content.split('\n')[0]
        
        # Try different patterns
        patterns = {
            'function_declaration': self.function_pattern,
            'class_declaration': self.class_pattern,
            'struct_declaration': self.struct_pattern
        }
        
        pattern = patterns.get(node.type)
        if pattern:
            match = pattern.search(first_line)
            if match:
                return match.group(1)
        
        # Fallback: extract identifier
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte:child.end_byte].decode('utf-8')
        
        return None
    
    def should_include_chunk(self, chunk) -> bool:
        """Apply Swift-specific filtering."""
        # Skip test files if configured
        if self.config and self.config.custom_options.get('skip_tests', False):
            if 'test' in chunk.file_path.lower() or 'Test' in chunk.content:
                return False
        
        # Skip private functions if configured
        if self.config and self.config.custom_options.get('skip_private', False):
            if chunk.content.strip().startswith('private '):
                return False
        
        return super().should_include_chunk(chunk)
    
    def process_node(self, node: Node, source: bytes, file_path: str, parent_context=None):
        """Process Swift nodes with special handling."""
        chunk = super().process_node(node, source, file_path, parent_context)
        
        if chunk and node.type == "computed_property":
            # Add metadata for computed properties
            chunk.metadata = {
                'property_type': 'computed',
                'has_getter': 'get {' in chunk.content,
                'has_setter': 'set {' in chunk.content
            }
        
        return chunk

# Usage example
class SwiftProjectAnalyzer:
    """Analyze Swift projects using the custom plugin."""
    
    def __init__(self):
        self.manager = get_plugin_manager()
        self.manager.register_plugin(SwiftPlugin)
    
    def analyze_swift_project(self, project_path: str):
        """Analyze a Swift project structure."""
        from pathlib import Path
        
        swift_files = list(Path(project_path).rglob("*.swift"))
        print(f"Found {len(swift_files)} Swift files\n")
        
        stats = {
            'total_chunks': 0,
            'by_type': {},
            'access_levels': {},
            'protocols': [],
            'extensions': []
        }
        
        for file_path in swift_files:
            chunks = chunk_file(str(file_path), "swift")
            stats['total_chunks'] += len(chunks)
            
            for chunk in chunks:
                # Count by type
                stats['by_type'][chunk.node_type] = stats['by_type'].get(chunk.node_type, 0) + 1
                
                # Analyze access levels
                for level in ['public', 'internal', 'fileprivate', 'private']:
                    if chunk.content.strip().startswith(f"{level} "):
                        stats['access_levels'][level] = stats['access_levels'].get(level, 0) + 1
                
                # Collect protocols and extensions
                if chunk.node_type == "protocol_declaration":
                    stats['protocols'].append(self._extract_name(chunk))
                elif chunk.node_type == "extension_declaration":
                    stats['extensions'].append(self._extract_name(chunk))
        
        # Print analysis
        print("Swift Project Analysis:")
        print("=" * 50)
        print(f"Total code chunks: {stats['total_chunks']}")
        print("\nChunk types:")
        for node_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {node_type}: {count}")
        
        print("\nAccess levels:")
        for level, count in stats['access_levels'].items():
            print(f"  {level}: {count}")
        
        print(f"\nProtocols defined: {len(stats['protocols'])}")
        print(f"Extensions: {len(stats['extensions'])}")
        
        return stats
    
    def _extract_name(self, chunk):
        """Extract name from chunk content."""
        first_line = chunk.content.split('\n')[0]
        match = re.search(r'(?:protocol|extension)\s+(\w+)', first_line)
        return match.group(1) if match else "Unknown"

# Register and use the plugin
analyzer = SwiftProjectAnalyzer()

# Analyze a Swift project
if Path("MySwiftProject").exists():
    stats = analyzer.analyze_swift_project("MySwiftProject")
```

### Plugin with Custom Chunk Rules

Create a plugin with advanced chunking rules.

```python
from chunker.languages.plugin_base import LanguagePlugin
from chunker.languages.base import ChunkRule
from chunker import get_plugin_manager
import re

class AdvancedPythonPlugin(LanguagePlugin):
    """Enhanced Python plugin with custom chunk rules."""
    
    @property
    def language_name(self) -> str:
        return "python_advanced"
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {".py"}
    
    @property
    def default_chunk_types(self) -> Set[str]:
        # Standard Python chunk types
        return {
            "function_definition",
            "class_definition",
            "async_function_definition",
            "decorated_definition"
        }
    
    def get_chunk_rules(self) -> list[ChunkRule]:
        """Define custom chunking rules."""
        return [
            # Extract FastAPI endpoints
            ChunkRule(
                name="fastapi_endpoint",
                node_type="decorated_definition",
                pattern=r'@(app|router)\.(get|post|put|delete|patch)',
                priority=100,
                metadata_extractor=self._extract_endpoint_metadata
            ),
            
            # Extract Django views
            ChunkRule(
                name="django_view",
                node_type="class_definition",
                pattern=r'class\s+\w+\s*\(.*View.*\)',
                priority=90
            ),
            
            # Extract test classes and functions
            ChunkRule(
                name="test_case",
                node_type="function_definition",
                pattern=r'def\s+test_\w+',
                priority=80,
                parent_type="class_definition"
            ),
            
            # Extract dataclasses
            ChunkRule(
                name="dataclass",
                node_type="decorated_definition",
                pattern=r'@dataclass',
                priority=85
            ),
            
            # Extract Pydantic models
            ChunkRule(
                name="pydantic_model",
                node_type="class_definition",
                pattern=r'class\s+\w+\s*\(.*BaseModel.*\)',
                priority=85
            )
        ]
    
    def _extract_endpoint_metadata(self, chunk) -> dict:
        """Extract metadata from FastAPI endpoints."""
        content = chunk.content
        metadata = {}
        
        # Extract HTTP method and path
        match = re.search(r'@(?:app|router)\.(\w+)\(["\']([^"\']*)["\'\]', content)
        if match:
            metadata['http_method'] = match.group(1).upper()
            metadata['path'] = match.group(2)
        
        # Extract response model
        response_match = re.search(r'response_model=([\w\.]+)', content)
        if response_match:
            metadata['response_model'] = response_match.group(1)
        
        # Extract dependencies
        deps = re.findall(r'Depends\(([\w\.]+)\)', content)
        if deps:
            metadata['dependencies'] = deps
        
        return metadata
    
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        """Extract name with special handling for decorators."""
        content = source[node.start_byte:node.end_byte].decode('utf-8')
        
        # For decorated functions, skip decorators
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith('def ') or line.strip().startswith('class '):
                match = re.search(r'(?:def|class)\s+(\w+)', line)
                if match:
                    return match.group(1)
        
        return None

# Example: Analyze a FastAPI project
class FastAPIAnalyzer:
    """Analyze FastAPI projects with custom rules."""
    
    def __init__(self):
        self.manager = get_plugin_manager()
        self.manager.register_plugin(AdvancedPythonPlugin)
    
    def analyze_api_structure(self, project_path: str):
        """Analyze FastAPI project structure."""
        from pathlib import Path
        from chunker import chunk_file
        
        endpoints = []
        models = []
        
        for py_file in Path(project_path).rglob("*.py"):
            chunks = chunk_file(str(py_file), "python_advanced")
            
            for chunk in chunks:
                if hasattr(chunk, 'metadata'):
                    if 'http_method' in chunk.metadata:
                        endpoints.append({
                            'file': str(py_file),
                            'name': chunk.content.split('\n')[0],
                            'method': chunk.metadata['http_method'],
                            'path': chunk.metadata.get('path', 'Unknown'),
                            'response_model': chunk.metadata.get('response_model'),
                            'dependencies': chunk.metadata.get('dependencies', [])
                        })
                    elif chunk.node_type == "pydantic_model":
                        models.append({
                            'file': str(py_file),
                            'name': self._extract_class_name(chunk),
                            'fields': self._extract_model_fields(chunk)
                        })
        
        # Generate API documentation
        print("FastAPI Project Structure:")
        print("=" * 60)
        print(f"\nEndpoints ({len(endpoints)}):")
        for ep in sorted(endpoints, key=lambda x: (x['path'], x['method'])):
            print(f"  {ep['method']:6} {ep['path']:30} -> {Path(ep['file']).name}")
            if ep['response_model']:
                print(f"         Response: {ep['response_model']}")
        
        print(f"\nModels ({len(models)}):")
        for model in models:
            print(f"  {model['name']} ({len(model['fields'])} fields)")
        
        return {'endpoints': endpoints, 'models': models}
    
    def _extract_class_name(self, chunk):
        """Extract class name from chunk."""
        match = re.search(r'class\s+(\w+)', chunk.content)
        return match.group(1) if match else "Unknown"
    
    def _extract_model_fields(self, chunk):
        """Extract Pydantic model fields."""
        fields = []
        lines = chunk.content.split('\n')
        for line in lines[1:]:  # Skip class definition
            if ':' in line and not line.strip().startswith('#'):
                field_match = re.match(r'\s*(\w+)\s*:\s*([^=]+)', line)
                if field_match:
                    fields.append({
                        'name': field_match.group(1),
                        'type': field_match.group(2).strip()
                    })
        return fields

# Usage
analyzer = FastAPIAnalyzer()
if Path("fastapi_project").exists():
    api_structure = analyzer.analyze_api_structure("fastapi_project")
```

## Export Format Recipes

### Multi-Format Export Pipeline

Export chunks to multiple formats with transformations.

```python
from chunker import chunk_file, chunk_directory_parallel
from chunker.export import JSONExporter, JSONLExporter, SchemaType
from chunker.exporters import ParquetExporter
from pathlib import Path
import pandas as pd
from typing import List, Dict, Any
import json

class MultiFormatExporter:
    """Export chunks to multiple formats with transformations."""
    
    def __init__(self):
        self.exporters = {
            'json': JSONExporter(schema_type=SchemaType.NESTED),
            'jsonl': JSONLExporter(),
            'parquet': ParquetExporter(compression="snappy")
        }
    
    def export_with_enrichment(self, chunks: List, base_name: str):
        """Export chunks with additional metadata and transformations."""
        # Enrich chunks with additional metadata
        enriched_chunks = self._enrich_chunks(chunks)
        
        # Export to different formats
        outputs = {}
        
        # JSON with nested structure
        json_path = f"{base_name}_nested.json"
        self.exporters['json'].export(enriched_chunks, json_path)
        outputs['json'] = json_path
        
        # JSONL for streaming
        jsonl_path = f"{base_name}_stream.jsonl"
        self.exporters['jsonl'].export(enriched_chunks, jsonl_path)
        outputs['jsonl'] = jsonl_path
        
        # Parquet for analytics
        parquet_path = f"{base_name}_analytics.parquet"
        self.exporters['parquet'].export(enriched_chunks, parquet_path)
        outputs['parquet'] = parquet_path
        
        # Custom CSV export
        csv_path = f"{base_name}_summary.csv"
        self._export_to_csv(enriched_chunks, csv_path)
        outputs['csv'] = csv_path
        
        # Generate summary report
        self._generate_summary_report(enriched_chunks, outputs)
        
        return outputs
    
    def _enrich_chunks(self, chunks: List) -> List:
        """Add additional metadata to chunks."""
        import hashlib
        from datetime import datetime
        
        enriched = []
        for i, chunk in enumerate(chunks):
            # Create enriched chunk (preserve original)
            enriched_chunk = chunk
            
            # Add metadata
            enriched_chunk.metadata = getattr(chunk, 'metadata', {})
            enriched_chunk.metadata.update({
                'index': i,
                'hash': hashlib.md5(chunk.content.encode()).hexdigest(),
                'size_bytes': len(chunk.content.encode('utf-8')),
                'line_count': chunk.end_line - chunk.start_line + 1,
                'complexity_estimate': self._estimate_complexity(chunk),
                'extracted_at': datetime.now().isoformat(),
                'has_docstring': self._has_docstring(chunk),
                'dependencies': self._extract_dependencies(chunk)
            })
            
            enriched.append(enriched_chunk)
        
        return enriched
    
    def _estimate_complexity(self, chunk) -> int:
        """Estimate chunk complexity."""
        complexity = 1
        keywords = ['if ', 'for ', 'while ', 'try:', 'except:', 'elif ', 'else:']
        for keyword in keywords:
            complexity += chunk.content.count(keyword)
        return complexity
    
    def _has_docstring(self, chunk) -> bool:
        """Check if chunk has a docstring."""
        return '"""' in chunk.content or "'''" in chunk.content
    
    def _extract_dependencies(self, chunk) -> List[str]:
        """Extract imports/dependencies from chunk."""
        dependencies = []
        if chunk.language == "python":
            import re
            imports = re.findall(r'(?:from|import)\s+([\w\.]+)', chunk.content)
            dependencies.extend(imports)
        return list(set(dependencies))
    
    def _export_to_csv(self, chunks: List, output_path: str):
        """Export summary to CSV."""
        data = []
        for chunk in chunks:
            data.append({
                'file': Path(chunk.file_path).name,
                'type': chunk.node_type,
                'name': chunk.content.split('\n')[0][:50] + '...',
                'start_line': chunk.start_line,
                'end_line': chunk.end_line,
                'lines': chunk.end_line - chunk.start_line + 1,
                'complexity': chunk.metadata.get('complexity_estimate', 0),
                'has_docstring': chunk.metadata.get('has_docstring', False)
            })
        
        df = pd.DataFrame(data)
        df.to_csv(output_path, index=False)
    
    def _generate_summary_report(self, chunks: List, outputs: Dict[str, str]):
        """Generate a summary report of the export."""
        report = {
            'export_summary': {
                'total_chunks': len(chunks),
                'total_lines': sum(c.end_line - c.start_line + 1 for c in chunks),
                'languages': list(set(c.language for c in chunks)),
                'chunk_types': dict(pd.Series([c.node_type for c in chunks]).value_counts()),
                'files_processed': len(set(c.file_path for c in chunks))
            },
            'complexity_stats': {
                'avg_complexity': sum(c.metadata.get('complexity_estimate', 0) for c in chunks) / len(chunks),
                'max_complexity': max(c.metadata.get('complexity_estimate', 0) for c in chunks),
                'complex_chunks': sum(1 for c in chunks if c.metadata.get('complexity_estimate', 0) > 10)
            },
            'output_files': outputs,
            'file_sizes': {}
        }
        
        # Add file sizes
        for format_name, path in outputs.items():
            if Path(path).exists():
                size_mb = Path(path).stat().st_size / (1024 * 1024)
                report['file_sizes'][format_name] = f"{size_mb:.2f} MB"
        
        # Save report
        report_path = f"{Path(outputs['json']).stem}_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\nExport Summary:")
        print("=" * 50)
        print(f"Total chunks: {report['export_summary']['total_chunks']}")
        print(f"Total lines: {report['export_summary']['total_lines']}")
        print(f"Average complexity: {report['complexity_stats']['avg_complexity']:.1f}")
        print("\nOutput files:")
        for format_name, path in outputs.items():
            size = report['file_sizes'].get(format_name, 'Unknown')
            print(f"  {format_name}: {path} ({size})")
        print(f"\nReport saved to: {report_path}")

# Usage example
class ProjectExporter:
    """Export entire projects with multiple formats."""
    
    def __init__(self):
        self.exporter = MultiFormatExporter()
    
    def export_project(self, project_path: str, output_dir: str):
        """Export all code from a project."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Process project in parallel
        results = chunk_directory_parallel(
            project_path,
            "python",  # Adjust for your project
            pattern="**/*.py",
            max_workers=8
        )
        
        # Flatten results
        all_chunks = []
        for file_chunks in results.values():
            all_chunks.extend(file_chunks)
        
        # Export with enrichment
        base_name = str(output_path / "project_chunks")
        outputs = self.exporter.export_with_enrichment(all_chunks, base_name)
        
        # Create partitioned Parquet for large datasets
        if len(all_chunks) > 1000:
            self._create_partitioned_export(all_chunks, output_path)
        
        return outputs
    
    def _create_partitioned_export(self, chunks: List, output_dir: Path):
        """Create partitioned Parquet export for large datasets."""
        exporter = ParquetExporter()
        
        # Export with partitioning by language and node type
        partitioned_dir = output_dir / "partitioned_chunks"
        exporter.export_partitioned(
            chunks,
            str(partitioned_dir),
            partition_cols=["language", "node_type"]
        )
        
        print(f"\nCreated partitioned export in: {partitioned_dir}")
        print("Partitions:")
        for partition in partitioned_dir.rglob("*.parquet"):
            rel_path = partition.relative_to(partitioned_dir)
            print(f"  {rel_path}")

# Usage
exporter = ProjectExporter()

# Export a project
if Path("my_project").exists():
    outputs = exporter.export_project("my_project", "exports")
    
    # Read back the Parquet file for analysis
    df = pd.read_parquet(outputs['parquet'])
    print(f"\nDataFrame shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
```

### Custom Export Format for Documentation

Create a custom Markdown export for documentation generation.

```python
from chunker import chunk_file, CodeChunk
from pathlib import Path
from typing import List, Dict
import re

class MarkdownDocExporter:
    """Export chunks as structured Markdown documentation."""
    
    def __init__(self):
        self.toc_entries = []
    
    def export_to_markdown(self, chunks: List[CodeChunk], output_path: str, 
                          project_name: str = "Project"):
        """Export chunks as formatted Markdown documentation."""
        # Group chunks by file
        chunks_by_file = self._group_by_file(chunks)
        
        # Generate documentation
        lines = [
            f"# {project_name} Code Documentation\n",
            "*Auto-generated documentation from source code*\n",
            "## Table of Contents\n"
        ]
        
        # Generate TOC
        toc_lines = []
        for file_path, file_chunks in sorted(chunks_by_file.items()):
            file_name = Path(file_path).name
            anchor = self._make_anchor(file_name)
            toc_lines.append(f"- [{file_name}](#{anchor})")
            
            # Add sub-items
            for chunk in file_chunks:
                if chunk.node_type in ["class_definition", "function_definition"]:
                    name = self._extract_name(chunk)
                    if name:
                        sub_anchor = self._make_anchor(f"{file_name}-{name}")
                        toc_lines.append(f"  - [{name}](#{sub_anchor})")
        
        lines.extend(toc_lines)
        lines.append("\n---\n")
        
        # Generate documentation for each file
        for file_path, file_chunks in sorted(chunks_by_file.items()):
            lines.extend(self._generate_file_doc(file_path, file_chunks))
        
        # Add index
        lines.extend(self._generate_index(chunks))
        
        # Write to file
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
        
        print(f"Documentation exported to: {output_path}")
    
    def _group_by_file(self, chunks: List[CodeChunk]) -> Dict[str, List[CodeChunk]]:
        """Group chunks by source file."""
        grouped = {}
        for chunk in chunks:
            if chunk.file_path not in grouped:
                grouped[chunk.file_path] = []
            grouped[chunk.file_path].append(chunk)
        return grouped
    
    def _generate_file_doc(self, file_path: str, chunks: List[CodeChunk]) -> List[str]:
        """Generate documentation for a single file."""
        lines = []
        file_name = Path(file_path).name
        
        # File header
        lines.append(f"## {file_name}")
        lines.append(f"*{file_path}*\n")
        
        # File summary
        summary = self._generate_file_summary(chunks)
        lines.append(summary)
        lines.append("")
        
        # Document each chunk
        for chunk in chunks:
            if chunk.node_type in ["class_definition", "function_definition", 
                                  "method_definition"]:
                lines.extend(self._document_chunk(chunk, file_name))
        
        lines.append("---\n")
        return lines
    
    def _generate_file_summary(self, chunks: List[CodeChunk]) -> str:
        """Generate a summary of the file contents."""
        counts = {}
        for chunk in chunks:
            counts[chunk.node_type] = counts.get(chunk.node_type, 0) + 1
        
        summary_parts = []
        if counts.get('class_definition', 0) > 0:
            summary_parts.append(f"{counts['class_definition']} classes")
        if counts.get('function_definition', 0) > 0:
            summary_parts.append(f"{counts['function_definition']} functions")
        
        return f"This file contains {', '.join(summary_parts)}." if summary_parts else "This file contains code chunks."
    
    def _document_chunk(self, chunk: CodeChunk, file_name: str) -> List[str]:
        """Document a single code chunk."""
        lines = []
        name = self._extract_name(chunk)
        
        if not name:
            return lines
        
        # Section header
        level = "###" if chunk.parent_context else "###"
        anchor = self._make_anchor(f"{file_name}-{name}")
        lines.append(f"{level} {name}")
        
        # Metadata
        metadata = []
        if chunk.parent_context:
            metadata.append(f"*Parent: {chunk.parent_context}*")
        metadata.append(f"*Lines {chunk.start_line}-{chunk.end_line}*")
        if metadata:
            lines.append(" | ".join(metadata))
        lines.append("")
        
        # Extract docstring
        docstring = self._extract_docstring(chunk)
        if docstring:
            lines.append(f"> {docstring}")
            lines.append("")
        
        # Function signature
        signature = self._extract_signature(chunk)
        if signature:
            lines.append("```" + chunk.language)
            lines.append(signature)
            lines.append("```")
            lines.append("")
        
        # Extract parameters (for functions)
        if chunk.node_type in ["function_definition", "method_definition"]:
            params = self._extract_parameters(chunk)
            if params:
                lines.append("**Parameters:**")
                for param in params:
                    lines.append(f"- `{param['name']}`: {param.get('type', 'Any')}")
                lines.append("")
        
        # Add any additional metadata
        if hasattr(chunk, 'metadata') and chunk.metadata:
            lines.append("**Metadata:**")
            for key, value in chunk.metadata.items():
                lines.append(f"- {key}: {value}")
            lines.append("")
        
        return lines
    
    def _generate_index(self, chunks: List[CodeChunk]) -> List[str]:
        """Generate an alphabetical index."""
        lines = ["\n## Index\n"]
        
        # Collect all named chunks
        index_entries = []
        for chunk in chunks:
            name = self._extract_name(chunk)
            if name:
                index_entries.append({
                    'name': name,
                    'type': chunk.node_type,
                    'file': Path(chunk.file_path).name,
                    'line': chunk.start_line
                })
        
        # Sort alphabetically
        index_entries.sort(key=lambda x: x['name'].lower())
        
        # Group by first letter
        current_letter = None
        for entry in index_entries:
            first_letter = entry['name'][0].upper()
            if first_letter != current_letter:
                current_letter = first_letter
                lines.append(f"\n### {current_letter}")
            
            lines.append(f"- **{entry['name']}** ({entry['type']}) - "
                        f"{entry['file']}:{entry['line']}")
        
        return lines
    
    def _extract_name(self, chunk: CodeChunk) -> str:
        """Extract the name of a function or class."""
        first_line = chunk.content.split('\n')[0]
        
        patterns = {
            'python': r'(?:def|class)\s+(\w+)',
            'javascript': r'(?:function|class|const|let|var)\s+(\w+)',
            'rust': r'(?:fn|struct|impl|trait)\s+(\w+)'
        }
        
        pattern = patterns.get(chunk.language, r'(\w+)')
        match = re.search(pattern, first_line)
        
        return match.group(1) if match else ""
    
    def _extract_docstring(self, chunk: CodeChunk) -> str:
        """Extract docstring from chunk."""
        lines = chunk.content.split('\n')
        
        for i, line in enumerate(lines[1:], 1):
            if '"""' in line or "'''" in line:
                # Simple single-line docstring
                if line.count('"""') == 2 or line.count("'''") == 2:
                    return line.strip().strip('"""').strip("'''")
                # Multi-line docstring
                quote = '"""' if '"""' in line else "'''"
                docstring_lines = [line.replace(quote, '').strip()]
                for j in range(i + 1, len(lines)):
                    if quote in lines[j]:
                        docstring_lines.append(lines[j].replace(quote, '').strip())
                        break
                    docstring_lines.append(lines[j].strip())
                return ' '.join(docstring_lines)
        
        return ""
    
    def _extract_signature(self, chunk: CodeChunk) -> str:
        """Extract function/class signature."""
        lines = chunk.content.split('\n')
        signature_lines = []
        
        for line in lines:
            signature_lines.append(line)
            if ':' in line and not line.strip().endswith(','):
                break
        
        return '\n'.join(signature_lines)
    
    def _extract_parameters(self, chunk: CodeChunk) -> List[Dict[str, str]]:
        """Extract function parameters."""
        params = []
        
        if chunk.language == "python":
            # Extract from function signature
            match = re.search(r'def\s+\w+\s*\(([^)]*)\)', chunk.content)
            if match:
                param_str = match.group(1)
                for param in param_str.split(','):
                    param = param.strip()
                    if param and param != 'self':
                        if ':' in param:
                            name, type_hint = param.split(':', 1)
                            params.append({'name': name.strip(), 'type': type_hint.strip()})
                        else:
                            params.append({'name': param, 'type': 'Any'})
        
        return params
    
    def _make_anchor(self, text: str) -> str:
        """Create a valid markdown anchor from text."""
        return re.sub(r'[^a-zA-Z0-9-]', '-', text.lower())

# Usage
exporter = MarkdownDocExporter()

# Export documentation for a project
from chunker import chunk_directory_parallel

results = chunk_directory_parallel("src/", "python", pattern="**/*.py")
all_chunks = []
for chunks in results.values():
    all_chunks.extend(chunks)

exporter.export_to_markdown(
    all_chunks,
    "project_documentation.md",
    project_name="My Python Project"
)
```

## AI/ML Integration

### Generate Code Embeddings for Semantic Search

Create vector embeddings for semantic code search.

```python
from chunker.chunker import chunk_file
from chunker.parser import list_languages
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import pickle
from pathlib import Path
from typing import List, Dict
import json

class CodeEmbeddingSystem:
    """Semantic code search using embeddings."""
    
    def __init__(self, model_name='microsoft/codebert-base'):
        # Use a code-specific model if available
        try:
            self.model = SentenceTransformer(model_name)
        except:
            # Fallback to general model
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.chunks = []
        self.embeddings = None
        self.index = None
    
    def index_codebase(self, directory):
        """Index all code in directory with embeddings."""
        print("Indexing codebase...")
        
        # Collect all chunks
        for lang in ['python', 'javascript', 'rust']:
            ext_map = {'python': '.py', 'javascript': '.js', 'rust': '.rs'}
            pattern = f"*{ext_map[lang]}"
            
            for file_path in Path(directory).rglob(pattern):
                if self._should_skip(file_path):
                    continue
                    
                try:
                    chunks = chunk_file(str(file_path), lang)
                    self.chunks.extend(chunks)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
        
        print(f"Found {len(self.chunks)} code chunks")
        
        # Generate embeddings
        print("Generating embeddings...")
        texts = [self._create_embedding_text(chunk) for chunk in self.chunks]
        self.embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # Create FAISS index
        dimension = self.embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(self.embeddings.astype('float32'))
        
        print(f"Indexed {len(self.chunks)} chunks with {dimension}-dimensional embeddings")
    
    def _should_skip(self, file_path):
        """Check if file should be skipped."""
        skip_patterns = ['__pycache__', 'node_modules', '.git', 'venv', 'test_']
        return any(pattern in str(file_path) for pattern in skip_patterns)
    
    def _create_embedding_text(self, chunk):
        """Create text representation for embedding."""
        # Combine context with code
        parts = []
        
        # Add metadata
        parts.append(f"Language: {chunk.language}")
        parts.append(f"Type: {chunk.node_type}")
        
        if chunk.parent_context:
            parts.append(f"Context: {chunk.parent_context}")
        
        # Add function/class name
        first_line = chunk.content.split('\n')[0]
        parts.append(f"Signature: {first_line}")
        
        # Add docstring if present
        docstring = self._extract_docstring(chunk.content)
        if docstring:
            parts.append(f"Description: {docstring}")
        
        # Add simplified code
        code_summary = self._summarize_code(chunk.content)
        parts.append(f"Code: {code_summary}")
        
        return '\n'.join(parts)
    
    def _extract_docstring(self, code):
        """Extract docstring from code."""
        lines = code.split('\n')
        for i, line in enumerate(lines[1:4]):
            if '"""' in line or "'''" in line:
                return line.strip().strip('"""').strip("'''")
        return None
    
    def _summarize_code(self, code):
        """Create a summary of the code for embedding."""
        lines = code.split('\n')
        
        # Keep important lines (function calls, returns, etc.)
        important_lines = []
        keywords = ['return', 'yield', 'raise', 'import', 'from', 'class', 'def']
        
        for line in lines[:20]:  # Limit to first 20 lines
            line = line.strip()
            if any(keyword in line for keyword in keywords):
                important_lines.append(line)
        
        return ' '.join(important_lines[:10])  # Limit summary length
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search for code similar to query."""
        if self.index is None:
            raise ValueError("Index not built. Call index_codebase() first.")
        
        # Encode query
        query_embedding = self.model.encode([query])
        
        # Search
        distances, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        # Build results
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                results.append({
                    'chunk': chunk,
                    'distance': float(distance),
                    'similarity': 1 / (1 + float(distance)),  # Convert distance to similarity
                    'preview': chunk.content.split('\n')[0]
                })
        
        return results
    
    def find_similar_functions(self, chunk_index: int, top_k: int = 5):
        """Find functions similar to a given chunk."""
        if chunk_index >= len(self.embeddings):
            raise ValueError("Invalid chunk index")
        
        # Get embedding for the chunk
        query_embedding = self.embeddings[chunk_index].reshape(1, -1)
        
        # Search (excluding the query itself)
        distances, indices = self.index.search(query_embedding.astype('float32'), top_k + 1)
        
        # Build results (skip first result which is the query itself)
        results = []
        for idx, distance in zip(indices[0][1:], distances[0][1:]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                results.append({
                    'chunk': chunk,
                    'distance': float(distance),
                    'similarity': 1 / (1 + float(distance))
                })
        
        return results
    
    def save(self, path: str):
        """Save the embedding system."""
        save_path = Path(path)
        save_path.mkdir(exist_ok=True)
        
        # Save chunks
        with open(save_path / "chunks.pkl", "wb") as f:
            pickle.dump(self.chunks, f)
        
        # Save embeddings
        np.save(save_path / "embeddings.npy", self.embeddings)
        
        # Save FAISS index
        faiss.write_index(self.index, str(save_path / "index.faiss"))
        
        # Save metadata
        metadata = {
            'num_chunks': len(self.chunks),
            'embedding_dim': self.embeddings.shape[1],
            'model_name': self.model._modules['0'].auto_model.name_or_path
        }
        with open(save_path / "metadata.json", "w") as f:
            json.dump(metadata, f)
    
    def load(self, path: str):
        """Load saved embedding system."""
        load_path = Path(path)
        
        # Load chunks
        with open(load_path / "chunks.pkl", "rb") as f:
            self.chunks = pickle.load(f)
        
        # Load embeddings
        self.embeddings = np.load(load_path / "embeddings.npy")
        
        # Load FAISS index
        self.index = faiss.read_index(str(load_path / "index.faiss"))
        
        print(f"Loaded {len(self.chunks)} chunks")

# Usage example
embedding_system = CodeEmbeddingSystem()

# Index your codebase
embedding_system.index_codebase("./src")

# Search for code
results = embedding_system.search("function that handles user authentication")

print("Search Results:")
for i, result in enumerate(results[:5]):
    chunk = result['chunk']
    print(f"\n{i+1}. {chunk.file_path}:{chunk.start_line}")
    print(f"   Similarity: {result['similarity']:.3f}")
    print(f"   Type: {chunk.node_type}")
    print(f"   Preview: {result['preview']}")

# Find similar functions
chunk_idx = 42  # Example chunk
similar = embedding_system.find_similar_functions(chunk_idx, top_k=3)
print(f"\nFunctions similar to chunk {chunk_idx}:")
for result in similar:
    chunk = result['chunk']
    print(f"  - {chunk.file_path}:{chunk.start_line} (similarity: {result['similarity']:.3f})")

# Save for later use
embedding_system.save("./code_embeddings")
```

### Generate Training Data for Code Models

Create datasets for training code understanding models.

```python
from chunker.chunker import chunk_file
from pathlib import Path
import json
import random
from typing import List, Dict, Tuple
import re

class CodeDatasetGenerator:
    """Generate training datasets from code."""
    
    def __init__(self):
        self.data = []
    
    def create_function_naming_dataset(self, directory):
        """Create dataset for function name prediction."""
        dataset = []
        
        for py_file in Path(directory).rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                chunks = chunk_file(str(py_file), "python")
                
                for chunk in chunks:
                    if chunk.node_type == "function_definition":
                        # Extract function name
                        name = self._extract_function_name(chunk.content)
                        if not name or name.startswith('_'):
                            continue
                        
                        # Remove function name from code
                        anonymized_code = self._anonymize_function(chunk.content, name)
                        
                        dataset.append({
                            'input': anonymized_code,
                            'target': name,
                            'metadata': {
                                'file': str(py_file),
                                'line': chunk.start_line,
                                'parent': chunk.parent_context
                            }
                        })
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
        
        return dataset
    
    def create_docstring_generation_dataset(self, directory):
        """Create dataset for docstring generation."""
        dataset = []
        
        for py_file in Path(directory).rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                chunks = chunk_file(str(py_file), "python")
                
                for chunk in chunks:
                    if chunk.node_type in ["function_definition", "class_definition"]:
                        docstring = self._extract_docstring(chunk.content)
                        if not docstring:
                            continue
                        
                        # Remove docstring from code
                        code_without_docstring = self._remove_docstring(chunk.content)
                        
                        dataset.append({
                            'input': code_without_docstring,
                            'target': docstring,
                            'metadata': {
                                'file': str(py_file),
                                'line': chunk.start_line,
                                'type': chunk.node_type
                            }
                        })
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
        
        return dataset
    
    def create_code_completion_dataset(self, directory, context_lines=10):
        """Create dataset for code completion."""
        dataset = []
        
        for py_file in Path(directory).rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                chunks = chunk_file(str(py_file), "python")
                
                for chunk in chunks:
                    if chunk.node_type == "function_definition":
                        # Create multiple completion examples from the function
                        func_lines = chunk.content.split('\n')
                        
                        for i in range(2, len(func_lines) - 1):
                            # Get context (previous lines)
                            start_idx = max(0, i - context_lines)
                            context = '\n'.join(func_lines[start_idx:i])
                            
                            # Get completion target (current line)
                            target = func_lines[i].strip()
                            
                            if target and not target.startswith('#'):
                                dataset.append({
                                    'input': context,
                                    'target': target,
                                    'metadata': {
                                        'file': str(py_file),
                                        'function_line': chunk.start_line,
                                        'completion_line': chunk.start_line + i
                                    }
                                })
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
        
        return dataset
    
    def create_bug_detection_dataset(self, directory):
        """Create synthetic bug detection dataset."""
        dataset = []
        
        for py_file in Path(directory).rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                chunks = chunk_file(str(py_file), "python")
                
                for chunk in chunks:
                    if chunk.node_type == "function_definition":
                        # Original (correct) code
                        dataset.append({
                            'code': chunk.content,
                            'has_bug': False,
                            'bug_type': None,
                            'metadata': {
                                'file': str(py_file),
                                'line': chunk.start_line
                            }
                        })
                        
                        # Create buggy versions
                        buggy_versions = self._introduce_bugs(chunk.content)
                        for bug_type, buggy_code in buggy_versions:
                            if buggy_code != chunk.content:
                                dataset.append({
                                    'code': buggy_code,
                                    'has_bug': True,
                                    'bug_type': bug_type,
                                    'metadata': {
                                        'file': str(py_file),
                                        'line': chunk.start_line,
                                        'original': False
                                    }
                                })
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
        
        return dataset
    
    def _extract_function_name(self, code):
        """Extract function name from code."""
        match = re.search(r'def\s+(\w+)', code)
        return match.group(1) if match else None
    
    def _anonymize_function(self, code, name):
        """Replace function name with placeholder."""
        return re.sub(rf'\bdef\s+{name}\b', 'def <FUNCTION_NAME>', code, count=1)
    
    def _extract_docstring(self, code):
        """Extract docstring from code."""
        lines = code.split('\n')
        in_docstring = False
        docstring_lines = []
        quote_style = None
        
        for line in lines[1:]:  # Skip function/class definition
            stripped = line.strip()
            
            if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                quote_style = '"""' if stripped.startswith('"""') else "'''"
                in_docstring = True
                
                # Check for single-line docstring
                if stripped.count(quote_style) == 2:
                    return stripped.strip(quote_style)
                else:
                    docstring_lines.append(stripped.replace(quote_style, '', 1))
            elif in_docstring:
                if quote_style in stripped:
                    docstring_lines.append(stripped.replace(quote_style, '', 1))
                    break
                else:
                    docstring_lines.append(stripped)
        
        return '\n'.join(docstring_lines).strip() if docstring_lines else None
    
    def _remove_docstring(self, code):
        """Remove docstring from code."""
        lines = code.split('\n')
        result_lines = [lines[0]]  # Keep function/class definition
        
        in_docstring = False
        quote_style = None
        
        for line in lines[1:]:
            stripped = line.strip()
            
            if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                quote_style = '"""' if stripped.startswith('"""') else "'''"
                in_docstring = True
                
                # Check for single-line docstring
                if stripped.count(quote_style) == 2:
                    continue
            elif in_docstring and quote_style in stripped:
                in_docstring = False
                continue
            elif not in_docstring:
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _introduce_bugs(self, code):
        """Introduce various types of bugs into code."""
        bugs = []
        
        # Off-by-one error
        off_by_one = re.sub(r'range\((\w+)\)', r'range(\1 + 1)', code)
        if off_by_one != code:
            bugs.append(('off_by_one', off_by_one))
        
        # Wrong operator
        wrong_op = code.replace('==', '=')  # Dangerous but for synthetic data
        if wrong_op != code:
            bugs.append(('wrong_operator', wrong_op))
        
        # Missing return
        if 'return' in code:
            no_return = re.sub(r'return\s+.*$', 'pass', code, flags=re.MULTILINE)
            if no_return != code:
                bugs.append(('missing_return', no_return))
        
        return bugs
    
    def save_dataset(self, dataset: List[Dict], output_path: str, split_ratio=0.8):
        """Save dataset with train/val split."""
        # Shuffle
        random.shuffle(dataset)
        
        # Split
        split_idx = int(len(dataset) * split_ratio)
        train_data = dataset[:split_idx]
        val_data = dataset[split_idx:]
        
        # Save
        base_path = Path(output_path)
        base_path.mkdir(exist_ok=True)
        
        with open(base_path / "train.jsonl", "w") as f:
            for item in train_data:
                f.write(json.dumps(item) + "\n")
        
        with open(base_path / "val.jsonl", "w") as f:
            for item in val_data:
                f.write(json.dumps(item) + "\n")
        
        # Save statistics
        stats = {
            'total_examples': len(dataset),
            'train_examples': len(train_data),
            'val_examples': len(val_data),
            'example_fields': list(dataset[0].keys()) if dataset else []
        }
        
        with open(base_path / "stats.json", "w") as f:
            json.dump(stats, f, indent=2)
        
        print(f"Dataset saved to {output_path}")
        print(f"  Train: {len(train_data)} examples")
        print(f"  Val: {len(val_data)} examples")

# Usage
generator = CodeDatasetGenerator()

# Generate different datasets
naming_dataset = generator.create_function_naming_dataset("./src")
generator.save_dataset(naming_dataset, "./datasets/function_naming")

docstring_dataset = generator.create_docstring_generation_dataset("./src")
generator.save_dataset(docstring_dataset, "./datasets/docstring_generation")

completion_dataset = generator.create_code_completion_dataset("./src")
generator.save_dataset(completion_dataset, "./datasets/code_completion")

bug_dataset = generator.create_bug_detection_dataset("./src")
generator.save_dataset(bug_dataset, "./datasets/bug_detection")
```

## Performance Optimization

### Using New Parallel Processing APIs

Leverage the new parallel processing APIs for maximum performance.

```python
from chunker import (
    chunk_files_parallel,
    chunk_directory_parallel,
    ASTCache
)
from pathlib import Path
import time

class OptimizedBatchProcessor:
    """High-performance batch processor using new APIs."""
    
    def __init__(self):
        # Configure for maximum performance
        self.cache = ASTCache(max_size=1000)
    
    def process_large_project(self, project_root: str):
        """Process a large project efficiently."""
        start_time = time.time()
        
        # Process by language for better cache utilization
        languages = {
            'python': '**/*.py',
            'javascript': '**/*.js',
            'rust': '**/*.rs'
        }
        
        all_results = {}
        total_chunks = 0
        
        for language, pattern in languages.items():
            print(f"\nProcessing {language} files...")
            
            # Use the new parallel directory API
            results = chunk_directory_parallel(
                project_root,
                language,
                pattern=pattern,
                max_workers=8,  # Adjust based on CPU
                show_progress=True
            )
            
            # Aggregate results
            language_chunks = sum(len(chunks) for chunks in results.values())
            total_chunks += language_chunks
            all_results.update(results)
            
            print(f"  Processed {len(results)} {language} files")
            print(f"  Found {language_chunks} chunks")
            
            # Show cache performance
            cache_stats = self.cache.get_stats()
            print(f"  Cache hit rate: {cache_stats['hit_rate']:.1%}")
        
        # Summary
        duration = time.time() - start_time
        print(f"\nTotal Processing Summary:")
        print(f"  Files: {len(all_results)}")
        print(f"  Chunks: {total_chunks}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Speed: {len(all_results)/duration:.1f} files/sec")
        
        return all_results
    
    def compare_sequential_vs_parallel(self, test_files: List[str], language: str):
        """Compare sequential vs parallel performance."""
        from chunker import chunk_file
        
        # Sequential processing
        print("Sequential processing...")
        start = time.time()
        sequential_results = {}
        for file in test_files:
            sequential_results[file] = chunk_file(file, language)
        sequential_time = time.time() - start
        
        # Clear cache for fair comparison
        self.cache.clear()
        
        # Parallel processing
        print("Parallel processing...")
        start = time.time()
        parallel_results = chunk_files_parallel(
            test_files,
            language,
            max_workers=8,
            show_progress=False
        )
        parallel_time = time.time() - start
        
        # Results
        print(f"\nPerformance Comparison:")
        print(f"  Sequential: {sequential_time:.2f}s")
        print(f"  Parallel: {parallel_time:.2f}s")
        print(f"  Speedup: {sequential_time/parallel_time:.2f}x")
        print(f"  Files processed: {len(test_files)}")
        
        return {
            'sequential_time': sequential_time,
            'parallel_time': parallel_time,
            'speedup': sequential_time/parallel_time
        }

# Usage
processor = OptimizedBatchProcessor()

# Process entire project
results = processor.process_large_project("./large_project")

# Compare performance
test_files = list(Path("src/").glob("*.py"))[:20]
if test_files:
    comparison = processor.compare_sequential_vs_parallel(
        [str(f) for f in test_files],
        "python"
    )
```

### Streaming Processing for Huge Files

Handle files too large for memory using the streaming API.

```python
from chunker import chunk_file_streaming
from pathlib import Path
import psutil
import os

class MemoryEfficientProcessor:
    """Process huge files without loading them entirely into memory."""
    
    def __init__(self, memory_limit_mb: int = 1000):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
    
    def process_huge_file(self, file_path: str, language: str):
        """Process a very large file using streaming."""
        file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        print(f"Processing {file_path} ({file_size_mb:.1f} MB)...")
        
        # Monitor memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        chunks_processed = 0
        chunk_types = {}
        
        # Stream process the file
        for chunk in chunk_file_streaming(file_path, language):
            chunks_processed += 1
            
            # Track chunk types
            chunk_types[chunk.node_type] = chunk_types.get(chunk.node_type, 0) + 1
            
            # Process chunk immediately (don't store)
            self._process_chunk(chunk)
            
            # Check memory usage periodically
            if chunks_processed % 100 == 0:
                current_memory = process.memory_info().rss
                memory_used = (current_memory - initial_memory) / (1024 * 1024)
                print(f"\rProcessed {chunks_processed} chunks, "
                      f"Memory delta: {memory_used:.1f} MB", end="")
                
                # If approaching limit, trigger garbage collection
                if current_memory > initial_memory + self.memory_limit_bytes:
                    import gc
                    gc.collect()
        
        # Final stats
        final_memory = process.memory_info().rss
        total_memory_used = (final_memory - initial_memory) / (1024 * 1024)
        
        print(f"\n\nStreaming Processing Complete:")
        print(f"  File size: {file_size_mb:.1f} MB")
        print(f"  Chunks processed: {chunks_processed}")
        print(f"  Memory used: {total_memory_used:.1f} MB")
        print(f"  Memory efficiency: {total_memory_used/file_size_mb:.1%}")
        print(f"\nChunk type distribution:")
        for node_type, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
            print(f"    {node_type}: {count}")
    
    def _process_chunk(self, chunk):
        """Process a single chunk without storing it."""
        # Example: Write to database, send to API, etc.
        # This avoids keeping all chunks in memory
        pass
    
    def batch_process_large_files(self, directory: str, size_threshold_mb: int = 10):
        """Process all large files in a directory using streaming."""
        large_files = []
        
        for file_path in Path(directory).rglob("*"):
            if file_path.is_file():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                if size_mb > size_threshold_mb:
                    ext = file_path.suffix.lower()
                    if ext in ['.py', '.js', '.rs', '.c', '.cpp']:
                        large_files.append((file_path, size_mb))
        
        print(f"Found {len(large_files)} large files (>{size_threshold_mb} MB)\n")
        
        for file_path, size_mb in sorted(large_files, key=lambda x: x[1], reverse=True):
            language = self._detect_language(file_path)
            if language:
                self.process_huge_file(str(file_path), language)
                print("\n" + "="*60 + "\n")
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.rs': 'rust',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp'
        }
        return ext_map.get(file_path.suffix.lower())

# Usage
processor = MemoryEfficientProcessor(memory_limit_mb=500)

# Process a single huge file
if Path("huge_codebase.py").exists():
    processor.process_huge_file("huge_codebase.py", "python")

# Process all large files in a directory
processor.batch_process_large_files("./large_project", size_threshold_mb=10)
```

## Configuration Recipes

### Dynamic Configuration Based on Project Type

Automatically configure based on detected project type.

```python
from chunker import ChunkerConfig, chunk_file
from pathlib import Path
import toml
import yaml
import json

class SmartConfigurator:
    """Automatically configure chunker based on project characteristics."""
    
    def __init__(self):
        self.project_patterns = {
            'django': {
                'files': ['manage.py', 'settings.py'],
                'config': {
                    'languages': {
                        'python': {
                            'chunk_types': [
                                'function_definition',
                                'class_definition',
                                'decorated_definition'
                            ],
                            'custom_options': {
                                'include_views': True,
                                'include_models': True,
                                'include_serializers': True
                            }
                        }
                    }
                }
            },
            'react': {
                'files': ['package.json', 'src/App.js'],
                'config': {
                    'languages': {
                        'javascript': {
                            'chunk_types': [
                                'function_declaration',
                                'arrow_function',
                                'class_declaration',
                                'jsx_element'
                            ],
                            'custom_options': {
                                'include_jsx': True,
                                'include_hooks': True
                            }
                        }
                    }
                }
            },
            'rust': {
                'files': ['Cargo.toml'],
                'config': {
                    'languages': {
                        'rust': {
                            'chunk_types': [
                                'function_item',
                                'impl_item',
                                'trait_item',
                                'struct_item',
                                'enum_item'
                            ],
                            'custom_options': {
                                'include_tests': False,
                                'include_macros': True
                            }
                        }
                    }
                }
            }
        }
    
    def detect_project_type(self, project_root: str) -> str:
        """Detect the type of project."""
        root = Path(project_root)
        
        for project_type, pattern in self.project_patterns.items():
            if all(any(root.rglob(f)) for f in pattern['files']):
                return project_type
        
        return 'generic'
    
    def generate_config(self, project_root: str) -> ChunkerConfig:
        """Generate optimal configuration for the project."""
        project_type = self.detect_project_type(project_root)
        print(f"Detected project type: {project_type}")
        
        if project_type == 'generic':
            # Analyze project to create custom config
            config_dict = self._analyze_project(project_root)
        else:
            config_dict = self.project_patterns[project_type]['config']
        
        # Add common settings
        config_dict.update({
            'cache_enabled': True,
            'cache_size': 200,
            'parallel_workers': 4,
            'exclude_patterns': [
                '*test*', '__pycache__', 'node_modules',
                '.git', '.venv', 'build', 'dist'
            ]
        })
        
        # Save configuration
        config_path = Path(project_root) / '.chunkerrc'
        self._save_config(config_dict, config_path)
        
        print(f"Generated configuration saved to: {config_path}")
        return ChunkerConfig(str(config_path))
    
    def _analyze_project(self, project_root: str) -> dict:
        """Analyze project structure to generate config."""
        root = Path(project_root)
        config = {
            'languages': {},
            'chunk_types': []
        }
        
        # Count files by extension
        file_counts = {}
        for file in root.rglob("*"):
            if file.is_file():
                ext = file.suffix.lower()
                if ext in ['.py', '.js', '.rs', '.c', '.cpp']:
                    file_counts[ext] = file_counts.get(ext, 0) + 1
        
        # Configure based on predominant languages
        for ext, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True):
            if ext == '.py':
                config['languages']['python'] = {
                    'enabled': True,
                    'chunk_types': [
                        'function_definition',
                        'class_definition',
                        'async_function_definition'
                    ],
                    'min_chunk_size': 3,
                    'max_chunk_size': 300
                }
            elif ext in ['.js', '.jsx']:
                config['languages']['javascript'] = {
                    'enabled': True,
                    'chunk_types': [
                        'function_declaration',
                        'arrow_function',
                        'class_declaration'
                    ]
                }
        
        return config
    
    def _save_config(self, config: dict, path: Path):
        """Save configuration in appropriate format."""
        if path.suffix == '.toml' or path.name == '.chunkerrc':
            with open(path, 'w') as f:
                toml.dump(config, f)
        elif path.suffix in ['.yaml', '.yml']:
            with open(path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
        else:
            with open(path, 'w') as f:
                json.dump(config, f, indent=2)
    
    def create_environment_configs(self, project_root: str):
        """Create different configs for different environments."""
        base_config = self.generate_config(project_root)
        
        # Development config
        dev_config = {
            'extends': '.chunkerrc',
            'cache_size': 500,
            'log_level': 'DEBUG',
            'include_tests': True,
            'languages': {
                'python': {
                    'custom_options': {
                        'include_docstrings': True,
                        'include_type_hints': True
                    }
                }
            }
        }
        
        # Production config
        prod_config = {
            'extends': '.chunkerrc',
            'cache_size': 100,
            'log_level': 'WARNING',
            'include_tests': False,
            'min_chunk_size': 5,
            'exclude_patterns': [
                '*test*', '*_test.py', 'test_*.py',
                '__pycache__', '.pytest_cache'
            ]
        }
        
        # CI config
        ci_config = {
            'extends': '.chunkerrc',
            'parallel_workers': 2,
            'show_progress': False,
            'output_format': 'json',
            'fail_on_error': True
        }
        
        # Save environment configs
        root = Path(project_root)
        self._save_config(dev_config, root / 'chunker.dev.toml')
        self._save_config(prod_config, root / 'chunker.prod.toml')
        self._save_config(ci_config, root / 'chunker.ci.toml')
        
        print("Created environment-specific configurations:")
        print("  - chunker.dev.toml (development)")
        print("  - chunker.prod.toml (production)")
        print("  - chunker.ci.toml (CI/CD)")

# Usage
configurator = SmartConfigurator()

# Generate config for current project
config = configurator.generate_config(".")

# Create environment-specific configs
configurator.create_environment_configs(".")

# Use the generated config
chunks = chunk_file("example.py", "python")
print(f"Processed with custom config: {len(chunks)} chunks")
```

### Parallel Processing with Progress Tracking

Process large codebases efficiently with detailed progress tracking.

```python
from chunker.chunker import chunk_file
from chunker.parser import get_parser, return_parser, clear_cache
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count, Manager
import time
from tqdm import tqdm
from typing import List, Dict, Any
import psutil
import os

class ParallelProcessor:
    """High-performance parallel code processor."""
    
    def __init__(self, max_workers=None, use_processes=True):
        self.max_workers = max_workers or cpu_count()
        self.use_processes = use_processes
        self.stats = {
            'files_processed': 0,
            'chunks_found': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def process_directory(self, directory: str, file_pattern: str = "*.py", 
                         process_func=None) -> List[Dict[str, Any]]:
        """Process all matching files in directory."""
        files = list(Path(directory).rglob(file_pattern))
        
        print(f"Found {len(files)} files to process")
        print(f"Using {self.max_workers} workers ({'processes' if self.use_processes else 'threads'})")
        
        self.stats['start_time'] = time.time()
        
        # Choose executor based on configuration
        Executor = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        
        results = []
        with Executor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(
                    process_func or self._process_file,
                    str(file_path)
                ): file_path
                for file_path in files
            }
            
            # Process with progress bar
            with tqdm(total=len(files), desc="Processing files") as pbar:
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        self.stats['files_processed'] += 1
                        self.stats['chunks_found'] += result.get('chunks_count', 0)
                        
                        # Update progress bar with info
                        pbar.set_postfix({
                            'chunks': self.stats['chunks_found'],
                            'errors': self.stats['errors']
                        })
                        
                    except Exception as e:
                        self.stats['errors'] += 1
                        results.append({
                            'file': str(file_path),
                            'error': str(e),
                            'chunks': []
                        })
                    
                    pbar.update(1)
        
        self.stats['end_time'] = time.time()
        self._print_summary()
        
        return results
    
    def _process_file(self, file_path: str) -> Dict[str, Any]:
        """Default file processor."""
        start_time = time.time()
        
        # Detect language
        language = self._detect_language(file_path)
        
        # Process file
        chunks = chunk_file(file_path, language)
        
        # Analyze chunks
        analysis = {
            'file': file_path,
            'language': language,
            'chunks_count': len(chunks),
            'processing_time': time.time() - start_time,
            'chunks': chunks,
            'stats': self._analyze_chunks(chunks)
        }
        
        return analysis
    
    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.rs': 'rust',
            '.c': 'c',
            '.h': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.hpp': 'cpp'
        }
        
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, 'python')
    
    def _analyze_chunks(self, chunks: List) -> Dict[str, Any]:
        """Analyze chunks for statistics."""
        if not chunks:
            return {}
        
        stats = {
            'total_lines': sum(c.end_line - c.start_line + 1 for c in chunks),
            'by_type': {},
            'largest_chunk': max(chunks, key=lambda c: c.end_line - c.start_line).node_type,
            'avg_chunk_size': sum(c.end_line - c.start_line + 1 for c in chunks) / len(chunks)
        }
        
        # Count by type
        for chunk in chunks:
            stats['by_type'][chunk.node_type] = stats['by_type'].get(chunk.node_type, 0) + 1
        
        return stats
    
    def _print_summary(self):
        """Print processing summary."""
        duration = self.stats['end_time'] - self.stats['start_time']
        files_per_second = self.stats['files_processed'] / duration if duration > 0 else 0
        
        print("\n" + "="*60)
        print("Processing Summary")
        print("="*60)
        print(f"Files processed: {self.stats['files_processed']}")
        print(f"Total chunks: {self.stats['chunks_found']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Speed: {files_per_second:.2f} files/second")
        print(f"Memory usage: {psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024:.1f} MB")

class OptimizedChunker:
    """Memory-efficient chunker for large files."""
    
    def __init__(self, chunk_size_mb: int = 10):
        self.chunk_size_bytes = chunk_size_mb * 1024 * 1024
    
    def chunk_large_file(self, file_path: str, language: str) -> List:
        """Chunk large files in parts to manage memory."""
        file_size = Path(file_path).stat().st_size
        
        if file_size <= self.chunk_size_bytes:
            # Small file - process normally
            return chunk_file(file_path, language)
        
        # Large file - process in parts
        print(f"Large file detected ({file_size / 1024 / 1024:.1f} MB), processing in chunks...")
        
        all_chunks = []
        parser = get_parser(language)
        
        try:
            with open(file_path, 'rb') as f:
                offset = 0
                
                while offset < file_size:
                    # Read chunk
                    f.seek(offset)
                    data = f.read(self.chunk_size_bytes)
                    
                    # Find good break point (end of line)
                    if offset + len(data) < file_size:
                        last_newline = data.rfind(b'\n')
                        if last_newline != -1:
                            data = data[:last_newline + 1]
                    
                    # Parse chunk
                    tree = parser.parse(data)
                    
                    # Extract chunks (adjust line numbers)
                    line_offset = data[:offset].count(b'\n') if offset > 0 else 0
                    chunks = self._extract_chunks_from_tree(
                        tree, data, file_path, language, line_offset
                    )
                    all_chunks.extend(chunks)
                    
                    # Move to next chunk
                    offset += len(data)
        
        finally:
            return_parser(language, parser)
        
        return all_chunks
    
    def _extract_chunks_from_tree(self, tree, data, file_path, language, line_offset):
        """Extract chunks from parse tree."""
        # This is a simplified version - real implementation would
        # properly walk the tree and extract chunks
        chunks = []
        
        # ... chunk extraction logic ...
        
        return chunks

# Usage examples
if __name__ == "__main__":
    # Example 1: Parallel processing with custom function
    def analyze_complexity(file_path: str) -> Dict[str, Any]:
        """Custom processing function."""
        language = Path(file_path).suffix.lstrip('.')
        language_map = {'py': 'python', 'js': 'javascript', 'rs': 'rust'}
        language = language_map.get(language, 'python')
        
        chunks = chunk_file(file_path, language)
        
        # Calculate complexity metrics
        complexity_scores = []
        for chunk in chunks:
            if chunk.node_type in ["function_definition", "method_definition"]:
                lines = chunk.end_line - chunk.start_line + 1
                # Simple complexity heuristic
                complexity = lines * 0.1 + chunk.content.count('if ') * 2
                complexity_scores.append({
                    'name': chunk.content.split('\n')[0],
                    'complexity': complexity,
                    'lines': lines
                })
        
        return {
            'file': file_path,
            'chunks': chunks,
            'complexity_scores': complexity_scores,
            'avg_complexity': sum(s['complexity'] for s in complexity_scores) / len(complexity_scores) 
                             if complexity_scores else 0
        }
    
    # Run parallel processing
    processor = ParallelProcessor(max_workers=8, use_processes=True)
    results = processor.process_directory(
        "./large_codebase",
        file_pattern="*.py",
        process_func=analyze_complexity
    )
    
    # Find most complex functions
    all_complexities = []
    for result in results:
        if 'complexity_scores' in result:
            for score in result['complexity_scores']:
                score['file'] = result['file']
                all_complexities.append(score)
    
    # Sort by complexity
    all_complexities.sort(key=lambda x: x['complexity'], reverse=True)
    
    print("\nTop 10 Most Complex Functions:")
    for i, item in enumerate(all_complexities[:10], 1):
        print(f"{i}. {Path(item['file']).name}: {item['name']}")
        print(f"   Complexity: {item['complexity']:.2f}, Lines: {item['lines']}")
```

### Incremental Processing with Change Detection

Process only changed files for efficiency.

```python
from chunker.chunker import chunk_file
from pathlib import Path
import hashlib
import json
import time
from datetime import datetime
from typing import Dict, List, Set
import git

class IncrementalProcessor:
    """Process only changed files since last run."""
    
    def __init__(self, cache_file: str = ".chunker_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.repo = None
        
        # Try to initialize git repo
        try:
            self.repo = git.Repo(search_parent_directories=True)
        except:
            print("Git repository not found, using file modification times")
    
    def _load_cache(self) -> Dict:
        """Load processing cache."""
        if Path(self.cache_file).exists():
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {
            'files': {},
            'last_run': None,
            'stats': {}
        }
    
    def _save_cache(self):
        """Save processing cache."""
        self.cache['last_run'] = datetime.now().isoformat()
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate file hash."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _get_changed_files(self, directory: str, pattern: str = "*.py") -> Set[Path]:
        """Get files that have changed since last run."""
        changed_files = set()
        all_files = set()
        
        # Get all matching files
        for file_path in Path(directory).rglob(pattern):
            if "__pycache__" not in str(file_path):
                all_files.add(file_path)
        
        # Check using git if available
        if self.repo and self.cache.get('last_run'):
            try:
                # Get changed files since last run
                last_run = datetime.fromisoformat(self.cache['last_run'])
                diff = self.repo.index.diff(None)  # Unstaged changes
                
                for item in diff:
                    file_path = Path(self.repo.working_dir) / item.a_path
                    if file_path in all_files:
                        changed_files.add(file_path)
                
                # Also check committed changes
                if self.cache.get('last_commit'):
                    commits = list(self.repo.iter_commits(
                        f"{self.cache['last_commit']}..HEAD"
                    ))
                    for commit in commits:
                        for item in commit.diff(commit.parents[0] if commit.parents else None):
                            file_path = Path(self.repo.working_dir) / item.a_path
                            if file_path in all_files:
                                changed_files.add(file_path)
                
                # Update last commit
                self.cache['last_commit'] = self.repo.head.commit.hexsha
                
            except Exception as e:
                print(f"Git diff failed: {e}, falling back to hash comparison")
                changed_files = self._check_by_hash(all_files)
        else:
            # Fall back to hash comparison
            changed_files = self._check_by_hash(all_files)
        
        # Check for new files
        cached_files = set(Path(f) for f in self.cache['files'].keys())
        new_files = all_files - cached_files
        changed_files.update(new_files)
        
        # Check for deleted files
        deleted_files = cached_files - all_files
        for file_path in deleted_files:
            del self.cache['files'][str(file_path)]
        
        return changed_files
    
    def _check_by_hash(self, files: Set[Path]) -> Set[Path]:
        """Check which files changed by comparing hashes."""
        changed = set()
        
        for file_path in files:
            file_str = str(file_path)
            current_hash = self._get_file_hash(file_str)
            
            if file_str not in self.cache['files'] or \
               self.cache['files'][file_str].get('hash') != current_hash:
                changed.add(file_path)
        
        return changed
    
    def process_incrementally(self, directory: str, language: str = "python",
                            force_all: bool = False) -> Dict[str, Any]:
        """Process only changed files."""
        start_time = time.time()
        
        # Get changed files
        if force_all:
            pattern = {'python': '*.py', 'javascript': '*.js', 'rust': '*.rs'}.get(language, '*')
            changed_files = set(Path(directory).rglob(pattern))
        else:
            changed_files = self._get_changed_files(directory)
        
        print(f"Found {len(changed_files)} changed files")
        
        # Process changed files
        results = {
            'processed_files': [],
            'total_chunks': 0,
            'errors': [],
            'processing_time': 0
        }
        
        for file_path in changed_files:
            try:
                # Process file
                chunks = chunk_file(str(file_path), language)
                
                # Update cache
                file_info = {
                    'hash': self._get_file_hash(str(file_path)),
                    'last_processed': datetime.now().isoformat(),
                    'chunks_count': len(chunks),
                    'chunk_types': list(set(c.node_type for c in chunks))
                }
                self.cache['files'][str(file_path)] = file_info
                
                # Add to results
                results['processed_files'].append({
                    'file': str(file_path),
                    'chunks': len(chunks),
                    'types': file_info['chunk_types']
                })
                results['total_chunks'] += len(chunks)
                
            except Exception as e:
                results['errors'].append({
                    'file': str(file_path),
                    'error': str(e)
                })
        
        # Update statistics
        results['processing_time'] = time.time() - start_time
        self._update_stats(results)
        
        # Save cache
        self._save_cache()
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _update_stats(self, results: Dict[str, Any]):
        """Update cumulative statistics."""
        if 'cumulative' not in self.cache['stats']:
            self.cache['stats']['cumulative'] = {
                'total_runs': 0,
                'total_files_processed': 0,
                'total_chunks_found': 0,
                'total_errors': 0,
                'total_time': 0
            }
        
        stats = self.cache['stats']['cumulative']
        stats['total_runs'] += 1
        stats['total_files_processed'] += len(results['processed_files'])
        stats['total_chunks_found'] += results['total_chunks']
        stats['total_errors'] += len(results['errors'])
        stats['total_time'] += results['processing_time']
    
    def _print_summary(self, results: Dict[str, Any]):
        """Print processing summary."""
        print("\n" + "="*60)
        print("Incremental Processing Summary")
        print("="*60)
        print(f"Files processed: {len(results['processed_files'])}")
        print(f"Total chunks: {results['total_chunks']}")
        print(f"Errors: {len(results['errors'])}")
        print(f"Processing time: {results['processing_time']:.2f} seconds")
        
        if results['errors']:
            print("\nErrors:")
            for error in results['errors'][:5]:
                print(f"  - {error['file']}: {error['error']}")
        
        # Show cumulative stats
        if 'cumulative' in self.cache['stats']:
            stats = self.cache['stats']['cumulative']
            print("\nCumulative Statistics:")
            print(f"  Total runs: {stats['total_runs']}")
            print(f"  Total files processed: {stats['total_files_processed']}")
            print(f"  Total chunks found: {stats['total_chunks_found']}")
            print(f"  Average files per run: {stats['total_files_processed'] / stats['total_runs']:.1f}")
    
    def get_file_history(self, file_path: str) -> Dict[str, Any]:
        """Get processing history for a file."""
        file_str = str(file_path)
        if file_str in self.cache['files']:
            return self.cache['files'][file_str]
        return None

# Usage
processor = IncrementalProcessor()

# First run - processes all files
results = processor.process_incrementally("./src", language="python")

# Make some changes to files...

# Second run - only processes changed files
results = processor.process_incrementally("./src", language="python")

# Force reprocess all files
results = processor.process_incrementally("./src", language="python", force_all=True)

# Check file history
history = processor.get_file_history("./src/main.py")
if history:
    print(f"Last processed: {history['last_processed']}")
    print(f"Chunks found: {history['chunks_count']}")
```

## Language-Specific Recipes

### Python: Extract Type Hints and Decorators

```python
import ast
from chunker.chunker import chunk_file
from typing import List, Dict, Any

class PythonAnalyzer:
    """Python-specific code analysis."""
    
    def analyze_type_hints(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract and analyze type hints."""
        chunks = chunk_file(file_path, "python")
        results = []
        
        for chunk in chunks:
            if chunk.node_type in ["function_definition", "method_definition"]:
                try:
                    tree = ast.parse(chunk.content)
                    func = tree.body[0]
                    
                    analysis = {
                        'function': func.name,
                        'location': f"{file_path}:{chunk.start_line}",
                        'parameters': self._extract_param_types(func),
                        'return_type': ast.unparse(func.returns) if func.returns else None,
                        'has_complete_hints': self._check_complete_hints(func),
                        'decorators': [ast.unparse(d) for d in func.decorator_list]
                    }
                    
                    results.append(analysis)
                except:
                    continue
        
        return results
    
    def _extract_param_types(self, func_node):
        """Extract parameter type hints."""
        params = []
        for arg in func_node.args.args:
            params.append({
                'name': arg.arg,
                'type': ast.unparse(arg.annotation) if arg.annotation else None
            })
        return params
    
    def _check_complete_hints(self, func_node):
        """Check if function has complete type hints."""
        # Check all parameters
        for arg in func_node.args.args:
            if arg.arg != 'self' and not arg.annotation:
                return False
        
        # Check return type (except for __init__)
        if func_node.name != '__init__' and not func_node.returns:
            return False
        
        return True
```

### JavaScript/TypeScript: Extract Exports and Imports

```python
from chunker.chunker import chunk_file
import re

class JavaScriptAnalyzer:
    """JavaScript/TypeScript-specific analysis."""
    
    def analyze_module_structure(self, file_path: str) -> Dict[str, Any]:
        """Analyze module imports and exports."""
        chunks = chunk_file(file_path, "javascript")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        analysis = {
            'imports': self._extract_imports(content),
            'exports': self._extract_exports(chunks, content),
            'components': self._find_react_components(chunks),
            'async_functions': self._find_async_functions(chunks)
        }
        
        return analysis
    
    def _extract_imports(self, content: str) -> List[Dict[str, str]]:
        """Extract import statements."""
        imports = []
        
        # ES6 imports
        import_pattern = r'import\s+(?:{([^}]+)}|(\w+))\s+from\s+["\']([^"\']+)["\']'
        for match in re.finditer(import_pattern, content):
            imports.append({
                'type': 'named' if match.group(1) else 'default',
                'names': match.group(1) or match.group(2),
                'source': match.group(3)
            })
        
        return imports
    
    def _extract_exports(self, chunks, content: str) -> List[Dict[str, Any]]:
        """Extract export statements."""
        exports = []
        
        for chunk in chunks:
            if 'export' in chunk.content.split('\n')[0]:
                exports.append({
                    'type': chunk.node_type,
                    'line': chunk.start_line,
                    'is_default': 'export default' in chunk.content,
                    'name': self._extract_export_name(chunk.content)
                })
        
        return exports
    
    def _find_react_components(self, chunks) -> List[str]:
        """Find React components."""
        components = []
        
        for chunk in chunks:
            # Check for React component patterns
            if chunk.node_type == "class_declaration":
                if "extends Component" in chunk.content or "extends React.Component" in chunk.content:
                    components.append(chunk.content.split('\n')[0])
            elif chunk.node_type == "function_declaration":
                # Check for JSX return
                if "return <" in chunk.content or "return (" in chunk.content:
                    components.append(chunk.content.split('\n')[0])
        
        return components
```

### Rust: Analyze Traits and Implementations

```python
from chunker.chunker import chunk_file
import re

class RustAnalyzer:
    """Rust-specific code analysis."""
    
    def analyze_rust_code(self, file_path: str) -> Dict[str, Any]:
        """Analyze Rust code structure."""
        chunks = chunk_file(file_path, "rust")
        
        analysis = {
            'structs': [],
            'traits': [],
            'impls': [],
            'functions': [],
            'unsafe_blocks': 0,
            'lifetimes': set()
        }
        
        for chunk in chunks:
            if chunk.node_type == "struct_item":
                analysis['structs'].append(self._analyze_struct(chunk))
            elif chunk.node_type == "trait_item":
                analysis['traits'].append(self._analyze_trait(chunk))
            elif chunk.node_type == "impl_item":
                analysis['impls'].append(self._analyze_impl(chunk))
            elif chunk.node_type == "function_item":
                analysis['functions'].append(self._analyze_function(chunk))
            
            # Count unsafe blocks
            analysis['unsafe_blocks'] += chunk.content.count('unsafe {')
            
            # Extract lifetimes
            lifetimes = re.findall(r"'(\w+)", chunk.content)
            analysis['lifetimes'].update(lifetimes)
        
        analysis['lifetimes'] = list(analysis['lifetimes'])
        return analysis
    
    def _analyze_struct(self, chunk):
        """Analyze struct definition."""
        first_line = chunk.content.split('\n')[0]
        return {
            'name': re.search(r'struct\s+(\w+)', first_line).group(1),
            'is_public': first_line.startswith('pub '),
            'has_generics': '<' in first_line,
            'line': chunk.start_line
        }
```

## Build Tool Integration

### Pre-commit Hook

```python
#!/usr/bin/env python3
"""
Pre-commit hook to check code quality using tree-sitter-chunker.
Save as .git/hooks/pre-commit and make executable.
"""

import subprocess
import sys
from pathlib import Path
from chunker.chunker import chunk_file
from chunker.exceptions import ChunkerError

# Configuration
MAX_FUNCTION_LENGTH = 50
MAX_COMPLEXITY = 10
MAX_FILE_LENGTH = 500

def get_staged_files():
    """Get list of staged files."""
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
        capture_output=True,
        text=True
    )
    return [f.strip() for f in result.stdout.split('\n') if f.strip()]

def check_file(file_path):
    """Check a single file for issues."""
    issues = []
    
    # Determine language
    ext_map = {'.py': 'python', '.js': 'javascript', '.rs': 'rust'}
    ext = Path(file_path).suffix
    if ext not in ext_map:
        return []
    
    language = ext_map[ext]
    
    try:
        chunks = chunk_file(file_path, language)
        
        # Check function length
        for chunk in chunks:
            if chunk.node_type in ["function_definition", "method_definition"]:
                length = chunk.end_line - chunk.start_line + 1
                if length > MAX_FUNCTION_LENGTH:
                    issues.append({
                        'file': file_path,
                        'line': chunk.start_line,
                        'type': 'long_function',
                        'message': f'Function is {length} lines (max: {MAX_FUNCTION_LENGTH})'
                    })
        
        # Check file length
        if chunks:
            total_lines = max(c.end_line for c in chunks)
            if total_lines > MAX_FILE_LENGTH:
                issues.append({
                    'file': file_path,
                    'line': 1,
                    'type': 'long_file',
                    'message': f'File is {total_lines} lines (max: {MAX_FILE_LENGTH})'
                })
        
    except ChunkerError as e:
        # Syntax error - let other tools handle this
        pass
    
    return issues

def main():
    """Run pre-commit checks."""
    staged_files = get_staged_files()
    all_issues = []
    
    for file_path in staged_files:
        if Path(file_path).exists():
            issues = check_file(file_path)
            all_issues.extend(issues)
    
    if all_issues:
        print("Pre-commit check failed:")
        print("-" * 60)
        
        for issue in all_issues:
            print(f"{issue['file']}:{issue['line']} - {issue['type']}")
            print(f"  {issue['message']}")
        
        print(f"\nTotal issues: {len(all_issues)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### GitHub Actions Workflow

```yaml
# .github/workflows/code-quality.yml
name: Code Quality Check

on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install uv
        uv pip install -e .
        uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git
        python scripts/fetch_grammars.py
        python scripts/build_lib.py
    
    - name: Run code analysis
      run: |
        python .github/scripts/analyze_code.py
    
    - name: Upload results
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: code-analysis-results
        path: |
          code-quality-report.html
          code-quality-report.json
```

## Advanced Patterns

### Custom Chunk Types

```python
from chunker.parser import get_parser
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CustomChunk:
    """Extended chunk with custom attributes."""
    type: str
    name: str
    content: str
    start_line: int
    end_line: int
    complexity: int
    dependencies: List[str]
    test_coverage: Optional[float] = None

class CustomChunker:
    """Extract custom chunk types."""
    
    def __init__(self):
        self.custom_extractors = {
            'python': {
                'test_function': self._extract_python_tests,
                'dataclass': self._extract_dataclasses,
                'api_endpoint': self._extract_api_endpoints
            }
        }
    
    def extract_custom_chunks(self, file_path: str, language: str) -> List[CustomChunk]:
        """Extract custom chunk types."""
        parser = get_parser(language)
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        tree = parser.parse(content)
        chunks = []
        
        if language in self.custom_extractors:
            for chunk_type, extractor in self.custom_extractors[language].items():
                chunks.extend(extractor(tree, content, file_path))
        
        return chunks
    
    def _extract_python_tests(self, tree, content, file_path):
        """Extract test functions."""
        chunks = []
        
        # Walk tree and find test functions
        def walk(node):
            if node.type == "function_definition":
                func_content = content[node.start_byte:node.end_byte].decode('utf-8')
                if func_content.startswith('def test_') or '@pytest.mark' in func_content:
                    chunks.append(CustomChunk(
                        type='test_function',
                        name=self._get_function_name(func_content),
                        content=func_content,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        complexity=self._calculate_complexity(func_content),
                        dependencies=self._extract_dependencies(func_content)
                    ))
            
            for child in node.children:
                walk(child)
        
        walk(tree.root_node)
        return chunks
```

## See Also

- [API Reference](api-reference.md) - Complete API documentation
- [User Guide](user-guide.md) - Comprehensive usage guide
- [Getting Started](getting-started.md) - Quick start tutorial
- [Architecture](architecture.md) - System design and internals

Happy coding! 🚀
"""Coupling analysis for detecting relationships between code elements."""

from typing import Dict, List, Set, Tuple, Any
from tree_sitter import Node
from ..interfaces.base import ASTProcessor


class CouplingAnalyzer(ASTProcessor):
    """Analyzes coupling and dependencies between AST nodes.
    
    Identifies:
    - Import dependencies
    - Function/method calls
    - Class inheritance relationships
    - Variable/constant references
    - Type dependencies
    """
    
    def __init__(self):
        self.import_nodes = {
            'import_statement', 'import_from_statement',
            'import_declaration', 'import_specifier',
            'use_statement', 'use_declaration',  # Rust
            'include_statement', 'require_statement',  # C/C++, Ruby
        }
        
        self.inheritance_nodes = {
            'class_definition', 'class_declaration',
            'interface_declaration', 'trait_definition',
        }
        
        self.reference_nodes = {
            'identifier', 'attribute', 'member_expression',
            'property_identifier', 'field_expression',
        }
    
    def analyze_coupling(self, node: Node, source: bytes) -> Dict[str, Any]:
        """Analyze coupling relationships in the AST."""
        context = {
            'imports': [],
            'exports': [],
            'function_calls': {},
            'class_hierarchy': {},
            'variable_refs': {},
            'type_refs': set(),
            'external_deps': set(),
            'internal_deps': set(),
            'coupling_score': 0.0,
        }
        
        # First pass: collect definitions
        self._collect_definitions(node, source, context)
        
        # Second pass: analyze references
        self.traverse(node, context)
        
        # Calculate coupling metrics
        context['coupling_score'] = self._calculate_coupling_score(context)
        
        return {
            'score': context['coupling_score'],
            'imports': context['imports'],
            'exports': context['exports'],
            'function_calls': dict(context['function_calls']),
            'class_hierarchy': context['class_hierarchy'],
            'external_dependencies': list(context['external_deps']),
            'internal_dependencies': list(context['internal_deps']),
            'type_dependencies': list(context['type_refs']),
        }
    
    def process_node(self, node: Node, context: Dict[str, Any]) -> Any:
        """Process node for coupling analysis."""
        node_type = node.type
        
        # Handle imports
        if node_type in self.import_nodes:
            self._process_import(node, context)
        
        # Handle function/method calls
        elif node_type in ['call', 'method_call', 'function_call', 'call_expression']:
            self._process_call(node, context)
        
        # Handle class inheritance
        elif node_type in self.inheritance_nodes:
            self._process_inheritance(node, context)
        
        # Handle references
        elif node_type in self.reference_nodes:
            self._process_reference(node, context)
        
        # Handle exports
        elif node_type in ['export_statement', 'export_declaration']:
            self._process_export(node, context)
        
        return None
    
    def should_process_children(self, node: Node, context: Dict[str, Any]) -> bool:
        """Process all children for complete analysis."""
        return True
    
    def _collect_definitions(self, node: Node, source: bytes, context: Dict[str, Any]):
        """First pass to collect all definitions."""
        definitions = context.setdefault('definitions', {
            'functions': set(),
            'classes': set(),
            'variables': set(),
            'types': set(),
        })
        
        # Collect function definitions
        if node.type in ['function_definition', 'method_definition', 'function_declaration']:
            name = self._get_node_name(node)
            if name:
                definitions['functions'].add(name)
        
        # Collect class definitions
        elif node.type in ['class_definition', 'class_declaration']:
            name = self._get_node_name(node)
            if name:
                definitions['classes'].add(name)
        
        # Collect variable definitions
        elif node.type in ['assignment', 'variable_declaration', 'const_declaration']:
            name = self._get_variable_name(node)
            if name:
                definitions['variables'].add(name)
        
        # Collect type definitions
        elif node.type in ['type_alias', 'type_definition', 'interface_declaration']:
            name = self._get_node_name(node)
            if name:
                definitions['types'].add(name)
        
        # Recurse through children
        for child in node.children:
            self._collect_definitions(child, source, context)
    
    def _process_import(self, node: Node, context: Dict[str, Any]):
        """Process import statements."""
        import_info = {
            'type': node.type,
            'module': None,
            'names': [],
            'alias': None,
        }
        
        # Extract module name and imported symbols
        for child in node.children:
            if child.type in ['dotted_name', 'string', 'module_name']:
                import_info['module'] = child.text.decode()
                context['external_deps'].add(import_info['module'])
            elif child.type == 'import_from_names':
                for name_child in child.children:
                    if name_child.type == 'identifier':
                        import_info['names'].append(name_child.text.decode())
        
        context['imports'].append(import_info)
    
    def _process_call(self, node: Node, context: Dict[str, Any]):
        """Process function/method calls."""
        func_name = self._extract_call_target(node)
        if func_name:
            # Track call frequency
            context['function_calls'][func_name] = context['function_calls'].get(func_name, 0) + 1
            
            # Determine if internal or external
            definitions = context.get('definitions', {})
            if func_name in definitions.get('functions', set()):
                context['internal_deps'].add(func_name)
            else:
                # Could be external or method call
                if '.' not in func_name:
                    context['external_deps'].add(func_name)
    
    def _process_inheritance(self, node: Node, context: Dict[str, Any]):
        """Process class inheritance relationships."""
        class_name = self._get_node_name(node)
        if not class_name:
            return
        
        bases = []
        for child in node.children:
            if child.type in ['argument_list', 'superclass', 'base_list']:
                for base_child in child.children:
                    if base_child.type == 'identifier':
                        base_name = base_child.text.decode()
                        bases.append(base_name)
                        context['type_refs'].add(base_name)
        
        if bases:
            context['class_hierarchy'][class_name] = bases
    
    def _process_reference(self, node: Node, context: Dict[str, Any]):
        """Process identifier references."""
        parent = context.get('parent')
        if not parent:
            return
        
        # Skip if this is a definition
        if parent.type in ['function_definition', 'class_definition', 'assignment']:
            return
        
        ref_name = node.text.decode()
        
        # Check if it's a known internal reference
        definitions = context.get('definitions', {})
        if ref_name in definitions.get('variables', set()):
            context['variable_refs'][ref_name] = context['variable_refs'].get(ref_name, 0) + 1
        elif ref_name in definitions.get('types', set()):
            context['type_refs'].add(ref_name)
    
    def _process_export(self, node: Node, context: Dict[str, Any]):
        """Process export statements."""
        export_info = {
            'type': node.type,
            'names': [],
        }
        
        for child in node.children:
            if child.type == 'identifier':
                export_info['names'].append(child.text.decode())
        
        context['exports'].append(export_info)
    
    def _calculate_coupling_score(self, context: Dict[str, Any]) -> float:
        """Calculate overall coupling score."""
        # Weights for different coupling types
        weights = {
            'external_imports': 2.0,
            'external_calls': 1.5,
            'internal_calls': 0.5,
            'inheritance': 1.0,
            'type_deps': 0.8,
        }
        
        score = 0.0
        
        # External dependencies are high coupling
        score += len(context['external_deps']) * weights['external_imports']
        
        # Function calls indicate coupling
        external_calls = sum(1 for call in context['function_calls'] 
                           if call in context['external_deps'])
        internal_calls = sum(1 for call in context['function_calls'] 
                           if call in context['internal_deps'])
        
        score += external_calls * weights['external_calls']
        score += internal_calls * weights['internal_calls']
        
        # Inheritance creates tight coupling
        score += len(context['class_hierarchy']) * weights['inheritance']
        
        # Type dependencies
        score += len(context['type_refs']) * weights['type_deps']
        
        return score
    
    def _get_node_name(self, node: Node) -> str:
        """Extract name from definition node."""
        for child in node.children:
            if child.type == 'identifier':
                return child.text.decode()
        return ""
    
    def _get_variable_name(self, node: Node) -> str:
        """Extract variable name from assignment/declaration."""
        for child in node.children:
            if child.type in ['identifier', 'pattern']:
                if child.type == 'identifier':
                    return child.text.decode()
                # Handle pattern matching
                elif child.type == 'pattern' and child.children:
                    first_child = child.children[0]
                    if first_child.type == 'identifier':
                        return first_child.text.decode()
        return ""
    
    def _extract_call_target(self, call_node: Node) -> str:
        """Extract function/method name from call node."""
        if not call_node.children:
            return ""
        
        func_node = call_node.children[0]
        
        if func_node.type == 'identifier':
            return func_node.text.decode()
        elif func_node.type in ['attribute', 'member_expression']:
            # Handle method calls
            parts = []
            for child in func_node.children:
                if child.type == 'identifier':
                    parts.append(child.text.decode())
            return '.'.join(parts) if parts else func_node.text.decode()
        
        return ""
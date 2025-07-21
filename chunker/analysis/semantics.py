"""Semantic analysis for understanding code meaning and relationships."""

from typing import Dict, List, Set, Any, Optional
from tree_sitter import Node
from ..interfaces.base import ASTProcessor


class SemanticAnalyzer(ASTProcessor):
    """Analyzes semantic properties of AST nodes.
    
    Identifies:
    - Code patterns and idioms
    - Semantic roles (initialization, validation, computation, etc.)
    - Data flow relationships
    - Side effects and purity
    """
    
    def __init__(self):
        # Semantic categories for different node patterns
        self.semantic_patterns = {
            'initialization': [
                'constructor', '__init__', 'new', 'create', 'build',
                'setup', 'initialize', 'config', 'configure'
            ],
            'validation': [
                'validate', 'check', 'verify', 'assert', 'ensure',
                'is_valid', 'can_', 'should_', 'must_'
            ],
            'computation': [
                'calculate', 'compute', 'process', 'transform',
                'convert', 'parse', 'analyze', 'evaluate'
            ],
            'io_operation': [
                'read', 'write', 'load', 'save', 'fetch',
                'send', 'receive', 'get', 'put', 'post'
            ],
            'lifecycle': [
                'start', 'stop', 'begin', 'end', 'open',
                'close', 'connect', 'disconnect', 'dispose'
            ],
            'error_handling': [
                'handle', 'catch', 'error', 'exception',
                'fail', 'retry', 'recover', 'fallback'
            ],
        }
        
        # Nodes that typically have side effects
        self.side_effect_nodes = {
            'assignment', 'augmented_assignment',
            'call', 'method_call',
            'print_statement', 'expression_statement',
            'delete_statement', 'return_statement',
            'yield_statement', 'raise_statement',
            'throw_statement', 'await_expression',
        }
        
        # Pure/functional patterns
        self.pure_patterns = {
            'const', 'final', 'readonly', 'immutable',
            'pure', 'functional', 'deterministic',
        }
    
    def analyze_semantics(self, node: Node, source: bytes) -> Dict[str, Any]:
        """Perform semantic analysis on the AST node."""
        context = {
            'semantic_role': None,
            'patterns': [],
            'side_effects': [],
            'data_flow': {
                'inputs': set(),
                'outputs': set(),
                'transformations': [],
            },
            'purity_score': 1.0,  # 1.0 = pure, 0.0 = many side effects
            'semantic_cohesion': 0.0,
            'semantic_markers': [],
        }
        
        # Analyze the node and its subtree
        self.traverse(node, context)
        
        # Determine primary semantic role
        context['semantic_role'] = self._determine_semantic_role(node, context)
        
        # Calculate semantic cohesion
        context['semantic_cohesion'] = self._calculate_cohesion(context)
        
        return {
            'role': context['semantic_role'],
            'patterns': list(set(context['patterns'])),
            'side_effects': context['side_effects'],
            'data_flow': {
                'inputs': list(context['data_flow']['inputs']),
                'outputs': list(context['data_flow']['outputs']),
                'transformations': context['data_flow']['transformations'],
            },
            'purity_score': context['purity_score'],
            'cohesion_score': context['semantic_cohesion'],
            'markers': context['semantic_markers'],
        }
    
    def process_node(self, node: Node, context: Dict[str, Any]) -> Any:
        """Process node for semantic analysis."""
        node_type = node.type
        
        # Check for side effects
        if node_type in self.side_effect_nodes:
            self._analyze_side_effect(node, context)
        
        # Analyze function/method semantics
        if node_type in ['function_definition', 'method_definition']:
            self._analyze_function_semantics(node, context)
        
        # Track data flow
        if node_type == 'identifier':
            self._track_data_flow(node, context)
        
        # Check for semantic markers (comments, decorators)
        if node_type in ['comment', 'decorator', 'annotation']:
            self._analyze_semantic_marker(node, context)
        
        # Analyze control flow for patterns
        if node_type in ['if_statement', 'try_statement', 'while_statement']:
            self._analyze_control_pattern(node, context)
        
        return None
    
    def should_process_children(self, node: Node, context: Dict[str, Any]) -> bool:
        """Process all children for complete semantic analysis."""
        return True
    
    def _determine_semantic_role(self, node: Node, context: Dict[str, Any]) -> str:
        """Determine the primary semantic role of a code block."""
        # Get function/class name if available
        name = self._get_node_name(node).lower()
        
        # Check against semantic patterns
        for role, patterns in self.semantic_patterns.items():
            for pattern in patterns:
                if pattern in name:
                    context['patterns'].append(role)
                    return role
        
        # Use heuristics based on node content
        if context['side_effects']:
            effect_types = [e['type'] for e in context['side_effects']]
            if 'io' in effect_types:
                return 'io_operation'
            elif 'state_mutation' in effect_types:
                return 'state_management'
        
        # Check for specific patterns in the code
        if 'exception' in context['patterns'] or 'error' in context['patterns']:
            return 'error_handling'
        
        # Default based on node type
        if node.type == 'class_definition':
            return 'data_structure'
        elif node.type in ['function_definition', 'method_definition']:
            if context['purity_score'] > 0.8:
                return 'computation'
            else:
                return 'procedure'
        
        return 'general'
    
    def _analyze_side_effect(self, node: Node, context: Dict[str, Any]):
        """Analyze potential side effects."""
        effect_info = {
            'node_type': node.type,
            'type': None,
            'severity': 'low',
        }
        
        # Determine side effect type
        if node.type in ['assignment', 'augmented_assignment']:
            effect_info['type'] = 'state_mutation'
            effect_info['severity'] = 'medium'
            
            # Track what's being modified
            target = self._get_assignment_target(node)
            if target:
                context['data_flow']['outputs'].add(target)
        
        elif node.type in ['call', 'method_call']:
            func_name = self._extract_call_name(node)
            if func_name:
                # Check if it's an I/O operation
                if any(io_word in func_name.lower() for io_word in 
                      ['read', 'write', 'print', 'send', 'save', 'load']):
                    effect_info['type'] = 'io'
                    effect_info['severity'] = 'high'
                else:
                    effect_info['type'] = 'function_call'
                    effect_info['severity'] = 'medium'
        
        elif node.type in ['raise_statement', 'throw_statement']:
            effect_info['type'] = 'exception'
            effect_info['severity'] = 'high'
        
        if effect_info['type']:
            context['side_effects'].append(effect_info)
            # Reduce purity score based on severity
            severity_penalty = {'low': 0.1, 'medium': 0.3, 'high': 0.5}
            context['purity_score'] -= severity_penalty.get(effect_info['severity'], 0.1)
            context['purity_score'] = max(0.0, context['purity_score'])
    
    def _analyze_function_semantics(self, node: Node, context: Dict[str, Any]):
        """Analyze semantic properties of functions/methods."""
        func_name = self._get_node_name(node).lower()
        
        # Check for semantic patterns in name
        for role, patterns in self.semantic_patterns.items():
            if any(pattern in func_name for pattern in patterns):
                context['patterns'].append(role)
        
        # Check for purity indicators
        if any(pure in func_name for pure in self.pure_patterns):
            context['purity_score'] = min(1.0, context['purity_score'] + 0.2)
        
        # Analyze parameters for data flow
        for child in node.children:
            if child.type == 'parameters':
                for param in child.children:
                    if param.type in ['identifier', 'parameter']:
                        param_name = param.text.decode()
                        context['data_flow']['inputs'].add(param_name)
    
    def _track_data_flow(self, node: Node, context: Dict[str, Any]):
        """Track data flow through identifiers."""
        parent = context.get('parent')
        if not parent:
            return
        
        identifier = node.text.decode()
        
        # Input: Used in expressions, conditions, arguments
        if parent.type in ['binary_expression', 'comparison', 'argument_list']:
            context['data_flow']['inputs'].add(identifier)
        
        # Output: Assignment targets, return values
        elif parent.type in ['assignment', 'return_statement']:
            context['data_flow']['outputs'].add(identifier)
        
        # Transformation: Both input and output
        elif parent.type == 'augmented_assignment':
            context['data_flow']['inputs'].add(identifier)
            context['data_flow']['outputs'].add(identifier)
            context['data_flow']['transformations'].append({
                'variable': identifier,
                'operation': parent.type,
            })
    
    def _analyze_semantic_marker(self, node: Node, context: Dict[str, Any]):
        """Analyze comments and decorators for semantic hints."""
        text = node.text.decode().lower()
        
        # Look for semantic keywords in comments
        semantic_keywords = {
            'pure': 'functional',
            'side effect': 'impure',
            'mutates': 'state_mutation',
            'thread-safe': 'concurrent',
            'async': 'asynchronous',
            'deprecated': 'legacy',
            'api': 'interface',
            'internal': 'private',
            'public': 'api',
        }
        
        for keyword, marker in semantic_keywords.items():
            if keyword in text:
                context['semantic_markers'].append(marker)
    
    def _analyze_control_pattern(self, node: Node, context: Dict[str, Any]):
        """Analyze control flow patterns."""
        if node.type == 'if_statement':
            # Check for validation patterns
            condition = self._get_condition_text(node)
            if condition and any(word in condition for word in 
                               ['valid', 'null', 'empty', 'exists', 'error']):
                context['patterns'].append('validation')
        
        elif node.type == 'try_statement':
            context['patterns'].append('error_handling')
        
        elif node.type == 'while_statement':
            # Could be polling, retry, or processing loop
            condition = self._get_condition_text(node)
            if condition and 'retry' in condition:
                context['patterns'].append('retry_logic')
    
    def _calculate_cohesion(self, context: Dict[str, Any]) -> float:
        """Calculate semantic cohesion score."""
        # High cohesion: Single responsibility, consistent patterns
        pattern_count = len(set(context['patterns']))
        
        if pattern_count == 0:
            return 0.5  # Neutral
        elif pattern_count == 1:
            return 1.0  # Highly cohesive
        else:
            # Reduce cohesion for multiple responsibilities
            return max(0.0, 1.0 - (pattern_count - 1) * 0.2)
    
    def _get_node_name(self, node: Node) -> str:
        """Extract name from function/class definition."""
        for child in node.children:
            if child.type == 'identifier':
                return child.text.decode()
        return ""
    
    def _get_assignment_target(self, node: Node) -> str:
        """Extract assignment target."""
        for child in node.children:
            if child.type == 'identifier':
                return child.text.decode()
            elif child.type == 'attribute':
                return child.text.decode()
        return ""
    
    def _extract_call_name(self, node: Node) -> str:
        """Extract function name from call node."""
        if node.children:
            func_node = node.children[0]
            if func_node.type == 'identifier':
                return func_node.text.decode()
            elif func_node.type in ['attribute', 'member_expression']:
                return func_node.text.decode()
        return ""
    
    def _get_condition_text(self, node: Node) -> str:
        """Extract condition text from control flow node."""
        for child in node.children:
            if child.type in ['condition', 'expression']:
                return child.text.decode()
        return ""
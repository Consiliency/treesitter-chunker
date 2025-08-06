"""Complexity analysis for AST nodes."""

from typing import Any

from tree_sitter import Node

from chunker.interfaces.base import ASTProcessor


class ComplexityAnalyzer(ASTProcessor):
    """Analyzes AST complexity for intelligent chunk boundaries.

    Calculates various complexity metrics including:
    - Cyclomatic complexity
    - Depth of nesting
    - Number of dependencies
    - Cognitive complexity
    """

    def __init__(self):
        self.complexity_weights = {
            "if_statement": 1,
            "elif_clause": 1,
            "else_clause": 1,
            "while_statement": 1,
            "for_statement": 1,
            "for_in_statement": 1,
            "try_statement": 1,
            "except_clause": 1,
            "finally_clause": 1,
            "switch_statement": 1,
            "case_statement": 1,
            "conditional_expression": 1,
            "and": 1,
            "or": 1,
            "not": 0.5,
            "call": 0.5,
            "method_call": 0.5,
            "nested_if": 0.5,
            "nested_loop": 1.0,
            "nested_try": 0.5,
        }

    def calculate_complexity(self, node: Node, _source: bytes) -> dict[
        str,
        Any,
    ]:
        """Calculate comprehensive complexity metrics for a node."""
        context = {
            "cyclomatic": 1,
            "cognitive": 0,
            "nesting_depth": 0,
            "max_nesting": 0,
            "dependencies": set(),
            "function_calls": 0,
            "branches": 0,
            "loops": 0,
            "exceptions": 0,
        }
        self.traverse(node, context)
        complexity_score = (
            context["cyclomatic"] * 1.0
            + context["cognitive"] * 0.5
            + context["max_nesting"] * 0.3
            + len(context["dependencies"]) * 0.2
        )
        return {
            "score": complexity_score,
            "cyclomatic": context["cyclomatic"],
            "cognitive": context["cognitive"],
            "max_nesting": context["max_nesting"],
            "dependencies": list(context["dependencies"]),
            "function_calls": context["function_calls"],
            "branches": context["branches"],
            "loops": context["loops"],
            "exceptions": context["exceptions"],
        }

    def process_node(self, node: Node, context: dict[str, Any]) -> Any:
        """Process a single node and update complexity metrics."""
        node_type = node.type
        if node_type in self.complexity_weights:
            context["cyclomatic"] += self.complexity_weights[node_type]
        parent = context.get("parent")
        if parent:
            parent_type = parent.type if parent else None
            if self._increases_nesting(node_type, parent_type):
                context["nesting_depth"] = context.get("parent_nesting", 0) + 1
                context["max_nesting"] = max(
                    context["max_nesting"],
                    context["nesting_depth"],
                )
                context["cognitive"] += context["nesting_depth"] * 0.5
        if node_type in {"if_statement", "conditional_expression"}:
            context["branches"] += 1
        elif node_type in {"while_statement", "for_statement", "for_in_statement"}:
            context["loops"] += 1
        elif node_type in {"try_statement", "except_clause"}:
            context["exceptions"] += 1
        elif node_type in {"call", "method_call", "function_call"}:
            context["function_calls"] += 1
            if node_type == "call" and node.children:
                func_name = self._extract_function_name(node)
                if func_name:
                    context["dependencies"].add(func_name)
        elif node_type == "identifier":
            parent_type = (
                context.get("parent", {}).type if context.get("parent") else None
            )
            if parent_type in {"type", "annotation", "parameter"}:
                context["dependencies"].add(node.text.decode())
        return None

    @staticmethod
    def should_process_children(_node: Node, context: dict[str, Any]) -> bool:
        """Always process children to get complete complexity analysis."""
        if "nesting_depth" in context:
            context["parent_nesting"] = context["nesting_depth"]
        return True

    @staticmethod
    def _increases_nesting(node_type: str, _parent_type: str) -> bool:
        """Check if this node increases nesting depth."""
        nesting_nodes = {
            "if_statement",
            "elif_clause",
            "else_clause",
            "while_statement",
            "for_statement",
            "for_in_statement",
            "try_statement",
            "except_clause",
            "finally_clause",
            "function_definition",
            "method_definition",
            "class_definition",
            "with_statement",
            "match_statement",
            "case_clause",
        }
        return node_type in nesting_nodes

    @staticmethod
    def _extract_function_name(call_node: Node) -> str:
        """Extract function name from a call node."""
        if not call_node.children:
            return ""
        func_node = call_node.children[0]
        if func_node.type == "identifier":
            return func_node.text.decode()
        if func_node.type == "attribute":
            parts = [
                child.text.decode()
                for child in func_node.children
                if child.type in {"identifier", "attribute"}
            ]
            return ".".join(parts)
        if func_node.type == "member_expression":
            return func_node.text.decode()
        return ""

    @staticmethod
    def get_complexity_threshold(node_type: str) -> float:
        """Get recommended complexity threshold for a node type."""
        thresholds = {
            "function_definition": 10.0,
            "method_definition": 10.0,
            "class_definition": 50.0,
            "module": 100.0,
            "block": 5.0,
        }
        return thresholds.get(node_type, 15.0)

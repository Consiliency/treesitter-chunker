"""Semantic analysis for understanding code meaning and relationships."""
from typing import Any

from tree_sitter import Node

from chunker.interfaces.base import ASTProcessor


class SemanticAnalyzer(ASTProcessor):
    """Analyzes semantic properties of AST nodes.

    Identifies:
    - Code patterns and idioms
    - Semantic roles (initialization, validation, computation, etc.)
    - Data flow relationships
    - Side effects and purity
    """

    def __init__(self):
        self.semantic_patterns = {"initialization": ["constructor",
            "__init__", "new", "create", "build", "setup", "initialize",
            "config", "configure"], "validation": ["validate", "check",
            "verify", "assert", "ensure", "is_valid", "can_", "should_",
            "must_"], "computation": ["calculate", "compute", "process",
            "transform", "convert", "parse", "analyze", "evaluate"],
            "io_operation": ["read", "write", "load", "save", "fetch",
            "send", "receive", "get", "put", "post"], "lifecycle": ["start",
            "stop", "begin", "end", "open", "close", "connect",
            "disconnect", "dispose"], "error_handling": ["handle", "catch",
            "error", "exception", "fail", "retry", "recover", "fallback"]}
        self.side_effect_nodes = {"assignment", "augmented_assignment",
            "call", "method_call", "print_statement",
            "expression_statement", "delete_statement", "return_statement",
            "yield_statement", "raise_statement", "throw_statement",
            "await_expression"}
        self.pure_patterns = {"const", "final", "readonly", "immutable",
            "pure", "functional", "deterministic"}

    def analyze_semantics(self, node: Node, _source: bytes) -> dict[str, Any]:
        """Perform semantic analysis on the AST node."""
        context = {"semantic_role": None, "patterns": [], "side_effects": [
            ], "data_flow": {"inputs": set(), "outputs": set(),
            "transformations": []}, "purity_score": 1.0,
            "semantic_cohesion": 0.0, "semantic_markers": []}
        self.traverse(node, context)
        context["semantic_role"] = self._determine_semantic_role(node, context)
        context["semantic_cohesion"] = self._calculate_cohesion(context)
        return {"role": context["semantic_role"], "patterns": list(set(
            context["patterns"])), "side_effects": context["side_effects"],
            "data_flow": {"inputs": list(context["data_flow"]["inputs"]),
            "outputs": list(context["data_flow"]["outputs"]),
            "transformations": context["data_flow"]["transformations"]},
            "purity_score": context["purity_score"], "cohesion_score":
            context["semantic_cohesion"], "markers": context[
            "semantic_markers"]}

    def process_node(self, node: Node, context: dict[str, Any]) -> Any:
        """Process node for semantic analysis."""
        node_type = node.type
        if node_type in self.side_effect_nodes:
            self._analyze_side_effect(node, context)
        if node_type in {"function_definition", "method_definition"}:
            self._analyze_function_semantics(node, context)
        if node_type == "identifier":
            self._track_data_flow(node, context)
        if node_type in {"comment", "decorator", "annotation"}:
            self._analyze_semantic_marker(node, context)
        if node_type in {"if_statement", "try_statement", "while_statement"}:
            self._analyze_control_pattern(node, context)
        return None

    @staticmethod
    def should_process_children(_node: Node, _context: dict[str, Any]) -> bool:
        """Process all children for complete semantic analysis."""
        return True

    def _determine_semantic_role(self, node: Node, context: dict[str, Any],
        ) -> str:
        """Determine the primary semantic role of a code block."""
        name = self._get_node_name(node).lower()
        for role, patterns in self.semantic_patterns.items():
            for pattern in patterns:
                if pattern in name:
                    context["patterns"].append(role)
                    return role
        if context["side_effects"]:
            effect_types = [e["type"] for e in context["side_effects"]]
            if "io" in effect_types:
                return "io_operation"
            if "state_mutation" in effect_types:
                return "state_management"
        if "exception" in context["patterns"] or "error" in context["patterns"
            ]:
            return "error_handling"
        if node.type == "class_definition":
            return "data_structure"
        if node.type in {"function_definition", "method_definition"}:
            if context["purity_score"] > 0.8:
                return "computation"
            return "procedure"
        return "general"

    def _analyze_side_effect(self, node: Node, context: dict[str, Any]):
        """Analyze potential side effects."""
        effect_info = {"node_type": node.type, "type": None, "severity": "low"}
        if node.type in {"assignment", "augmented_assignment"}:
            effect_info["type"] = "state_mutation"
            effect_info["severity"] = "medium"
            target = self._get_assignment_target(node)
            if target:
                context["data_flow"]["outputs"].add(target)
        elif node.type in {"call", "method_call"}:
            func_name = self._extract_call_name(node)
            if func_name:
                if any(io_word in func_name.lower() for io_word in ["read",
                    "write", "print", "send", "save", "load"]):
                    effect_info["type"] = "io"
                    effect_info["severity"] = "high"
                else:
                    effect_info["type"] = "function_call"
                    effect_info["severity"] = "medium"
        elif node.type in {"raise_statement", "throw_statement"}:
            effect_info["type"] = "exception"
            effect_info["severity"] = "high"
        if effect_info["type"]:
            context["side_effects"].append(effect_info)
            severity_penalty = {"low": 0.1, "medium": 0.3, "high": 0.5}
            context["purity_score"] -= severity_penalty.get(effect_info[
                "severity"], 0.1)
            context["purity_score"] = max(0.0, context["purity_score"])

    def _analyze_function_semantics(self, node: Node, context: dict[str, Any]):
        """Analyze semantic properties of functions/methods."""
        func_name = self._get_node_name(node).lower()
        for role, patterns in self.semantic_patterns.items():
            if any(pattern in func_name for pattern in patterns):
                context["patterns"].append(role)
        if any(pure in func_name for pure in self.pure_patterns):
            context["purity_score"] = min(1.0, context["purity_score"] + 0.2)
        for child in node.children:
            if child.type == "parameters":
                for param in child.children:
                    if param.type in {"identifier", "parameter"}:
                        param_name = param.text.decode()
                        context["data_flow"]["inputs"].add(param_name)

    @staticmethod
    def _track_data_flow(node: Node, context: dict[str, Any]):
        """Track data flow through identifiers."""
        parent = context.get("parent")
        if not parent:
            return
        identifier = node.text.decode()
        if parent.type in {"binary_expression", "comparison", "argument_list"}:
            context["data_flow"]["inputs"].add(identifier)
        elif parent.type in {"assignment", "return_statement"}:
            context["data_flow"]["outputs"].add(identifier)
        elif parent.type == "augmented_assignment":
            context["data_flow"]["inputs"].add(identifier)
            context["data_flow"]["outputs"].add(identifier)
            context["data_flow"]["transformations"].append({"variable":
                identifier, "operation": parent.type})

    @staticmethod
    def _analyze_semantic_marker(node: Node, context: dict[str, Any]):
        """Analyze comments and decorators for semantic hints."""
        text = node.text.decode().lower()
        semantic_keywords = {"pure": "functional", "side effect": "impure",
            "mutates": "state_mutation", "thread-safe": "concurrent",
            "async": "asynchronous", "deprecated": "legacy", "api":
            "interface", "internal": "private", "public": "api"}
        for keyword, marker in semantic_keywords.items():
            if keyword in text:
                context["semantic_markers"].append(marker)

    def _analyze_control_pattern(self, node: Node, context: dict[str, Any]):
        """Analyze control flow patterns."""
        if node.type == "if_statement":
            condition = self._get_condition_text(node)
            if condition and any(word in condition for word in ["valid",
                "null", "empty", "exists", "error"]):
                context["patterns"].append("validation")
        elif node.type == "try_statement":
            context["patterns"].append("error_handling")
        elif node.type == "while_statement":
            condition = self._get_condition_text(node)
            if condition and "retry" in condition:
                context["patterns"].append("retry_logic")

    @staticmethod
    def _calculate_cohesion(context: dict[str, Any]) -> float:
        """Calculate semantic cohesion score."""
        pattern_count = len(set(context["patterns"]))
        if pattern_count == 0:
            return 0.5
        if pattern_count == 1:
            return 1.0
        return max(0.0, 1.0 - (pattern_count - 1) * 0.2)

    @staticmethod
    def _get_node_name(node: Node) -> str:
        """Extract name from function/class definition."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
        return ""

    @staticmethod
    def _get_assignment_target(node: Node) -> str:
        """Extract assignment target."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
            if child.type == "attribute":
                return child.text.decode()
        return ""

    @staticmethod
    def _extract_call_name(node: Node) -> str:
        """Extract function name from call node."""
        if node.children:
            func_node = node.children[0]
            if func_node.type == "identifier":
                return func_node.text.decode()
            if func_node.type in {"attribute", "member_expression"}:
                return func_node.text.decode()
        return ""

    @staticmethod
    def _get_condition_text(node: Node) -> str:
        """Extract condition text from control flow node."""
        for child in node.children:
            if child.type in {"condition", "expression"}:
                return child.text.decode()
        return ""

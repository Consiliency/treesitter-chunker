"""Code complexity metrics implementation."""
from abc import ABC

from tree_sitter import Node

from chunker.interfaces.metadata import ComplexityAnalyzer, ComplexityMetrics


class BaseComplexityAnalyzer(ComplexityAnalyzer, ABC):
    """Base implementation for calculating code complexity metrics."""

    def __init__(self, language: str):
        """
        Initialize the complexity analyzer.

        Args:
            language: Programming language name
        """
        self.language = language
        self._decision_points = self._get_decision_point_types()
        self._cognitive_factors = self._get_cognitive_complexity_factors()

    @staticmethod
    def _get_decision_point_types() -> set[str]:
        """
        Get node types that represent decision points.

        Returns:
            Set of node type names
        """
        return {"if_statement", "if_expression", "elif_clause",
            "else_clause", "while_statement", "while_expression",
            "for_statement", "for_expression", "for_in_statement",
            "do_statement", "do_while_statement", "switch_statement",
            "switch_expression", "case_statement", "case_clause",
            "conditional_expression", "ternary_expression", "try_statement",
            "catch_clause", "except_clause", "match_statement",
            "match_expression", "and", "or", "binary_expression",
            "logical_and", "logical_or"}

    @staticmethod
    def _get_cognitive_complexity_factors() -> dict[str, int]:
        """
        Get cognitive complexity weights for different constructs.

        Returns:
            Mapping of node types to complexity weights
        """
        return {"if_statement": 1, "elif_clause": 1, "else_clause": 0,
            "while_statement": 1, "for_statement": 1, "do_statement": 1,
            "switch_statement": 1, "case_statement": 0, "match_statement":
            1, "try_statement": 1, "catch_clause": 1, "except_clause": 1,
            "and": 1, "or": 1, "logical_and": 1, "logical_or": 1,
            "conditional_expression": 1, "ternary_expression": 1,
            "recursive_call": 1}

    @staticmethod
    def calculate_cyclomatic_complexity(node: Node) -> int:
        """
        Calculate cyclomatic complexity (McCabe complexity).

        Formula: M = E - N + 2P
        Simplified: Count decision points + 1

        Args:
            node: AST node

        Returns:
            Cyclomatic complexity score
        """
        complexity = 1

        def count_decision_points(n: Node):
            nonlocal complexity
            if n.type in self._decision_points:
                if n.type == "else_clause":
                    pass
                elif n.type in {"binary_expression", "logical_expression"}:
                    operator_node = self._find_operator_node(n)
                    if operator_node and operator_node.type in {"and", "or",
                        "&&", "||"}:
                        complexity += 1
                else:
                    complexity += 1
            for child in n.children:
                count_decision_points(child)
        count_decision_points(node)
        return complexity

    @staticmethod
    def calculate_cognitive_complexity(node: Node) -> int:
        """
        Calculate cognitive complexity.

        Considers nesting level and type of control structures.

        Args:
            node: AST node

        Returns:
            Cognitive complexity score
        """
        complexity = 0

        def calculate_recursive(n: Node, nesting_level: int, parent_types:
            set[str]):
            nonlocal complexity
            current_nesting = nesting_level
            increment = 0
            if n.type in self._cognitive_factors:
                base_increment = self._cognitive_factors[n.type]
                if base_increment > 0:
                    increment = base_increment + nesting_level
                    complexity += increment
                    if self._increases_nesting(n.type):
                        current_nesting += 1
            if self._is_recursive_call(n, parent_types):
                complexity += self._cognitive_factors.get("recursive_call", 1)
            current_types = parent_types.copy()
            if n.type in {"function_definition", "method_definition",
                "function_declaration"}:
                name_node = self._find_name_node(n)
                if name_node:
                    current_types.add(name_node.type)
            for child in n.children:
                calculate_recursive(child, current_nesting, current_types)
        calculate_recursive(node, 0, set())
        return complexity

    @staticmethod
    def calculate_nesting_depth(node: Node) -> int:
        """
        Calculate maximum nesting depth.

        Args:
            node: AST node

        Returns:
            Maximum nesting level
        """
        max_depth = 0

        def calculate_depth(n: Node, current_depth: int, is_root: bool = False):
            nonlocal max_depth
            if self._increases_nesting(n.type) and not is_root:
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            for child in n.children:
                calculate_depth(child, current_depth, False)
        is_root_node = node.type in {"function_definition",
            "method_definition", "class_definition"}
        calculate_depth(node, 0, is_root_node)
        return max_depth

    def count_logical_lines(self, node: Node, source: bytes) -> int:
        """
        Count logical lines of code.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            Number of logical lines
        """
        text = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        logical_lines = 0
        in_multiline_comment = False
        in_multiline_string = False
        string_delimiter = None
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if not in_multiline_string:
                if line.startswith(('"""', "'''")) and len(line) > 3:
                    string_delimiter = line[:3]
                    in_multiline_string = True
                    if line.count(string_delimiter) >= 2:
                        in_multiline_string = False
                        logical_lines += 1
                    continue
                if line in {'"""', "'''"}:
                    string_delimiter = line
                    in_multiline_string = True
                    continue
            else:
                if string_delimiter in line:
                    in_multiline_string = False
                continue
            if "/*" in line and not in_multiline_string:
                in_multiline_comment = True
            if "*/" in line and in_multiline_comment:
                in_multiline_comment = False
                continue
            if in_multiline_comment:
                continue
            if self._is_comment_line(line):
                continue
            logical_lines += 1
        return logical_lines

    def analyze_complexity(self, node: Node, source: bytes,
        ) -> ComplexityMetrics:
        """
        Perform complete complexity analysis.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            All complexity metrics
        """
        text = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        lines_of_code = len(text.split("\n"))
        return ComplexityMetrics(cyclomatic=self.
            calculate_cyclomatic_complexity(node), cognitive=self.
            calculate_cognitive_complexity(node), nesting_depth=self.
            calculate_nesting_depth(node), lines_of_code=lines_of_code,
            logical_lines=self.count_logical_lines(node, source))

    @staticmethod
    def _find_operator_node(node: Node) -> (Node | None):
        """Find operator node in binary expression."""
        for child in node.children:
            if child.type in {"and", "or", "&&", "||", "operator"}:
                return child
        return None

    @staticmethod
    def _increases_nesting(node_type: str) -> bool:
        """Check if node type increases nesting level."""
        return node_type in {"if_statement", "while_statement",
            "for_statement", "do_statement", "switch_statement",
            "try_statement", "function_definition", "method_definition",
            "class_definition", "with_statement", "match_statement",
            "block_statement", "lambda_expression", "arrow_function"}

    def _is_recursive_call(self, node: Node, parent_function_names: set[str],
        ) -> bool:
        """Check if node is a recursive function call."""
        if node.type not in {"call_expression", "function_call", "method_call",
            }:
            return False
        name_node = self._find_name_node(node)
        return bool(name_node and name_node.type in parent_function_names)

    @staticmethod
    def _find_name_node(node: Node) -> (Node | None):
        """Find name/identifier node."""
        for child in node.children:
            if child.type in {"identifier", "function_name", "method_name"}:
                return child
        return None

    @staticmethod
    def _is_comment_line(line: str) -> bool:
        """Check if line is a comment."""
        line = line.strip()
        return line.startswith(("//", "#", "--", "*", "/*", "*/", '"' * 3,
            "'" * 3))

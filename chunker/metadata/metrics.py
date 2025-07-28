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

        # Define decision point node types per language
        self._decision_points = self._get_decision_point_types()

        # Define cognitive complexity factors
        self._cognitive_factors = self._get_cognitive_complexity_factors()

    def _get_decision_point_types(self) -> set[str]:
        """
        Get node types that represent decision points.

        Returns:
            Set of node type names
        """
        # Common decision points across languages
        return {
            "if_statement",
            "if_expression",
            "elif_clause",
            "else_clause",
            "while_statement",
            "while_expression",
            "for_statement",
            "for_expression",
            "for_in_statement",
            "do_statement",
            "do_while_statement",
            "switch_statement",
            "switch_expression",
            "case_statement",
            "case_clause",
            "conditional_expression",
            "ternary_expression",
            "try_statement",
            "catch_clause",
            "except_clause",
            "match_statement",
            "match_expression",
            "and",
            "or",
            "binary_expression",
            "logical_and",
            "logical_or",
        }

    def _get_cognitive_complexity_factors(self) -> dict[str, int]:
        """
        Get cognitive complexity weights for different constructs.

        Returns:
            Mapping of node types to complexity weights
        """
        return {
            # Basic flow control
            "if_statement": 1,
            "elif_clause": 1,
            "else_clause": 0,  # else doesn't add complexity
            "while_statement": 1,
            "for_statement": 1,
            "do_statement": 1,
            # Advanced flow control
            "switch_statement": 1,
            "case_statement": 0,  # cases are like elif
            "match_statement": 1,
            # Exception handling
            "try_statement": 1,
            "catch_clause": 1,
            "except_clause": 1,
            # Logical operators
            "and": 1,
            "or": 1,
            "logical_and": 1,
            "logical_or": 1,
            # Ternary/conditional
            "conditional_expression": 1,
            "ternary_expression": 1,
            # Recursion (detected separately)
            "recursive_call": 1,
        }

    def calculate_cyclomatic_complexity(self, node: Node) -> int:
        """
        Calculate cyclomatic complexity (McCabe complexity).

        Formula: M = E - N + 2P
        Simplified: Count decision points + 1

        Args:
            node: AST node

        Returns:
            Cyclomatic complexity score
        """
        complexity = 1  # Base complexity

        def count_decision_points(n: Node):
            nonlocal complexity

            # Check if this is a decision point
            if n.type in self._decision_points:
                # else_clause doesn't add to cyclomatic complexity
                if n.type == "else_clause":
                    pass
                # Special handling for binary expressions
                elif n.type in ("binary_expression", "logical_expression"):
                    # Only count if it's actually a logical operator
                    operator_node = self._find_operator_node(n)
                    if operator_node and operator_node.type in (
                        "and",
                        "or",
                        "&&",
                        "||",
                    ):
                        complexity += 1
                else:
                    complexity += 1

            # Recurse through children
            for child in n.children:
                count_decision_points(child)

        count_decision_points(node)
        return complexity

    def calculate_cognitive_complexity(self, node: Node) -> int:
        """
        Calculate cognitive complexity.

        Considers nesting level and type of control structures.

        Args:
            node: AST node

        Returns:
            Cognitive complexity score
        """
        complexity = 0

        def calculate_recursive(n: Node, nesting_level: int, parent_types: set[str]):
            nonlocal complexity

            current_nesting = nesting_level
            increment = 0

            # Get base increment for this node type
            if n.type in self._cognitive_factors:
                base_increment = self._cognitive_factors[n.type]

                # Add nesting penalty
                if base_increment > 0:
                    increment = base_increment + nesting_level
                    complexity += increment

                    # Increase nesting for children
                    if self._increases_nesting(n.type):
                        current_nesting += 1

            # Check for recursive calls
            if self._is_recursive_call(n, parent_types):
                complexity += self._cognitive_factors.get("recursive_call", 1)

            # Track function/method names for recursion detection
            current_types = parent_types.copy()
            if n.type in (
                "function_definition",
                "method_definition",
                "function_declaration",
            ):
                name_node = self._find_name_node(n)
                if name_node:
                    current_types.add(name_node.type)

            # Recurse through children
            for child in n.children:
                calculate_recursive(child, current_nesting, current_types)

        calculate_recursive(node, 0, set())
        return complexity

    def calculate_nesting_depth(self, node: Node) -> int:
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

            # Don't count the root function/method/class as nesting
            if self._increases_nesting(n.type) and not is_root:
                current_depth += 1
                max_depth = max(max_depth, current_depth)

            # Recurse through children
            for child in n.children:
                calculate_depth(child, current_depth, False)

        # Start with is_root=True if node is a function/method/class
        is_root_node = node.type in (
            "function_definition",
            "method_definition",
            "class_definition",
        )
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
        # Get the source text for this node
        text = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        # Count non-empty, non-comment lines
        logical_lines = 0
        in_multiline_comment = False
        in_multiline_string = False
        string_delimiter = None

        for line in text.split("\n"):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Handle multi-line strings (Python docstrings) - but count the first line if it's a statement
            if not in_multiline_string:
                if (line.startswith(('"""', "'''"))) and len(line) > 3:
                    string_delimiter = line[:3]
                    in_multiline_string = True
                    # Check if it ends on the same line
                    if line.count(string_delimiter) >= 2:
                        in_multiline_string = False
                        # Count this line if it's a standalone string (likely docstring)
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

            # Handle multi-line comments (C-style)
            if "/*" in line and not in_multiline_string:
                in_multiline_comment = True
            if "*/" in line and in_multiline_comment:
                in_multiline_comment = False
                continue

            if in_multiline_comment:
                continue

            # Skip single-line comments
            if self._is_comment_line(line):
                continue

            logical_lines += 1

        return logical_lines

    def analyze_complexity(self, node: Node, source: bytes) -> ComplexityMetrics:
        """
        Perform complete complexity analysis.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            All complexity metrics
        """
        # Calculate line counts
        text = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
        lines_of_code = len(text.split("\n"))

        return ComplexityMetrics(
            cyclomatic=self.calculate_cyclomatic_complexity(node),
            cognitive=self.calculate_cognitive_complexity(node),
            nesting_depth=self.calculate_nesting_depth(node),
            lines_of_code=lines_of_code,
            logical_lines=self.count_logical_lines(node, source),
        )

    # Helper methods

    def _find_operator_node(self, node: Node) -> Node | None:
        """Find operator node in binary expression."""
        for child in node.children:
            if child.type in ("and", "or", "&&", "||", "operator"):
                return child
        return None

    def _increases_nesting(self, node_type: str) -> bool:
        """Check if node type increases nesting level."""
        return node_type in {
            "if_statement",
            "while_statement",
            "for_statement",
            "do_statement",
            "switch_statement",
            "try_statement",
            "function_definition",
            "method_definition",
            "class_definition",
            "with_statement",
            "match_statement",
            "block_statement",
            "lambda_expression",
            "arrow_function",
        }

    def _is_recursive_call(self, node: Node, parent_function_names: set[str]) -> bool:
        """Check if node is a recursive function call."""
        if node.type not in ("call_expression", "function_call", "method_call"):
            return False

        # Try to get the function name being called
        name_node = self._find_name_node(node)
        return bool(name_node and name_node.type in parent_function_names)

    def _find_name_node(self, node: Node) -> Node | None:
        """Find name/identifier node."""
        for child in node.children:
            if child.type in ("identifier", "function_name", "method_name"):
                return child
        return None

    def _is_comment_line(self, line: str) -> bool:
        """Check if line is a comment."""
        line = line.strip()
        # Common comment patterns
        return line.startswith(
            ("//", "#", "--", "*", "/*", "*/", '"' * 3, "'" * 3),
        )  # Python docstring

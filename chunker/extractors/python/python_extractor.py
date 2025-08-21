# chunker/extractors/python/python_extractor.py

import ast
import logging
import time
import traceback
from ast import Attribute, Call, ClassDef, Constant, FunctionDef, Name, NodeVisitor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..core.extraction_framework import (
    BaseExtractor,
    CallSite,
    ExtractionResult,
    ExtractionUtils,
)

logger = logging.getLogger(__name__)


class PythonCallVisitor(NodeVisitor):
    """AST visitor for Python call site detection."""

    def __init__(self, source_code: str, file_path: Path | None = None):
        """Initialize the Python call visitor.

        Args:
            source_code: The Python source code being analyzed
            file_path: Optional path to the source file
        """
        self.source_code = source_code
        self.file_path = file_path or Path("<unknown>")
        self.call_sites: list[CallSite] = []
        self.current_context: dict[str, Any] = {
            "class_stack": [],  # Stack of class contexts
            "function_stack": [],  # Stack of function contexts
            "scope_depth": 0,  # Current nesting depth
            "imports": set(),  # Imported modules/functions
            "current_line": 1,  # Current line number
        }
        self.source_lines = source_code.splitlines(keepends=True)

        # Pre-process imports
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Use the alias name if provided, otherwise use the original name
                        import_name = alias.asname if alias.asname else alias.name
                        self.current_context["imports"].add(import_name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for alias in node.names:
                            # For "from module import name as alias", use alias if provided
                            if alias.asname:
                                self.current_context["imports"].add(alias.asname)
                            else:
                                self.current_context["imports"].add(
                                    f"{node.module}.{alias.name}",
                                )
                    else:
                        for alias in node.names:
                            import_name = alias.asname if alias.asname else alias.name
                            self.current_context["imports"].add(import_name)
        except Exception as e:
            logger.warning(f"Error preprocessing imports: {e}")

    def visit_Call(self, node: Call) -> None:
        """Visit call nodes to extract call site information.

        Args:
            node: The AST Call node to process
        """
        try:
            # Extract function name and determine call type
            function_name, call_type = self._extract_function_info(node)

            if function_name:
                # Calculate position information
                line_number = getattr(node, "lineno", 1)
                column_number = getattr(node, "col_offset", 0)

                # Calculate byte offsets
                byte_start, byte_end = self._calculate_byte_offsets(node)

                # Extract context information
                context = self._extract_call_context(node)

                # Create CallSite object
                call_site = CallSite(
                    function_name=function_name,
                    line_number=line_number,
                    column_number=column_number,
                    byte_start=byte_start,
                    byte_end=byte_end,
                    call_type=call_type,
                    context=context,
                    language="python",
                    file_path=self.file_path,
                )

                self.call_sites.append(call_site)

        except Exception as e:
            logger.warning(
                f"Error processing call node at line {getattr(node, 'lineno', '?')}: {e}",
            )

        # Continue visiting child nodes
        self.generic_visit(node)

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Visit function definitions to update context.

        Args:
            node: The AST FunctionDef node to process
        """
        # Push function context
        self.current_context["function_stack"].append(
            {
                "name": node.name,
                "line": getattr(node, "lineno", 1),
                "args": [arg.arg for arg in node.args.args],
                "is_method": len(self.current_context["class_stack"]) > 0,
                "decorators": [
                    self._get_decorator_name(dec) for dec in node.decorator_list
                ],
            },
        )
        self.current_context["scope_depth"] += 1

        # Visit child nodes
        self.generic_visit(node)

        # Pop function context
        self.current_context["function_stack"].pop()
        self.current_context["scope_depth"] -= 1

    def visit_ClassDef(self, node: ClassDef) -> None:
        """Visit class definitions to update context.

        Args:
            node: The AST ClassDef node to process
        """
        # Push class context
        self.current_context["class_stack"].append(
            {
                "name": node.name,
                "line": getattr(node, "lineno", 1),
                "bases": [self._get_base_name(base) for base in node.bases],
                "decorators": [
                    self._get_decorator_name(dec) for dec in node.decorator_list
                ],
            },
        )
        self.current_context["scope_depth"] += 1

        # Visit child nodes
        self.generic_visit(node)

        # Pop class context
        self.current_context["class_stack"].pop()
        self.current_context["scope_depth"] -= 1

    def visit_Attribute(self, node: Attribute) -> None:
        """Visit attribute nodes for method call detection.

        Args:
            node: The AST Attribute node to process
        """
        # Attribute nodes are handled as part of Call nodes
        # This method exists to track attribute access patterns
        self.generic_visit(node)

    def _extract_function_info(self, node: Call) -> tuple[str, str]:
        """Extract function name and call type from Call node.

        Args:
            node: The AST Call node

        Returns:
            Tuple of (function_name, call_type)
        """
        function_name = ""
        call_type = "function"

        try:
            if isinstance(node.func, Name):
                # Simple function call: func()
                function_name = node.func.id
                call_type = "function"

            elif isinstance(node.func, Attribute):
                # Method call: obj.method() or module.func()
                function_name = node.func.attr
                call_type = "method"

                # Try to get the full qualified name
                obj_name = self._get_attribute_chain(node.func)
                if obj_name:
                    function_name = f"{obj_name}.{function_name}"

            else:
                # Complex call (lambda, subscript, etc.)
                function_name = self._extract_complex_call_name(node.func)
                call_type = "complex"

        except Exception as e:
            logger.debug(f"Error extracting function info: {e}")
            function_name = "<unknown>"
            call_type = "unknown"

        return function_name, call_type

    def _get_attribute_chain(self, node: Attribute) -> str:
        """Get the full attribute chain for method calls.

        Args:
            node: The AST Attribute node

        Returns:
            String representation of the attribute chain
        """
        try:
            if isinstance(node.value, Name):
                return node.value.id
            if isinstance(node.value, Attribute):
                parent_chain = self._get_attribute_chain(node.value)
                return f"{parent_chain}.{node.value.attr}"
            if isinstance(node.value, Call):
                # Chained method calls
                return self._extract_complex_call_name(node.value)
            return str(type(node.value).__name__)
        except Exception as e:
            logger.debug(f"Error getting attribute chain: {e}")
            return "<unknown>"

    def _extract_complex_call_name(self, node: ast.AST) -> str:
        """Extract name from complex call expressions.

        Args:
            node: The AST node representing a complex call

        Returns:
            String representation of the call
        """
        try:
            if node is None:
                return "<complex>"
            if isinstance(node, Name):
                return node.id
            if isinstance(node, Attribute):
                return f"{self._get_attribute_chain(node)}"
            if isinstance(node, Call):
                # Nested call
                inner_name, _ = self._extract_function_info(node)
                return f"({inner_name})"
            if isinstance(node, ast.Subscript):
                # Subscript call like func[0]()
                value_name = self._extract_complex_call_name(node.value)
                return f"{value_name}[...]"
            if isinstance(node, ast.Lambda):
                return "<lambda>"
            return f"<{type(node).__name__}>"
        except Exception as e:
            logger.debug(f"Error extracting complex call name: {e}")
            return "<complex>"

    def _calculate_byte_offsets(self, node: ast.AST) -> tuple[int, int]:
        """Calculate byte start and end offsets for a node.

        Args:
            node: The AST node

        Returns:
            Tuple of (start_byte, end_byte)
        """
        try:
            line_start = getattr(node, "lineno", 1)
            col_start = getattr(node, "col_offset", 0)

            # Calculate end position (approximation)
            line_end = getattr(node, "end_lineno", line_start)
            col_end = getattr(node, "end_col_offset", col_start + 1)

            # Convert to byte offsets
            byte_start = self._line_col_to_byte(line_start, col_start)
            byte_end = self._line_col_to_byte(line_end, col_end)

            return byte_start, byte_end

        except Exception as e:
            logger.debug(f"Error calculating byte offsets: {e}")
            return 0, 0

    def _line_col_to_byte(self, line: int, col: int) -> int:
        """Convert line/column position to byte offset.

        Args:
            line: Line number (1-based)
            col: Column number (0-based)

        Returns:
            Byte offset
        """
        try:
            byte_offset = 0

            # Add bytes for complete lines before target line
            for i in range(min(line - 1, len(self.source_lines))):
                byte_offset += len(self.source_lines[i].encode("utf-8"))

            # Add bytes for columns in target line
            if line <= len(self.source_lines):
                line_text = self.source_lines[line - 1]
                col_bytes = line_text[:col].encode("utf-8")
                byte_offset += len(col_bytes)

            return byte_offset

        except Exception as e:
            logger.debug(f"Error converting line/col to byte: {e}")
            return 0

    def _extract_call_context(self, node: Call) -> dict[str, Any]:
        """Extract context information from Python call node.

        Args:
            node: The AST Call node

        Returns:
            Dictionary containing context information
        """
        context = {
            "node_type": "Call",
            "scope_depth": self.current_context["scope_depth"],
        }

        try:
            context.update(
                {
                    "argument_count": len(node.args) if node.args is not None else 0,
                    "keyword_count": (
                        len(node.keywords) if node.keywords is not None else 0
                    ),
                    "has_starargs": (
                        any(isinstance(arg, ast.Starred) for arg in node.args)
                        if node.args
                        else False
                    ),
                    "has_kwargs": (
                        any(kw.arg is None for kw in node.keywords)
                        if node.keywords
                        else False
                    ),
                },
            )
        except Exception as e:
            logger.debug(f"Error extracting basic call context: {e}")
            context["context_error"] = str(e)

        try:
            # Add current class context
            if self.current_context["class_stack"]:
                current_class = self.current_context["class_stack"][-1]
                context["current_class"] = current_class["name"]
                context["class_line"] = current_class["line"]

            # Add current function context
            if self.current_context["function_stack"]:
                current_function = self.current_context["function_stack"][-1]
                context["current_function"] = current_function["name"]
                context["function_line"] = current_function["line"]
                context["is_method_call"] = current_function["is_method"]

            # Add argument types if available
            arg_types = []
            for arg in node.args:
                arg_types.append(self._get_node_type_info(arg))
            if arg_types:
                context["argument_types"] = arg_types

            # Add keyword argument names
            if node.keywords:
                context["keyword_args"] = [kw.arg for kw in node.keywords if kw.arg]

            # Check if this is a known imported function
            func_name, _ = self._extract_function_info(node)
            if any(
                func_name.startswith(imp) for imp in self.current_context["imports"]
            ):
                context["is_imported"] = True

        except Exception as e:
            logger.debug(f"Error extracting call context: {e}")
            context["context_error"] = str(e)

        return context

    def _get_node_type_info(self, node: ast.AST) -> str:
        """Get type information for an AST node.

        Args:
            node: The AST node

        Returns:
            String describing the node type
        """
        try:
            if node is None:
                return "Unknown"
            if isinstance(node, Constant):
                return f"Constant({type(node.value).__name__})"
            if isinstance(node, Name):
                return f"Name({node.id})"
            if isinstance(node, Attribute):
                return f"Attribute({node.attr})"
            if isinstance(node, Call):
                return "Call"
            if isinstance(node, ast.List):
                return "List"
            if isinstance(node, ast.Dict):
                return "Dict"
            if isinstance(node, ast.Tuple):
                return "Tuple"
            return type(node).__name__
        except Exception:
            return "Unknown"

    def _get_decorator_name(self, decorator: ast.AST) -> str:
        """Extract decorator name from decorator node.

        Args:
            decorator: The decorator AST node

        Returns:
            String name of the decorator
        """
        try:
            if decorator is None:
                return "<unknown>"
            if isinstance(decorator, Name):
                return decorator.id
            if isinstance(decorator, Attribute):
                return f"{self._get_attribute_chain(decorator)}"
            if isinstance(decorator, Call):
                func_name, _ = self._extract_function_info(decorator)
                return f"{func_name}(...)"
            return str(type(decorator).__name__)
        except Exception:
            return "<unknown>"

    def _get_base_name(self, base: ast.AST) -> str:
        """Extract base class name from base node.

        Args:
            base: The base class AST node

        Returns:
            String name of the base class
        """
        try:
            if base is None:
                return "<unknown>"
            if isinstance(base, Name):
                return base.id
            if isinstance(base, Attribute):
                return f"{self._get_attribute_chain(base)}"
            return str(type(base).__name__)
        except Exception:
            return "<unknown>"


class PythonExtractor(BaseExtractor):
    """Specialized extractor for Python source code."""

    def __init__(self):
        """Initialize Python extractor."""
        super().__init__("python")
        self.patterns = PythonPatterns()

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """Extract call sites from Python source code.

        Args:
            source_code: The Python source code to analyze
            file_path: Optional path to the source file

        Returns:
            ExtractionResult containing found call sites and metadata
        """
        start_time = time.perf_counter()
        result = ExtractionResult()

        try:
            # Validate input
            self._validate_input(source_code, file_path)

            # Validate Python syntax
            if not self.validate_source(source_code):
                result.add_error("Invalid Python syntax")
                return result

            with self._measure_performance("python_extraction"):
                # Parse the source code into AST
                try:
                    tree = ast.parse(
                        source_code,
                        filename=str(file_path) if file_path else "<string>",
                    )
                except SyntaxError as e:
                    result.add_error(f"Python syntax error: {e}")
                    return result

                # Create visitor and extract call sites
                visitor = PythonCallVisitor(source_code, file_path)
                visitor.visit(tree)

                # Add call sites to result
                result.call_sites = visitor.call_sites

                # Add metadata
                result.metadata.update(
                    {
                        "language": "python",
                        "ast_node_count": len(list(ast.walk(tree))),
                        "source_lines": len(source_code.splitlines()),
                        "source_bytes": len(source_code.encode("utf-8")),
                        "imports_found": len(visitor.current_context["imports"]),
                    },
                )

                if file_path:
                    result.metadata.update(
                        ExtractionUtils.extract_file_metadata(file_path),
                    )

                # Validate extracted call sites
                validation_errors = 0
                for call_site in result.call_sites:
                    errors = ExtractionUtils.validate_call_site(call_site, source_code)
                    if errors:
                        validation_errors += 1
                        logger.debug(
                            f"Validation errors for call site {call_site.function_name}: {errors}",
                        )

                if validation_errors > 0:
                    result.add_warning(
                        f"{validation_errors} call sites had validation issues",
                    )

        except Exception as e:
            result.add_error("Unexpected error during extraction", e)

        finally:
            result.extraction_time = time.perf_counter() - start_time
            result.performance_metrics.update(self.get_performance_metrics())

        return result

    def validate_source(self, source_code: str) -> bool:
        """Validate Python source code.

        Args:
            source_code: The Python source code to validate

        Returns:
            True if valid Python syntax, False otherwise
        """
        try:
            if not isinstance(source_code, str):
                return False

            if not source_code.strip():
                return True  # Empty code is valid

            # Try to parse as Python AST
            ast.parse(source_code)
            return True

        except SyntaxError as e:
            logger.debug(f"Python syntax validation failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during Python validation: {e}")
            return False

    def extract_function_calls(self, source_code: str) -> list[CallSite]:
        """Extract function calls from Python code.

        Args:
            source_code: The Python source code to analyze

        Returns:
            List of CallSite objects representing function calls
        """
        result = self.extract_calls(source_code)

        # Filter for function calls only
        function_calls = [
            call_site
            for call_site in result.call_sites
            if call_site.call_type == "function"
        ]

        return function_calls

    def extract_method_calls(self, source_code: str) -> list[CallSite]:
        """Extract method calls from Python code.

        Args:
            source_code: The Python source code to analyze

        Returns:
            List of CallSite objects representing method calls
        """
        result = self.extract_calls(source_code)

        # Filter for method calls only
        method_calls = [
            call_site
            for call_site in result.call_sites
            if call_site.call_type == "method"
        ]

        return method_calls


class PythonPatterns:
    """Python-specific pattern recognition."""

    @staticmethod
    def is_function_call(node: ast.Call) -> bool:
        """Check if call node represents a function call.

        Args:
            node: The AST Call node to check

        Returns:
            True if the node represents a function call (not method call)
        """
        try:
            if node is None or not hasattr(node, "func"):
                return False
            # Function calls have Name nodes as func
            return isinstance(node.func, ast.Name)
        except Exception:
            return False

    @staticmethod
    def is_method_call(node: ast.Call) -> bool:
        """Check if call node represents a method call.

        Args:
            node: The AST Call node to check

        Returns:
            True if the node represents a method call (has attribute access)
        """
        try:
            if node is None or not hasattr(node, "func"):
                return False
            # Method calls have Attribute nodes as func
            return isinstance(node.func, ast.Attribute)
        except Exception:
            return False

    @staticmethod
    def extract_call_context(node: ast.Call, context: dict[str, Any]) -> dict[str, Any]:
        """Extract context information from Python call node.

        Args:
            node: The AST Call node
            context: Additional context information

        Returns:
            Dictionary containing extracted context
        """
        extracted_context = context.copy()

        try:
            # Add call-specific information
            extracted_context.update(
                {
                    "is_function_call": PythonPatterns.is_function_call(node),
                    "is_method_call": PythonPatterns.is_method_call(node),
                    "argument_count": len(node.args),
                    "keyword_count": len(node.keywords),
                    "has_starargs": any(
                        isinstance(arg, ast.Starred) for arg in node.args
                    ),
                    "has_kwargs": any(kw.arg is None for kw in node.keywords),
                },
            )

            # Extract function/method name
            if isinstance(node.func, ast.Name):
                extracted_context["function_name"] = node.func.id
            elif isinstance(node.func, ast.Attribute):
                extracted_context["method_name"] = node.func.attr

                # Try to get object name
                if isinstance(node.func.value, ast.Name):
                    extracted_context["object_name"] = node.func.value.id

            # Analyze arguments
            arg_info = []
            for i, arg in enumerate(node.args):
                arg_data = {
                    "position": i,
                    "type": type(arg).__name__,
                }

                if isinstance(arg, ast.Constant):
                    arg_data["value_type"] = type(arg.value).__name__
                elif isinstance(arg, ast.Name):
                    arg_data["name"] = arg.id
                elif isinstance(arg, ast.Attribute):
                    arg_data["attribute"] = arg.attr

                arg_info.append(arg_data)

            if arg_info:
                extracted_context["arguments"] = arg_info

            # Analyze keyword arguments
            if node.keywords:
                kw_info = []
                for kw in node.keywords:
                    kw_data = {
                        "name": kw.arg,
                        "type": type(kw.value).__name__,
                    }

                    if isinstance(kw.value, ast.Constant):
                        kw_data["value_type"] = type(kw.value.value).__name__

                    kw_info.append(kw_data)

                extracted_context["keyword_arguments"] = kw_info

        except Exception as e:
            logger.debug(f"Error extracting call context: {e}")
            extracted_context["extraction_error"] = str(e)

        return extracted_context

    @staticmethod
    def is_builtin_function(function_name: str) -> bool:
        """Check if function name is a Python builtin.

        Args:
            function_name: Name of the function to check

        Returns:
            True if the function is a Python builtin
        """
        python_builtins = {
            "abs",
            "all",
            "any",
            "ascii",
            "bin",
            "bool",
            "breakpoint",
            "bytearray",
            "bytes",
            "callable",
            "chr",
            "classmethod",
            "compile",
            "complex",
            "delattr",
            "dict",
            "dir",
            "divmod",
            "enumerate",
            "eval",
            "exec",
            "filter",
            "float",
            "format",
            "frozenset",
            "getattr",
            "globals",
            "hasattr",
            "hash",
            "help",
            "hex",
            "id",
            "input",
            "int",
            "isinstance",
            "issubclass",
            "iter",
            "len",
            "list",
            "locals",
            "map",
            "max",
            "memoryview",
            "min",
            "next",
            "object",
            "oct",
            "open",
            "ord",
            "pow",
            "print",
            "property",
            "range",
            "repr",
            "reversed",
            "round",
            "set",
            "setattr",
            "slice",
            "sorted",
            "staticmethod",
            "str",
            "sum",
            "super",
            "tuple",
            "type",
            "vars",
            "zip",
            "__import__",
        }

        return function_name in python_builtins

    @staticmethod
    def is_dunder_method(method_name: str) -> bool:
        """Check if method name is a Python dunder (magic) method.

        Args:
            method_name: Name of the method to check

        Returns:
            True if the method is a dunder method
        """
        if not isinstance(method_name, str):
            return False

        return (
            method_name.startswith("__")
            and method_name.endswith("__")
            and len(method_name) > 4
            and not method_name.count("__") > 2  # Avoid cases like __a__b__
        )

    @staticmethod
    def get_call_complexity_score(node: ast.Call) -> int:
        """Calculate complexity score for a call based on its structure.

        Args:
            node: The AST Call node

        Returns:
            Integer complexity score (higher = more complex)
        """
        score = 1  # Base score

        try:
            # Add score for arguments
            score += len(node.args)
            score += len(node.keywords)

            # Add score for nested calls in arguments
            for arg in ast.walk(node):
                if isinstance(arg, ast.Call) and arg != node:
                    score += 2

            # Add score for complex function references
            if isinstance(node.func, ast.Attribute):
                score += 1
                # Add score for chained attributes
                current = node.func.value
                while isinstance(current, ast.Attribute):
                    score += 1
                    current = current.value

            # Add score for starred args and kwargs
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                score += 2

            if any(kw.arg is None for kw in node.keywords):
                score += 2

        except Exception:
            # If we can't calculate complexity, assume it's complex
            score = 10

        return score

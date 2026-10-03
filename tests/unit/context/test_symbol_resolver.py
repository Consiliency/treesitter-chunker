"""Unit tests for symbol resolvers."""

from pathlib import Path

import pytest

from chunker.context import BaseSymbolResolver, ContextFactory
from chunker.parser import get_parser


class TestBaseSymbolResolver:
    """Test the base symbol resolver functionality."""

    @classmethod
    def test_init(cls):
        """Test initialization."""
        resolver = BaseSymbolResolver("python")
        assert resolver.language == "python"
        assert resolver._definition_cache == {}
        assert resolver._reference_cache == {}

    @classmethod
    def test_get_symbol_type_unknown(cls):
        """Test getting symbol type for unknown node."""
        resolver = BaseSymbolResolver("python")
        mock_node = type("MockNode", (), {"type": "unknown_node", "parent": None})()
        result = resolver.get_symbol_type(mock_node)
        assert result == "unknown"

    @classmethod
    def test_get_symbol_type_with_parent(cls):
        """Test getting symbol type based on parent."""
        resolver = BaseSymbolResolver("python")
        parent_node = type(
            "MockNode",
            (),
            {"type": "function_definition", "parent": None},
        )()
        child_node = type(
            "MockNode",
            (),
            {"type": "identifier", "parent": parent_node},
        )()
        result = resolver.get_symbol_type(child_node)
        assert result == "function"


class TestPythonSymbolResolver:
    """Test Python-specific symbol resolution."""

    @staticmethod
    def test_real_parsed_references_exclude_properties_and_keyword_names():
        fixture = Path(__file__).parents[2] / "fixtures/context/symbol_references.py"
        root = get_parser("python").parse(fixture.read_bytes()).root_node
        assert not root.has_error
        references = ContextFactory.create_symbol_resolver(
            "python"
        ).find_symbol_references("render", root)
        assert [(node.parent.type, node.start_point.row) for node in references] == [
            ("call", 4),
            ("call", 6),
        ]

    @staticmethod
    def test_real_parsed_import_references_exclude_import_binding():
        fixture = (
            Path(__file__).parents[2]
            / "fixtures/boundary_ir/repos/python/app/service.py"
        )
        root = get_parser("python").parse(fixture.read_bytes()).root_node
        assert not root.has_error
        references = ContextFactory.create_symbol_resolver(
            "python"
        ).find_symbol_references("format_name", root)
        assert [(node.parent.type, node.start_point.row) for node in references] == [
            ("call", 5),
            ("call", 11),
        ]

    @staticmethod
    @pytest.fixture
    def python_code():
        """Sample Python code for testing."""
        return """
class Calculator:
    def __init__(self):
        self.result = 0

    def add(self, x, y):
        result = x + y
        self.result = result
        return result

def calculate(a, b):
    calc = Calculator()
    return calc.add(a, b)

PI = 3.14159
result = calculate(5, PI)
""".strip()

    @staticmethod
    def test_get_symbol_type_class(python_code):
        """Test getting symbol type for a class."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())
        resolver = ContextFactory.create_symbol_resolver("python")

        def find_identifier(node, name):
            if node.type == "identifier" and node.text == name.encode():
                return node
            for child in node.children:
                result = find_identifier(child, name)
                if result:
                    return result
            return None

        for node in tree.root_node.children:
            if node.type == "class_definition":
                calc_id = find_identifier(node, "Calculator")
                if calc_id:
                    symbol_type = resolver.get_symbol_type(calc_id)
                    assert symbol_type == "class"
                    break

    @staticmethod
    def test_get_symbol_type_function(python_code):
        """Test getting symbol type for a function."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())
        resolver = ContextFactory.create_symbol_resolver("python")

        def find_function_name(node, name):
            if node.type == "function_definition":
                for child in node.children:
                    if child.type == "identifier" and child.text == name.encode():
                        return child
            for child in node.children:
                result = find_function_name(child, name)
                if result:
                    return result
            return None

        calc_func = find_function_name(tree.root_node, "calculate")
        assert calc_func is not None
        symbol_type = resolver.get_symbol_type(calc_func)
        assert symbol_type == "function"

    @staticmethod
    def test_find_symbol_references(python_code):
        """Test finding symbol references."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())
        resolver = ContextFactory.create_symbol_resolver("python")
        refs = resolver.find_symbol_references("Calculator", tree.root_node)
        assert isinstance(refs, list)


class TestJavaScriptSymbolResolver:
    """Test JavaScript-specific symbol resolution."""

    @staticmethod
    def test_real_parsed_symbol_references_exclude_definitions_and_properties():
        fixture = Path(__file__).parents[2] / "fixtures/context/symbol_references.js"
        root = get_parser("javascript").parse(fixture.read_bytes()).root_node
        assert not root.has_error
        resolver = ContextFactory.create_symbol_resolver("javascript")

        references = resolver.find_symbol_references("formatName", root)
        assert [(node.parent.type, node.start_point.row) for node in references] == [
            ("call_expression", 5),
            ("call_expression", 9),
        ]
        assert [
            node.parent.type
            for node in resolver.find_symbol_references("generate", root)
        ] == ["call_expression"]

    @staticmethod
    def test_definition_cache_tracks_parsed_tree():
        """A reused resolver must not return another tree's declaration."""
        fixtures = Path(__file__).parents[2] / "fixtures"
        with_renderer = (
            fixtures / "boundary_ir/repos/javascript/service.js"
        ).read_bytes()
        without_renderer = (
            fixtures / "context/javascript_scope_boundaries.js"
        ).read_bytes()
        parser = get_parser("javascript")
        resolver = ContextFactory.create_symbol_resolver("javascript")

        for index in range(4096):
            root = parser.parse(
                with_renderer if index % 2 == 0 else without_renderer
            ).root_node
            assert not root.has_error
            found = resolver.find_symbol_definition("Renderer", root, root)
            if index % 2 == 0:
                assert found is not None and found.type == "class_declaration"
            else:
                assert found is None
        assert len(resolver._definition_cache) <= 256

    @staticmethod
    def test_reference_cache_tracks_parsed_tree():
        """Reference results are bound to the AST passed to the resolver."""

        class TextResolver(BaseSymbolResolver):
            @staticmethod
            def _get_node_text(node):
                return node.text.decode("utf-8") if node.text else ""

        fixtures = Path(__file__).parents[2] / "fixtures"
        with_renderer = (
            fixtures / "boundary_ir/repos/javascript/service.js"
        ).read_bytes()
        without_renderer = (
            fixtures / "context/javascript_scope_boundaries.js"
        ).read_bytes()
        parser = get_parser("javascript")
        resolver = TextResolver("javascript")

        for index in range(512):
            root = parser.parse(
                with_renderer if index % 2 == 0 else without_renderer
            ).root_node
            assert not root.has_error
            references = resolver.find_symbol_references("Renderer", root)
            assert [node.text for node in references] == (
                [b"Renderer"] if index % 2 == 0 else []
            )
        assert len(resolver._reference_cache) <= 256

    @staticmethod
    def test_module_declarations_stop_at_child_scopes():
        """Find declarations at a scope edge without leaking their body locals."""
        fixture = (
            Path(__file__).parents[2]
            / "fixtures/boundary_ir/repos/javascript/service.js"
        )
        tree = get_parser("javascript").parse(fixture.read_bytes())
        root = tree.root_node
        resolver = ContextFactory.create_symbol_resolver("javascript")

        renderer = resolver.find_symbol_definition("Renderer", root, root)
        run = resolver.find_symbol_definition("run", root, root)
        assert renderer is not None and renderer.type == "class_declaration"
        assert run is not None and run.type == "function_declaration"
        assert resolver.find_symbol_definition("cleaned", root, root) is None
        assert resolver.find_symbol_definition("render", root, root) is None

        method = resolver.find_symbol_definition("render", renderer, root)
        local = resolver.find_symbol_definition("cleaned", run, root)
        assert method is not None and method.type == "method_definition"
        assert local is not None and local.type == "variable_declarator"

    @staticmethod
    def test_module_lookup_skips_nonmodule_declarations():
        """Nested declarations cannot mask a real module function."""
        fixture = (
            Path(__file__).parents[2]
            / "fixtures/context/javascript_scope_boundaries.js"
        )
        root = get_parser("javascript").parse(fixture.read_bytes()).root_node
        assert not root.has_error
        resolver = ContextFactory.create_symbol_resolver("javascript")

        run = resolver.find_symbol_definition("run", root, root)
        assert run is not None and run.type == "function_declaration"
        for name in (
            "method",
            "helper",
            "generatorExpressionLocal",
            "generatorLocal",
            "hidden",
            "caseLocal",
            "innerLet",
        ):
            assert resolver.find_symbol_definition(name, root, root) is None

    @staticmethod
    def test_generator_declaration_is_module_definition_without_body_local_leak():
        fixture = (
            Path(__file__).parents[2]
            / "fixtures/context/javascript_scope_boundaries.js"
        )
        root = get_parser("javascript").parse(fixture.read_bytes()).root_node
        assert not root.has_error
        resolver = ContextFactory.create_symbol_resolver("javascript")

        generator = resolver.find_symbol_definition("gen", root, root)
        assert generator is not None
        assert generator.type == "generator_function_declaration"
        name = generator.child_by_field_name("name")
        assert name is not None
        assert resolver.get_symbol_type(name) == "function"
        assert resolver.find_symbol_definition("generatorLocal", root, root) is None
        local = resolver.find_symbol_definition("generatorLocal", generator, root)
        assert local is not None and local.type == "variable_declarator"

    @staticmethod
    @pytest.mark.parametrize(
        "prefix",
        [
            "function* gen() { const run = 1; }",
            "const obj = { run() {} };",
            "if (true) { let run = 1; }",
            "const holder = class { run() {} };",
        ],
    )
    def test_nested_declaration_does_not_mask_module_function(prefix):
        source = f"{prefix} function run() {{}}".encode()
        root = get_parser("javascript").parse(source).root_node
        assert not root.has_error
        found = ContextFactory.create_symbol_resolver(
            "javascript"
        ).find_symbol_definition("run", root, root)
        assert found is not None and found.type == "function_declaration"

    @staticmethod
    @pytest.fixture
    def javascript_code():
        """Sample JavaScript code for testing."""
        return """
class Calculator {
    constructor() {
        this.result = 0;
    }

    add(x, y) {
        const result = x + y;
        this.result = result;
        return result;
    }
}

function calculate(a, b) {
    const calc = new Calculator();
    return calc.add(a, b);
}

const PI = 3.14159;
let result = calculate(5, PI);

export { Calculator, calculate };
""".strip()

    @staticmethod
    def test_get_symbol_type_class(javascript_code):
        """Test getting symbol type for a JavaScript class."""
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())
        resolver = ContextFactory.create_symbol_resolver("javascript")

        def find_class_identifier(node):
            if node.type == "class_declaration":
                for child in node.children:
                    if child.type == "identifier":
                        return child
            for child in node.children:
                result = find_class_identifier(child)
                if result:
                    return result
            return None

        calc_id = find_class_identifier(tree.root_node)
        assert calc_id is not None
        symbol_type = resolver.get_symbol_type(calc_id)
        assert symbol_type == "class"

    @staticmethod
    def test_get_symbol_type_const(javascript_code):
        """Test getting symbol type for a const declaration."""
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())
        resolver = ContextFactory.create_symbol_resolver("javascript")

        def find_const_identifier(node, name):
            if node.type == "variable_declarator":
                for child in node.children:
                    if child.type == "identifier" and child.text == name.encode():
                        parent = node.parent
                        if parent and "const" in parent.text.decode():
                            return child
            for child in node.children:
                result = find_const_identifier(child, name)
                if result:
                    return result
            return None

        pi_id = find_const_identifier(tree.root_node, "PI")
        if pi_id:
            symbol_type = resolver.get_symbol_type(pi_id)
            assert symbol_type in {"constant", "variable"}

    @staticmethod
    def test_get_node_type_map():
        """Test the node type mapping for JavaScript."""
        resolver = ContextFactory.create_symbol_resolver("javascript")
        type_map = resolver._get_node_type_map()
        assert "function_declaration" in type_map
        assert type_map["function_declaration"] == "function"
        assert "class_declaration" in type_map
        assert type_map["class_declaration"] == "class"
        assert "const_declaration" in type_map
        assert type_map["const_declaration"] == "constant"

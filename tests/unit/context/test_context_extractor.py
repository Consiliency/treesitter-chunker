"""Unit tests for context extractors."""

import pytest

from chunker.context import BaseContextExtractor, ContextFactory
from chunker.interfaces.context import ContextItem, ContextType
from chunker.parser import get_parser


class TestBaseContextExtractor:
    """Test the base context extractor functionality."""

    @classmethod
    def test_init(cls):
        """Test initialization."""
        extractor = BaseContextExtractor("python")
        assert extractor.language == "python"
        assert extractor._context_cache == {}

    @classmethod
    def test_build_context_prefix_empty(cls):
        """Test building context prefix with no items."""
        extractor = BaseContextExtractor("python")
        result = extractor.build_context_prefix([])
        assert not result @ classmethod

    def test_build_context_prefix_basic(self):
        """Test building context prefix with basic items."""
        extractor = BaseContextExtractor("python")
        mock_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        items = [
            ContextItem(
                type=ContextType.IMPORT,
                content="import os",
                node=mock_node,
                line_number=1,
                importance=90,
            ),
            ContextItem(
                type=ContextType.IMPORT,
                content="from typing import List",
                node=mock_node,
                line_number=2,
                importance=90,
            ),
        ]
        result = extractor.build_context_prefix(items)
        expected = "import os\nfrom typing import List"
        assert result == expected

    @classmethod
    def test_build_context_prefix_with_types(cls):
        """Test building context prefix with type definitions."""
        extractor = BaseContextExtractor("python")
        mock_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        items = [
            ContextItem(
                type=ContextType.IMPORT,
                content="import os",
                node=mock_node,
                line_number=1,
                importance=90,
            ),
            ContextItem(
                type=ContextType.TYPE_DEF,
                content="class MyClass: ...",
                node=mock_node,
                line_number=5,
                importance=80,
            ),
        ]
        result = extractor.build_context_prefix(items)
        expected = "import os\n\nclass MyClass: ..."
        assert result == expected

    @classmethod
    def test_build_context_prefix_with_max_size(cls):
        """Test building context prefix with size limit."""
        extractor = BaseContextExtractor("python")
        mock_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        items = [
            ContextItem(
                type=ContextType.IMPORT,
                content="import very_long_module_name_that_exceeds_limit",
                node=mock_node,
                line_number=1,
                importance=90,
            ),
        ]
        result = extractor.build_context_prefix(items, max_size=20)
        assert "truncated" in result
        assert len(result.split("\n")[0]) <= 20

    @classmethod
    def test_build_context_prefix_sorted_by_importance(cls):
        """Test that context items are sorted by importance."""
        extractor = BaseContextExtractor("python")
        mock_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        items = [
            ContextItem(
                type=ContextType.CONSTANT,
                content="CONST = 42",
                node=mock_node,
                line_number=10,
                importance=40,
            ),
            ContextItem(
                type=ContextType.IMPORT,
                content="import os",
                node=mock_node,
                line_number=1,
                importance=90,
            ),
            ContextItem(
                type=ContextType.TYPE_DEF,
                content="class MyClass: ...",
                node=mock_node,
                line_number=5,
                importance=80,
            ),
        ]
        result = extractor.build_context_prefix(items)
        lines = result.split("\n")
        assert lines[0] == "import os"
        assert "class MyClass" in result
        assert "CONST = 42" in result


class TestPythonContextExtractor:
    """Test Python-specific context extraction."""

    @staticmethod
    @pytest.fixture()
    def python_code():
        """Sample Python code for testing."""
        return """
import os
from typing import List, Dict

@dataclass
class User:
    name: str
    age: int

def process_users(users: List[User]) -> Dict[str, User]:
    ""\"Process a list of users.""\"
    result = {}
    for user in users:
        result[user.name] = user
    return result

class UserManager:
    def __init__(self):
        self.users = []

    def add_user(self, user: User):
        self.users.append(user)
""".strip()

    @staticmethod
    def test_extract_imports(python_code):
        """Test extracting imports from Python code."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())
        extractor = ContextFactory.create_context_extractor("python")
        imports = extractor.extract_imports(tree.root_node, python_code.encode())
        assert len(imports) == 2
        assert imports[0].type == ContextType.IMPORT
        assert imports[0].content == "import os"
        assert imports[1].content == "from typing import List, Dict"

    @staticmethod
    def test_extract_type_definitions(python_code):
        """Test extracting type definitions from Python code."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())
        extractor = ContextFactory.create_context_extractor("python")
        type_defs = extractor.extract_type_definitions(
            tree.root_node,
            python_code.encode(),
        )
        assert len(type_defs) == 2
        assert type_defs[0].type == ContextType.TYPE_DEF
        assert "class User:" in type_defs[0].content
        assert "..." in type_defs[0].content
        assert "class UserManager:" in type_defs[1].content

    @staticmethod
    def test_extract_decorators(python_code):
        """Test extracting decorators from Python code."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())
        extractor = ContextFactory.create_context_extractor("python")

        def find_class_node(node, name):
            if node.type == "class_definition":
                for child in node.children:
                    if child.type == "identifier" and child.text == name.encode():
                        return node
            for child in node.children:
                result = find_class_node(child, name)
                if result:
                    return result
            return None

        user_class = find_class_node(tree.root_node, "User")
        assert user_class is not None
        decorators = extractor.find_decorators(
            user_class,
            python_code.encode(),
        )
        assert len(decorators) == 1
        assert decorators[0].type == ContextType.DECORATOR
        assert decorators[0].content == "@dataclass"

    @staticmethod
    def test_extract_parent_context(python_code):
        """Test extracting parent context."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())
        extractor = ContextFactory.create_context_extractor("python")

        def find_method_node(node, method_name):
            if node.type == "function_definition":
                for child in node.children:
                    if (
                        child.type == "identifier"
                        and child.text == method_name.encode()
                    ):
                        return node
            for child in node.children:
                result = find_method_node(child, method_name)
                if result:
                    return result
            return None

        add_user_method = find_method_node(tree.root_node, "add_user")
        assert add_user_method is not None
        parent_context = extractor.extract_parent_context(
            add_user_method,
            tree.root_node,
            python_code.encode(),
        )
        assert len(parent_context) == 1
        assert parent_context[0].type == ContextType.PARENT_SCOPE
        assert "class UserManager:" in parent_context[0].content


class TestJavaScriptContextExtractor:
    """Test JavaScript-specific context extraction."""

    @staticmethod
    @pytest.fixture()
    def javascript_code():
        """Sample JavaScript code for testing."""
        return """
import { Component } from 'react';
import * as utils from './utils';

class UserList extends Component {
    constructor(props) {
        super(props);
        this.state = { users: [] };
    }

    addUser(user) {
        this.setState({
            users: [...this.state.users, user]
        });
    }
}

const processData = async (data) => {
    const result = await utils.process(data);
    return result.map(item => ({
        ...item,
        processed: true
    }));
};

export default UserList;
""".strip()

    @staticmethod
    def test_extract_imports(javascript_code):
        """Test extracting imports from JavaScript code."""
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())
        extractor = ContextFactory.create_context_extractor("javascript")
        imports = extractor.extract_imports(tree.root_node, javascript_code.encode())
        assert len(imports) == 2
        assert imports[0].type == ContextType.IMPORT
        assert "import { Component }" in imports[0].content
        assert "import * as utils" in imports[1].content

    @staticmethod
    def test_extract_type_definitions(javascript_code):
        """Test extracting class definitions from JavaScript code."""
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())
        extractor = ContextFactory.create_context_extractor("javascript")
        type_defs = extractor.extract_type_definitions(
            tree.root_node,
            javascript_code.encode(),
        )
        assert len(type_defs) == 1
        assert type_defs[0].type == ContextType.TYPE_DEF
        assert "class UserList extends Component" in type_defs[0].content
        assert "{ ... }" in type_defs[0].content

    @staticmethod
    def test_extract_parent_context(javascript_code):
        """Test extracting parent context in JavaScript."""
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())
        extractor = ContextFactory.create_context_extractor("javascript")

        def find_method_node(node, method_name):
            if node.type == "method_definition":
                for child in node.children:
                    if (
                        child.type == "property_identifier"
                        and child.text == method_name.encode()
                    ):
                        return node
            for child in node.children:
                result = find_method_node(child, method_name)
                if result:
                    return result
            return None

        add_user_method = find_method_node(tree.root_node, "addUser")
        assert add_user_method is not None
        parent_context = extractor.extract_parent_context(
            add_user_method,
            tree.root_node,
            javascript_code.encode(),
        )
        assert len(parent_context) >= 1
        assert any("class UserList" in ctx.content for ctx in parent_context)

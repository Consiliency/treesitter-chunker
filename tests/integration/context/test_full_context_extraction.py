"""Integration tests for full context extraction workflow."""

import pytest

from chunker.context import ContextFactory
from chunker.parser import get_parser
from chunker.chunker import chunk_file


class TestPythonContextExtraction:
    """Test full context extraction for Python code."""
    
    @pytest.fixture
    def complex_python_code(self):
        """Complex Python code with multiple contexts."""
        return '''
import os
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass
from functools import lru_cache

# Constants
MAX_CACHE_SIZE = 1000
DEFAULT_TIMEOUT = 30

@dataclass
class Config:
    """Configuration settings."""
    name: str
    value: int
    enabled: bool = True

class DatabaseManager:
    """Manages database connections."""
    
    def __init__(self, config: Config):
        self.config = config
        self._connection = None
    
    @property
    def is_connected(self) -> bool:
        return self._connection is not None
    
    @lru_cache(maxsize=MAX_CACHE_SIZE)
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        if not self.is_connected:
            raise RuntimeError("Not connected to database")
        
        # Simulate database query
        return {"id": user_id, "name": f"User{user_id}"}
    
    def update_user(self, user_id: int, data: Dict) -> bool:
        """Update user data."""
        user = self.get_user(user_id)
        if user:
            user.update(data)
            return True
        return False

def process_users(manager: DatabaseManager, user_ids: List[int]) -> Dict[int, Dict]:
    """Process multiple users."""
    results = {}
    
    for user_id in user_ids:
        try:
            user_data = manager.get_user(user_id)
            if user_data:
                results[user_id] = user_data
        except Exception as e:
            print(f"Error processing user {user_id}: {e}")
    
    return results

# Module-level function
def create_manager(name: str = "default") -> DatabaseManager:
    """Create a new database manager."""
    config = Config(name=name, value=42)
    return DatabaseManager(config)
'''.strip()
    
    def test_extract_full_context_for_method(self, complex_python_code):
        """Test extracting full context for a method."""
        parser = get_parser('python')
        tree = parser.parse(complex_python_code.encode())
        source = complex_python_code.encode()
        
        # Create context components
        extractor, resolver, analyzer, filter = ContextFactory.create_all('python')
        
        # Find the update_user method
        def find_method(node, class_name, method_name):
            if node.type == 'class_definition':
                # Check if this is the right class
                for child in node.children:
                    if child.type == 'identifier' and child.text == class_name.encode():
                        # Look for the method
                        for class_child in node.children:
                            if class_child.type == 'block':
                                for block_child in class_child.children:
                                    if block_child.type == 'function_definition':
                                        for func_child in block_child.children:
                                            if func_child.type == 'identifier' and func_child.text == method_name.encode():
                                                return block_child
            
            for child in node.children:
                result = find_method(child, class_name, method_name)
                if result:
                    return result
            return None
        
        update_method = find_method(tree.root_node, 'DatabaseManager', 'update_user')
        assert update_method is not None
        
        # Extract various context types
        imports = extractor.extract_imports(tree.root_node, source)
        type_defs = extractor.extract_type_definitions(tree.root_node, source)
        parent_context = extractor.extract_parent_context(update_method, tree.root_node, source)
        dependencies = extractor.extract_dependencies(update_method, tree.root_node, source)
        
        # Verify imports
        assert len(imports) > 0
        import_contents = [item.content for item in imports]
        assert any("typing import" in content for content in import_contents)
        assert any("dataclasses import" in content for content in import_contents)
        
        # Verify type definitions
        assert len(type_defs) >= 2  # Config and DatabaseManager
        type_contents = [item.content for item in type_defs]
        assert any("class Config" in content for content in type_contents)
        assert any("class DatabaseManager" in content for content in type_contents)
        
        # Verify parent context
        assert len(parent_context) == 1
        assert "class DatabaseManager" in parent_context[0].content
        
        # Filter relevant context
        all_context = imports + type_defs + parent_context + dependencies
        relevant_context = [
            item for item in all_context
            if filter.is_relevant(item, update_method)
        ]
        
        # Build context prefix
        context_prefix = extractor.build_context_prefix(relevant_context)
        assert "import" in context_prefix
        assert "class" in context_prefix
    
    def test_context_for_nested_function(self, complex_python_code):
        """Test context extraction for a nested function."""
        parser = get_parser('python')
        tree = parser.parse(complex_python_code.encode())
        source = complex_python_code.encode()
        
        extractor = ContextFactory.create_context_extractor('python')
        
        # Find the inner try block in process_users
        def find_try_block(node):
            if node.type == 'try_statement':
                return node
            for child in node.children:
                result = find_try_block(child)
                if result:
                    return result
            return None
        
        try_block = find_try_block(tree.root_node)
        assert try_block is not None
        
        # Get parent context
        parent_context = extractor.extract_parent_context(try_block, tree.root_node, source)
        assert len(parent_context) >= 1
        
        # Should include the process_users function
        context_contents = [item.content for item in parent_context]
        assert any("def process_users" in content for content in context_contents)
    
    def test_symbol_resolution(self, complex_python_code):
        """Test symbol resolution in context."""
        parser = get_parser('python')
        tree = parser.parse(complex_python_code.encode())
        
        resolver = ContextFactory.create_symbol_resolver('python')
        analyzer = ContextFactory.create_scope_analyzer('python')
        
        # Find the get_user method
        def find_method_body(node, method_name):
            if node.type == 'function_definition':
                for child in node.children:
                    if child.type == 'identifier' and child.text == method_name.encode():
                        # Find the block
                        for sibling in node.children:
                            if sibling.type == 'block':
                                return sibling
            for child in node.children:
                result = find_method_body(child, method_name)
                if result:
                    return result
            return None
        
        get_user_body = find_method_body(tree.root_node, 'get_user')
        assert get_user_body is not None
        
        # Get visible symbols
        visible = analyzer.get_visible_symbols(get_user_body, tree.root_node)
        assert isinstance(visible, set)
        
        # The method should see class-level and module-level symbols
        # Note: actual symbol names would need source bytes to extract


class TestJavaScriptContextExtraction:
    """Test full context extraction for JavaScript code."""
    
    @pytest.fixture
    def complex_javascript_code(self):
        """Complex JavaScript code with multiple contexts."""
        return '''
import React, { useState, useEffect } from 'react';
import { connect } from 'react-redux';
import * as api from './api';

const MAX_RETRIES = 3;
const TIMEOUT_MS = 5000;

// Type definitions (JSDoc style)
/**
 * @typedef {Object} User
 * @property {number} id
 * @property {string} name
 * @property {string} email
 */

class UserService {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.cache = new Map();
    }
    
    async getUser(userId) {
        if (this.cache.has(userId)) {
            return this.cache.get(userId);
        }
        
        const user = await this.apiClient.fetch(`/users/${userId}`);
        this.cache.set(userId, user);
        return user;
    }
    
    async updateUser(userId, data) {
        const user = await this.getUser(userId);
        const updated = { ...user, ...data };
        
        await this.apiClient.put(`/users/${userId}`, updated);
        this.cache.set(userId, updated);
        
        return updated;
    }
}

const UserList = ({ users, loadUsers }) => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    useEffect(() => {
        const fetchUsers = async () => {
            setLoading(true);
            try {
                await loadUsers();
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        
        fetchUsers();
    }, [loadUsers]);
    
    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error: {error}</div>;
    
    return (
        <ul>
            {users.map(user => (
                <li key={user.id}>{user.name}</li>
            ))}
        </ul>
    );
};

const mapStateToProps = state => ({
    users: state.users.list
});

const mapDispatchToProps = dispatch => ({
    loadUsers: () => dispatch(api.fetchUsers())
});

export default connect(mapStateToProps, mapDispatchToProps)(UserList);
'''.strip()
    
    def test_extract_full_context_for_class_method(self, complex_javascript_code):
        """Test extracting full context for a class method."""
        parser = get_parser('javascript')
        tree = parser.parse(complex_javascript_code.encode())
        source = complex_javascript_code.encode()
        
        # Create context components
        extractor, resolver, analyzer, filter = ContextFactory.create_all('javascript')
        
        # Find the updateUser method
        def find_method(node, method_name):
            if node.type == 'method_definition':
                for child in node.children:
                    if child.type == 'property_identifier' and child.text == method_name.encode():
                        return node
            for child in node.children:
                result = find_method(child, method_name)
                if result:
                    return result
            return None
        
        update_method = find_method(tree.root_node, 'updateUser')
        assert update_method is not None
        
        # Extract context
        imports = extractor.extract_imports(tree.root_node, source)
        type_defs = extractor.extract_type_definitions(tree.root_node, source)
        parent_context = extractor.extract_parent_context(update_method, tree.root_node, source)
        
        # Verify imports
        assert len(imports) > 0
        import_contents = [item.content for item in imports]
        assert any("import React" in content for content in import_contents)
        assert any("import * as api" in content for content in import_contents)
        
        # Verify parent context (UserService class)
        assert len(parent_context) >= 1
        assert any("class UserService" in ctx.content for ctx in parent_context)
    
    def test_context_for_react_component(self, complex_javascript_code):
        """Test context extraction for React component."""
        parser = get_parser('javascript')
        tree = parser.parse(complex_javascript_code.encode())
        source = complex_javascript_code.encode()
        
        extractor = ContextFactory.create_context_extractor('javascript')
        filter = ContextFactory.create_context_filter('javascript')
        
        # Find the UserList component
        def find_component(node, name):
            if node.type == 'variable_declarator':
                for child in node.children:
                    if child.type == 'identifier' and child.text == name.encode():
                        return node
            for child in node.children:
                result = find_component(child, name)
                if result:
                    return result
            return None
        
        user_list = find_component(tree.root_node, 'UserList')
        assert user_list is not None
        
        # Extract relevant imports
        imports = extractor.extract_imports(tree.root_node, source)
        relevant_imports = [
            imp for imp in imports 
            if filter.score_relevance(imp, user_list) > 0.5
        ]
        
        # Should include React imports
        import_contents = [item.content for item in relevant_imports]
        assert any("React" in content for content in import_contents)
    
    def test_scope_analysis_with_closures(self, complex_javascript_code):
        """Test scope analysis with JavaScript closures."""
        parser = get_parser('javascript')
        tree = parser.parse(complex_javascript_code.encode())
        
        analyzer = ContextFactory.create_scope_analyzer('javascript')
        
        # Find the fetchUsers arrow function inside useEffect
        def find_arrow_function(node, name):
            if node.type == 'arrow_function':
                # Check if it's assigned to the right variable
                parent = node.parent
                if parent and parent.type == 'variable_declarator':
                    for child in parent.children:
                        if child.type == 'identifier' and child.text == name.encode():
                            return node
            for child in node.children:
                result = find_arrow_function(child, name)
                if result:
                    return result
            return None
        
        fetch_users = find_arrow_function(tree.root_node, 'fetchUsers')
        assert fetch_users is not None
        
        # Get scope chain
        scope_chain = analyzer.get_scope_chain(fetch_users)
        assert len(scope_chain) >= 2  # fetchUsers -> useEffect callback -> UserList
        
        # Verify scope types
        scope_types = [analyzer.get_scope_type(scope) for scope in scope_chain]
        assert 'arrow' in scope_types or 'function' in scope_types
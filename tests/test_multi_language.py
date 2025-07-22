"""Tests for multi-language processing functionality."""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from chunker.multi_language import (
    LanguageDetectorImpl, ProjectAnalyzerImpl, MultiLanguageProcessorImpl
)
from chunker.interfaces.multi_language import (
    EmbeddedLanguageType, LanguageRegion, CrossLanguageReference
)
from chunker.types import CodeChunk


class TestLanguageDetector:
    """Test language detection functionality."""
    
    def setup_method(self):
        self.detector = LanguageDetectorImpl()
    
    def test_detect_from_extension(self):
        """Test language detection from file extensions."""
        test_cases = [
            ('test.py', 'python'),
            ('test.js', 'javascript'),
            ('test.jsx', 'javascript'),
            ('test.ts', 'typescript'),
            ('test.tsx', 'typescript'),
            ('test.java', 'java'),
            ('test.go', 'go'),
            ('test.rs', 'rust'),
            ('test.rb', 'ruby'),
            ('test.cpp', 'cpp'),
            ('test.c', 'c'),
            ('test.h', 'c'),
            ('test.hpp', 'cpp'),
            ('test.cs', 'csharp'),
            ('test.php', 'php'),
            ('test.swift', 'swift'),
            ('test.kt', 'kotlin'),
            ('test.html', 'html'),
            ('test.css', 'css'),
            ('test.json', 'json'),
            ('test.yaml', 'yaml'),
            ('test.yml', 'yaml'),
            ('test.md', 'markdown'),
            ('test.sql', 'sql'),
            ('test.graphql', 'graphql'),
            ('test.ipynb', 'jupyter'),
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for filename, expected_lang in test_cases:
                file_path = os.path.join(tmpdir, filename)
                with open(file_path, 'w') as f:
                    f.write('// test content')
                
                lang, confidence = self.detector.detect_from_file(file_path)
                assert lang == expected_lang
                assert confidence >= 0.8
    
    def test_detect_from_shebang(self):
        """Test language detection from shebang lines."""
        test_cases = [
            ('#!/usr/bin/env python3\nprint("hello")', 'python'),
            ('#!/usr/bin/python\nprint("hello")', 'python'),
            ('#!/usr/bin/env node\nconsole.log("hello")', 'javascript'),
            ('#!/usr/bin/ruby\nputs "hello"', 'ruby'),
            ('#!/bin/bash\necho "hello"', 'bash'),
            ('#!/bin/sh\necho "hello"', 'bash'),
            ('#!/usr/bin/env perl\nprint "hello\\n"', 'perl'),
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for content, expected_lang in test_cases:
                file_path = os.path.join(tmpdir, 'script')
                with open(file_path, 'w') as f:
                    f.write(content)
                
                lang, confidence = self.detector.detect_from_file(file_path)
                assert lang == expected_lang
                assert confidence >= 0.95
    
    def test_detect_from_content(self):
        """Test language detection from content patterns."""
        test_cases = [
            # Python
            ('import os\nimport sys\n\ndef main():\n    pass', 'python'),
            ('from pathlib import Path\n\nclass MyClass:\n    pass', 'python'),
            ('if __name__ == "__main__":\n    main()', 'python'),
            
            # JavaScript
            ('const fs = require("fs");\nfunction main() {}', 'javascript'),
            ('import React from "react";\nexport default App;', 'javascript'),
            ('let x = 5;\nconst y = 10;\nvar z = 15;', 'javascript'),
            
            # TypeScript
            ('interface User {\n  name: string;\n  age: number;\n}', 'typescript'),
            ('type Status = "active" | "inactive";', 'typescript'),
            ('enum Color { Red, Green, Blue }', 'typescript'),
            
            # Java
            ('package com.example;\n\npublic class Main {}', 'java'),
            ('import java.util.*;\n\nprivate String name;', 'java'),
            
            # Go
            ('package main\n\nimport "fmt"\n\nfunc main() {}', 'go'),
            ('type User struct {\n    Name string\n}', 'go'),
            
            # Rust
            ('use std::io;\n\nfn main() {}', 'rust'),
            ('pub struct User {\n    name: String\n}', 'rust'),
            ('let mut x = 5;', 'rust'),
            
            # Ruby
            ('require "json"\n\ndef hello\n  puts "Hello"\nend', 'ruby'),
            ('class User\n  attr_reader :name\nend', 'ruby'),
            
            # PHP
            ('<?php\nnamespace App;\n\nclass User {}', 'php'),
            ('<?php\n$name = "John";\nfunction test() {}', 'php'),
        ]
        
        for content, expected_lang in test_cases:
            lang, confidence = self.detector.detect_from_content(content)
            assert lang == expected_lang
            assert confidence > 0.5
    
    def test_detect_multiple_languages(self):
        """Test detection of multiple languages in content."""
        # Markdown with code blocks
        content = '''
# Documentation

Here's some Python code:

```python
def hello():
    print("Hello, World!")
```

And some JavaScript:

```javascript
function greet() {
    console.log("Hello, World!");
}
```
'''
        
        languages = self.detector.detect_multiple(content)
        lang_dict = dict(languages)
        
        # Should detect Python and JavaScript embedded in Markdown
        assert 'python' in lang_dict
        assert 'javascript' in lang_dict
        assert lang_dict['python'] > 0
        assert lang_dict['javascript'] > 0
    
    def test_detect_html_with_embedded(self):
        """Test detection in HTML with embedded scripts and styles."""
        content = '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; }
    </style>
</head>
<body>
    <script>
        console.log("Hello");
    </script>
</body>
</html>
'''
        
        languages = self.detector.detect_multiple(content)
        lang_dict = dict(languages)
        
        assert 'javascript' in lang_dict
        assert 'css' in lang_dict
    
    def test_detect_jsx_content(self):
        """Test detection of JSX content."""
        content = '''
import React from 'react';

const Component = () => {
    return <div className="container">Hello</div>;
};
'''
        
        languages = self.detector.detect_multiple(content)
        lang_dict = dict(languages)
        
        assert 'javascript' in lang_dict or 'typescript' in lang_dict


class TestProjectAnalyzer:
    """Test project structure analysis."""
    
    def setup_method(self):
        self.analyzer = ProjectAnalyzerImpl()
    
    def test_analyze_simple_project(self):
        """Test analysis of a simple project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_root = Path(tmpdir)
            
            # Create files
            (project_root / 'package.json').write_text('{}')
            (project_root / 'src').mkdir()
            (project_root / 'src' / 'index.js').write_text('console.log("hello");')
            (project_root / 'src' / 'utils.js').write_text('export function util() {}')
            (project_root / 'test').mkdir()
            (project_root / 'test' / 'test.js').write_text('describe("test", () => {});')
            
            analysis = self.analyzer.analyze_structure(str(project_root))
            
            assert analysis['file_count'] == 4
            assert 'javascript' in analysis['languages']
            assert analysis['languages']['javascript'] >= 3
            assert 'javascript' in analysis['framework_indicators']
            assert analysis['structure']['has_tests'] is True
            assert analysis['project_type'] in ['node_application', 'frontend_webapp']
    
    def test_analyze_fullstack_project(self):
        """Test analysis of a fullstack web application."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            
            # Backend structure
            (project_root / 'backend').mkdir()
            (project_root / 'backend' / 'requirements.txt').write_text('flask==2.0.0')
            (project_root / 'backend' / 'api').mkdir()
            (project_root / 'backend' / 'api' / 'routes.py').write_text('from flask import Flask')
            
            # Frontend structure
            (project_root / 'frontend').mkdir()
            (project_root / 'frontend' / 'package.json').write_text('{}')
            (project_root / 'frontend' / 'src').mkdir()
            (project_root / 'frontend' / 'src' / 'App.jsx').write_text('import React from "react";')
            
            analysis = self.analyzer.analyze_structure(str(project_root))
            
            assert analysis['structure']['has_backend'] is True
            assert analysis['structure']['has_frontend'] is True
            assert analysis['project_type'] == 'fullstack_webapp'
            assert 'python' in analysis['framework_indicators']
            assert 'javascript' in analysis['framework_indicators']
    
    def test_find_api_boundaries(self):
        """Test finding API boundaries between components."""
        chunks = [
            # Python backend endpoint
            CodeChunk(
                language='python',
                file_path='backend/api/users.py',
                node_type='function_definition',
                start_line=10,
                end_line=20,
                byte_start=100,
                byte_end=300,
                parent_context='',
                content='@app.route("/api/users")\ndef get_users():\n    return jsonify(users)'
            ),
            # JavaScript frontend call
            CodeChunk(
                language='javascript',
                file_path='frontend/src/api.js',
                node_type='function_definition',
                start_line=5,
                end_line=10,
                byte_start=50,
                byte_end=150,
                parent_context='',
                content='async function fetchUsers() {\n  return await fetch("/api/users");\n}'
            ),
        ]
        
        boundaries = self.analyzer.find_api_boundaries(chunks)
        
        assert len(boundaries) >= 1
        assert any(b['type'] == 'rest_endpoint' and b['endpoint'] == '/api/users' for b in boundaries)
    
    def test_suggest_chunk_grouping(self):
        """Test chunk grouping suggestions."""
        chunks = [
            CodeChunk(
                language='python',
                file_path='features/auth/backend/auth.py',
                node_type='class_definition',
                start_line=1,
                end_line=50,
                byte_start=0,
                byte_end=1000,
                parent_context='',
                content='class AuthService:\n    pass'
            ),
            CodeChunk(
                language='javascript',
                file_path='features/auth/frontend/Login.jsx',
                node_type='function_definition',
                start_line=1,
                end_line=30,
                byte_start=0,
                byte_end=600,
                parent_context='',
                content='function LoginForm() {}'
            ),
            CodeChunk(
                language='python',
                file_path='features/users/backend/users.py',
                node_type='class_definition',
                start_line=1,
                end_line=40,
                byte_start=0,
                byte_end=800,
                parent_context='',
                content='class UserService:\n    pass'
            ),
        ]
        
        groupings = self.analyzer.suggest_chunk_grouping(chunks)
        
        # Should group by feature
        assert 'feature_auth' in groupings
        assert len(groupings['feature_auth']) == 2
        assert 'feature_users' in groupings
        assert len(groupings['feature_users']) == 1
        
        # Should also group by language
        assert 'lang_python' in groupings
        assert 'lang_javascript' in groupings


class TestMultiLanguageProcessor:
    """Test multi-language processing."""
    
    def setup_method(self):
        self.processor = MultiLanguageProcessorImpl()
    
    def test_detect_project_languages(self):
        """Test project language detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            
            # Create mixed language project
            (project_root / 'main.py').write_text('print("hello")')
            (project_root / 'app.js').write_text('console.log("hello")')
            (project_root / 'styles.css').write_text('body { margin: 0; }')
            (project_root / 'index.html').write_text('<html></html>')
            
            languages = self.processor.detect_project_languages(str(project_root))
            
            assert 'python' in languages
            assert 'javascript' in languages
            assert 'css' in languages
            assert 'html' in languages
            assert sum(languages.values()) == pytest.approx(1.0, rel=0.01)
    
    def test_identify_jsx_regions(self):
        """Test identification of regions in JSX files."""
        content = '''
import React from 'react';

const Component = () => {
    const style = {
        color: 'red',
        fontSize: '16px'
    };
    
    return (
        <div style={{backgroundColor: 'blue'}}>
            <h1>Hello</h1>
        </div>
    );
};
'''
        
        regions = self.processor.identify_language_regions('component.jsx', content)
        
        # Should identify main JavaScript region
        assert any(r.language == 'javascript' for r in regions)
        
        # Should identify embedded CSS in style props
        css_regions = [r for r in regions if r.language == 'css']
        assert len(css_regions) > 0
        assert css_regions[0].embedding_type == EmbeddedLanguageType.STYLE
    
    def test_identify_html_regions(self):
        """Test identification of regions in HTML files."""
        content = '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            margin: 0;
            padding: 0;
        }
    </style>
</head>
<body>
    <h1>Hello</h1>
    <script>
        console.log("Page loaded");
        document.getElementById("btn").onclick = function() {
            alert("Clicked!");
        };
    </script>
</body>
</html>
'''
        
        regions = self.processor.identify_language_regions('index.html', content)
        
        # Should have HTML, CSS, and JavaScript regions
        languages = {r.language for r in regions}
        assert 'html' in languages
        assert 'css' in languages
        assert 'javascript' in languages
        
        # Check embedding types
        css_region = next(r for r in regions if r.language == 'css')
        assert css_region.embedding_type == EmbeddedLanguageType.STYLE
        assert css_region.parent_language == 'html'
        
        js_region = next(r for r in regions if r.language == 'javascript')
        assert js_region.embedding_type == EmbeddedLanguageType.SCRIPT
        assert js_region.parent_language == 'html'
    
    def test_identify_markdown_regions(self):
        """Test identification of code blocks in Markdown."""
        content = '''
# Documentation

Here's a Python example:

```python
def greet(name):
    return f"Hello, {name}!"
```

And a JavaScript example:

```javascript
function greet(name) {
    return `Hello, ${name}!`;
}
```

Some inline SQL: `SELECT * FROM users`
'''
        
        regions = self.processor.identify_language_regions('README.md', content)
        
        # Should identify markdown and embedded code
        languages = {r.language for r in regions}
        assert 'markdown' in languages
        assert 'python' in languages
        assert 'javascript' in languages
        
        # Check code block regions
        code_regions = [r for r in regions if r.embedding_type == EmbeddedLanguageType.DOCUMENTATION]
        assert len(code_regions) >= 2
    
    def test_identify_notebook_regions(self):
        """Test identification of regions in Jupyter notebooks."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# Title\n", "Some documentation"]
                },
                {
                    "cell_type": "code",
                    "source": ["import pandas as pd\n", "df = pd.DataFrame()"]
                },
                {
                    "cell_type": "code",
                    "source": ["print(df.head())"]
                }
            ],
            "metadata": {
                "language_info": {
                    "name": "python"
                }
            }
        }
        
        content = json.dumps(notebook_content)
        regions = self.processor.identify_language_regions('notebook.ipynb', content)
        
        # Should identify markdown and python regions
        languages = {r.language for r in regions}
        assert 'markdown' in languages
        assert 'python' in languages
        
        # Check region types
        markdown_regions = [r for r in regions if r.language == 'markdown']
        assert markdown_regions[0].embedding_type == EmbeddedLanguageType.DOCUMENTATION
        
        python_regions = [r for r in regions if r.language == 'python']
        assert all(r.embedding_type == EmbeddedLanguageType.SCRIPT for r in python_regions)
    
    def test_extract_embedded_sql(self):
        """Test extraction of embedded SQL queries."""
        content = '''
def get_users():
    query = "SELECT id, name FROM users WHERE active = true"
    return db.execute(query)
    
def update_user(user_id, name):
    sql = """
        UPDATE users 
        SET name = %s 
        WHERE id = %s
    """
    return db.execute(sql, (name, user_id))
'''
        
        snippets = self.processor.extract_embedded_code(content, 'python', 'sql')
        
        assert len(snippets) >= 2
        assert any('SELECT' in s[0] for s in snippets)
        assert any('UPDATE' in s[0] for s in snippets)
    
    def test_extract_embedded_graphql(self):
        """Test extraction of embedded GraphQL queries."""
        content = '''
const GET_USER = gql`
  query GetUser($id: ID!) {
    user(id: $id) {
      name
      email
    }
  }
`;

const query = graphql('{ users { id name } }');
'''
        
        snippets = self.processor.extract_embedded_code(content, 'javascript', 'graphql')
        
        assert len(snippets) >= 2
        assert any('query GetUser' in s[0] for s in snippets)
        assert any('users { id name }' in s[0] for s in snippets)
    
    @patch('chunker.multi_language.get_parser')
    @patch('chunker.multi_language.chunk_file')
    def test_process_mixed_file(self, mock_chunk_file, mock_get_parser):
        """Test processing files with multiple languages."""
        # Mock parser and chunk_file
        mock_parser = MagicMock()
        mock_get_parser.return_value = mock_parser
        mock_chunk_file.return_value = [
            CodeChunk(
                language='javascript',
                file_path='test.jsx',
                node_type='function_definition',
                start_line=1,
                end_line=10,
                byte_start=0,
                byte_end=200,
                parent_context='',
                content='function Component() {}'
            )
        ]
        
        content = '''
import React from 'react';

function Component() {
    return <div style={{color: 'red'}}>Hello</div>;
}
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsx', delete=False) as f:
            f.write(content)
            f.flush()
            
            chunks = self.processor.process_mixed_file(f.name, 'javascript')
            
            assert len(chunks) > 0
            assert chunks[0].language == 'javascript'
            
            os.unlink(f.name)
    
    def test_cross_language_references(self):
        """Test finding cross-language references."""
        chunks = [
            # Python API endpoint
            CodeChunk(
                language='python',
                file_path='backend/api.py',
                node_type='function_definition',
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context='',
                content='@app.get("/api/users")\nasync def get_users():\n    return users'
            ),
            # JavaScript API call
            CodeChunk(
                language='javascript',
                file_path='frontend/api.js',
                node_type='function_definition',
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context='',
                content='async function loadUsers() {\n  return fetch("/api/users");\n}'
            ),
            # TypeScript interface
            CodeChunk(
                language='typescript',
                file_path='shared/types.ts',
                node_type='interface_declaration',
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context='',
                content='interface User {\n  id: string;\n  name: string;\n}'
            ),
            # Go struct with same name
            CodeChunk(
                language='go',
                file_path='backend/models.go',
                node_type='struct_declaration',
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context='',
                content='type User struct {\n  ID   string\n  Name string\n}'
            ),
        ]
        
        references = self.processor.cross_language_references(chunks)
        
        # Should find API call reference
        api_refs = [r for r in references if r.reference_type == 'api_call']
        assert len(api_refs) > 0
        assert api_refs[0].source_chunk.language == 'javascript'
        assert api_refs[0].target_chunk.language == 'python'
        
        # Should find shared type reference
        type_refs = [r for r in references if r.reference_type == 'shared_type']
        assert len(type_refs) > 0
    
    def test_group_by_feature(self):
        """Test grouping chunks by feature."""
        chunks = [
            # Auth feature - backend
            CodeChunk(
                language='python',
                file_path='features/auth/backend/auth_service.py',
                node_type='class_definition',
                start_line=1,
                end_line=50,
                byte_start=0,
                byte_end=1000,
                parent_context='',
                content='class AuthService:\n    def login(self): pass'
            ),
            # Auth feature - frontend
            CodeChunk(
                language='javascript',
                file_path='features/auth/frontend/LoginComponent.jsx',
                node_type='function_definition',
                start_line=1,
                end_line=30,
                byte_start=0,
                byte_end=600,
                parent_context='',
                content='function LoginComponent() {}'
            ),
            # User feature - backend
            CodeChunk(
                language='python',
                file_path='features/users/backend/user_service.py',
                node_type='class_definition',
                start_line=1,
                end_line=40,
                byte_start=0,
                byte_end=800,
                parent_context='',
                content='class UserService:\n    def get_user(self): pass'
            ),
            # Shared UserController
            CodeChunk(
                language='java',
                file_path='src/controllers/UserController.java',
                node_type='class_definition',
                start_line=1,
                end_line=60,
                byte_start=0,
                byte_end=1200,
                parent_context='',
                content='public class UserController {}'
            ),
        ]
        
        groups = self.processor.group_by_feature(chunks)
        
        # Should group by feature directory
        assert 'auth' in groups
        assert len(groups['auth']) == 2
        assert all(c.file_path.find('auth') != -1 for c in groups['auth'])
        
        assert 'users' in groups
        assert len(groups['users']) == 2  # UserService and UserController
        
        # Should also create entity-based groups
        assert any('user' in k.lower() for k in groups.keys())
    
    def test_embedded_language_detection(self):
        """Test detection of various embedded language scenarios."""
        # Test SQL in Python
        python_content = '''
def get_data():
    query = """
        SELECT u.id, u.name, p.title
        FROM users u
        JOIN posts p ON u.id = p.user_id
        WHERE u.active = true
    """
    return db.execute(query)
'''
        
        regions = self.processor.identify_language_regions('data.py', python_content)
        embedded = self.processor._identify_embedded_regions(python_content, 'python')
        
        assert any(r.language == 'sql' for r in embedded)
        sql_region = next(r for r in embedded if r.language == 'sql')
        assert sql_region.embedding_type == EmbeddedLanguageType.QUERY
        
        # Test JSON in JavaScript
        js_content = '''
const config = '{"api": {"endpoint": "https://api.example.com", "key": "secret"}}';
const data = JSON.parse(config);
'''
        
        embedded = self.processor._identify_embedded_regions(js_content, 'javascript')
        assert any(r.language == 'json' for r in embedded)
        json_region = next(r for r in embedded if r.language == 'json')
        assert json_region.embedding_type == EmbeddedLanguageType.CONFIGURATION


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    def setup_method(self):
        self.processor = MultiLanguageProcessorImpl()
    
    def test_react_typescript_project(self):
        """Test processing a React TypeScript project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            
            # Create project structure
            (project_root / 'src').mkdir()
            (project_root / 'src' / 'components').mkdir()
            
            # TypeScript component with JSX
            component_content = '''
import React, { useState } from 'react';
import './Button.css';

interface ButtonProps {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary';
}

export const Button: React.FC<ButtonProps> = ({ label, onClick, variant = 'primary' }) => {
    const [isHovered, setIsHovered] = useState(false);
    
    return (
        <button
            className={`btn btn-${variant} ${isHovered ? 'hovered' : ''}`}
            onClick={onClick}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            style={{
                backgroundColor: variant === 'primary' ? '#007bff' : '#6c757d',
                color: 'white'
            }}
        >
            {label}
        </button>
    );
};
'''
            
            (project_root / 'src' / 'components' / 'Button.tsx').write_text(component_content)
            
            # CSS file
            css_content = '''
.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn.hovered {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}
'''
            
            (project_root / 'src' / 'components' / 'Button.css').write_text(css_content)
            
            # Process the component file
            regions = self.processor.identify_language_regions(
                str(project_root / 'src' / 'components' / 'Button.tsx'),
                component_content
            )
            
            # Should identify TypeScript and embedded CSS
            languages = {r.language for r in regions}
            assert 'typescript' in languages
            
            # Should find CSS in style prop
            css_regions = [r for r in regions if r.language == 'css' and r.embedding_type == EmbeddedLanguageType.STYLE]
            assert len(css_regions) > 0
    
    def test_fullstack_api_integration(self):
        """Test processing a fullstack application with API integration."""
        # Backend Python/Flask
        backend_chunk = CodeChunk(
            language='python',
            file_path='backend/api/users.py',
            node_type='function_definition',
            start_line=10,
            end_line=25,
            byte_start=200,
            byte_end=500,
            parent_context='UsersAPI',
            content='''
@app.route('/api/v1/users', methods=['GET'])
def get_users():
    """Get all users with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    users = User.query.paginate(page=page, per_page=per_page)
    return jsonify({
        'users': [u.to_dict() for u in users.items],
        'total': users.total,
        'page': page,
        'pages': users.pages
    })
'''
        )
        
        # Frontend TypeScript/React
        frontend_chunk = CodeChunk(
            language='typescript',
            file_path='frontend/src/services/userService.ts',
            node_type='function_definition',
            start_line=5,
            end_line=20,
            byte_start=100,
            byte_end=400,
            parent_context='',
            content='''
export async function fetchUsers(page: number = 1, perPage: number = 10): Promise<UserResponse> {
    const response = await fetch(`/api/v1/users?page=${page}&per_page=${perPage}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch users');
    }
    
    return response.json();
}
'''
        )
        
        # Shared TypeScript interface
        interface_chunk = CodeChunk(
            language='typescript',
            file_path='shared/types/user.ts',
            node_type='interface_declaration',
            start_line=1,
            end_line=10,
            byte_start=0,
            byte_end=200,
            parent_context='',
            content='''
export interface User {
    id: number;
    username: string;
    email: string;
    created_at: string;
    updated_at: string;
}

export interface UserResponse {
    users: User[];
    total: number;
    page: number;
    pages: number;
}
'''
        )
        
        chunks = [backend_chunk, frontend_chunk, interface_chunk]
        
        # Find cross-language references
        references = self.processor.cross_language_references(chunks)
        
        # Should find API call reference
        api_refs = [r for r in references if r.reference_type == 'api_call']
        assert len(api_refs) > 0
        assert any(ref.source_chunk.language == 'typescript' and ref.target_chunk.language == 'python' for ref in api_refs)
        
        # Group by feature
        groups = self.processor.group_by_feature(chunks)
        
        # Should group user-related chunks
        user_groups = [g for name, g in groups.items() if 'user' in name.lower()]
        assert len(user_groups) > 0
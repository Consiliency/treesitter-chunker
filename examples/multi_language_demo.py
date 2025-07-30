#!/usr/bin/env python3
"""Demo script for multi-language processing capabilities."""

import tempfile
from pathlib import Path

from chunker.multi_language import (
    LanguageDetectorImpl,
    MultiLanguageProcessorImpl,
    ProjectAnalyzerImpl,
)
from chunker.types import CodeChunk


def demo_language_detection():
    """Demonstrate language detection capabilities."""
    print("=== Language Detection Demo ===\n")

    detector = LanguageDetectorImpl()

    # Test content samples
    samples = {
        "Python": '''
def calculate_fibonacci(n):
    """Calculate nth Fibonacci number."""
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
''',
        "JavaScript/React": """
import React, { useState } from 'react';

const Counter = () => {
    const [count, setCount] = useState(0);

    return (
        <div className="counter">
            <h1>Count: {count}</h1>
            <button onClick={() => setCount(count + 1)}>
                Increment
            </button>
        </div>
    );
};

export default Counter;
""",
        "HTML with embedded JS/CSS": """
<!DOCTYPE html>
<html>
<head>
    <style>
        .highlight {
            background-color: yellow;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1 id="title">Hello World</h1>
    <script>
        document.getElementById('title').onclick = function() {
            this.classList.toggle('highlight');
        };
    </script>
</body>
</html>
""",
    }

    for name, content in samples.items():
        lang, confidence = detector.detect_from_content(content)
        print(f"{name}: Detected as {lang} (confidence: {confidence:.2f})")

        # Also check for multiple languages
        languages = detector.detect_multiple(content)
        if len(languages) > 1:
            print(
                f"  Multiple languages detected: {', '.join(f'{l}({p:.1%})' for l, p in languages)}",
            )

    print()


def demo_embedded_language_detection():
    """Demonstrate detection of embedded languages."""
    print("=== Embedded Language Detection Demo ===\n")

    processor = MultiLanguageProcessorImpl()

    # Python with embedded SQL
    python_sql = '''
import sqlite3

def get_active_users(conn):
    """Get all active users from database."""
    query = """
        SELECT u.id, u.username, u.email, p.name as profile_name
        FROM users u
        JOIN profiles p ON u.id = p.user_id
        WHERE u.is_active = 1
        ORDER BY u.created_at DESC
    """

    cursor = conn.execute(query)
    return cursor.fetchall()
'''

    regions = processor.identify_language_regions("db_query.py", python_sql)
    print("Python file with embedded SQL:")
    for region in regions:
        print(f"  - {region.language} ({region.start_line}-{region.end_line})")
        if region.embedding_type:
            print(f"    Type: {region.embedding_type.value}")

    # Extract just the SQL
    sql_snippets = processor.extract_embedded_code(python_sql, "python", "sql")
    print(f"\nExtracted {len(sql_snippets)} SQL snippet(s)")

    print()


def demo_cross_language_references():
    """Demonstrate cross-language reference detection."""
    print("=== Cross-Language Reference Detection Demo ===\n")

    processor = MultiLanguageProcessorImpl()

    # Create sample chunks representing a simple API
    chunks = [
        # Python backend
        CodeChunk(
            language="python",
            file_path="backend/api/auth.py",
            node_type="function_definition",
            start_line=10,
            end_line=20,
            byte_start=200,
            byte_end=400,
            parent_context="",
            content='''
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Handle user login."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        token = generate_token(user.id)
        return jsonify({'token': token, 'user_id': user.id})

    return jsonify({'error': 'Invalid credentials'}), 401
''',
        ),
        # TypeScript frontend
        CodeChunk(
            language="typescript",
            file_path="frontend/src/services/auth.ts",
            node_type="function_definition",
            start_line=5,
            end_line=15,
            byte_start=100,
            byte_end=300,
            parent_context="",
            content="""
export async function login(username: string, password: string): Promise<AuthResponse> {
    const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });

    if (!response.ok) {
        throw new Error('Login failed');
    }

    return response.json();
}
""",
        ),
        # Shared TypeScript interface
        CodeChunk(
            language="typescript",
            file_path="shared/types/auth.ts",
            node_type="interface_declaration",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="""
export interface AuthResponse {
    token: string;
    user_id: number;
}
""",
        ),
    ]

    references = processor.cross_language_references(chunks)
    print(f"Found {len(references)} cross-language reference(s):")
    for ref in references:
        print(f"  - {ref.source_chunk.language} -> {ref.target_chunk.language}")
        print(f"    Type: {ref.reference_type}")
        print(f"    Source: {Path(ref.source_chunk.file_path).name}")
        print(f"    Target: {Path(ref.target_chunk.file_path).name}")
        print(f"    Confidence: {ref.confidence:.2f}")

    print()


def demo_feature_grouping():
    """Demonstrate grouping chunks by feature."""
    print("=== Feature Grouping Demo ===\n")

    processor = MultiLanguageProcessorImpl()

    # Create chunks representing different features
    chunks = [
        # User feature - backend
        CodeChunk(
            language="python",
            file_path="features/users/backend/user_service.py",
            node_type="class_definition",
            start_line=1,
            end_line=50,
            byte_start=0,
            byte_end=1000,
            parent_context="",
            content="class UserService:\n    def get_user(self, user_id): pass",
        ),
        CodeChunk(
            language="python",
            file_path="features/users/backend/user_model.py",
            node_type="class_definition",
            start_line=1,
            end_line=30,
            byte_start=0,
            byte_end=600,
            parent_context="",
            content="class User:\n    pass",
        ),
        # User feature - frontend
        CodeChunk(
            language="typescript",
            file_path="features/users/frontend/UserProfile.tsx",
            node_type="function_definition",
            start_line=1,
            end_line=40,
            byte_start=0,
            byte_end=800,
            parent_context="",
            content="export const UserProfile: React.FC = () => {}",
        ),
        # Auth feature
        CodeChunk(
            language="python",
            file_path="features/auth/backend/auth_service.py",
            node_type="class_definition",
            start_line=1,
            end_line=60,
            byte_start=0,
            byte_end=1200,
            parent_context="",
            content="class AuthService:\n    def login(self): pass",
        ),
        # Shared user-related component
        CodeChunk(
            language="java",
            file_path="shared/controllers/UserController.java",
            node_type="class_definition",
            start_line=1,
            end_line=80,
            byte_start=0,
            byte_end=1600,
            parent_context="",
            content="public class UserController {}",
        ),
    ]

    groups = processor.group_by_feature(chunks)
    print(f"Grouped {len(chunks)} chunks into {len(groups)} groups:\n")

    for group_name, group_chunks in groups.items():
        print(f"{group_name}:")
        for chunk in group_chunks:
            print(f"  - {Path(chunk.file_path).name} ({chunk.language})")
        print()


def demo_project_analysis():
    """Demonstrate project structure analysis."""
    print("=== Project Analysis Demo ===\n")

    analyzer = ProjectAnalyzerImpl()

    # Create a mock project structure

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project structure
        project_root = Path(tmpdir) / "my-fullstack-app"
        project_root.mkdir()

        # Backend structure
        backend = project_root / "backend"
        backend.mkdir()
        (backend / "requirements.txt").write_text("flask==2.0.0\nsqlalchemy==1.4.0\n")

        api_dir = backend / "api"
        api_dir.mkdir()
        (api_dir / "users.py").write_text(
            "from flask import Blueprint\n\nusers_bp = Blueprint('users', __name__)",
        )
        (api_dir / "auth.py").write_text(
            "from flask import Blueprint\n\nauth_bp = Blueprint('auth', __name__)",
        )

        # Frontend structure
        frontend = project_root / "frontend"
        frontend.mkdir()
        (frontend / "package.json").write_text(
            '{"name": "my-app", "dependencies": {"react": "^18.0.0"}}',
        )

        src_dir = frontend / "src"
        src_dir.mkdir()
        (src_dir / "App.tsx").write_text(
            "import React from 'react';\n\nexport const App = () => <div>Hello</div>;",
        )
        (src_dir / "index.js").write_text(
            "import { App } from './App';\n\nReactDOM.render(<App />, document.getElementById('root'));",
        )

        # Tests
        tests = project_root / "tests"
        tests.mkdir()
        (tests / "test_api.py").write_text(
            "import pytest\n\ndef test_users_endpoint():\n    pass",
        )

        # Analyze the project
        analysis = analyzer.analyze_structure(str(project_root))

        print(f"Project: {analysis['project_path']}")
        print(f"Type: {analysis['project_type']}")
        print(f"Total files: {analysis['file_count']}")
        print(f"Total lines: {analysis['total_lines']}")
        print("\nLanguages detected:")
        for lang, count in analysis["languages"].items():
            print(f"  - {lang}: {count} files")
        print("\nProject structure:")
        for key, value in analysis["structure"].items():
            print(f"  - {key}: {value}")
        print("\nFramework indicators:")
        for indicator in analysis["framework_indicators"]:
            print(f"  - {indicator}")


if __name__ == "__main__":
    demo_language_detection()
    demo_embedded_language_detection()
    demo_cross_language_references()
    demo_feature_grouping()
    demo_project_analysis()

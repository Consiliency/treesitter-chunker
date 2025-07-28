"""Comprehensive tests for SQL language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.sql import SQLPlugin


class TestSQLBasicChunking:
    """Test basic SQL chunking functionality."""

    def test_simple_create_table(self, tmp_path):
        """Test basic CREATE TABLE statement."""
        src = tmp_path / "schema.sql"
        src.write_text(
            """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""",
        )
        chunks = chunk_file(src, "sql")
        assert len(chunks) >= 1

        # Check for CREATE TABLE statement
        assert any(c.node_type == "create_table_statement" for c in chunks)
        table_chunk = next(c for c in chunks if c.node_type == "create_table_statement")
        assert "users" in table_chunk.content
        assert "id INTEGER PRIMARY KEY" in table_chunk.content

    def test_multiple_statements(self, tmp_path):
        """Test file with multiple SQL statements."""
        src = tmp_path / "database.sql"
        src.write_text(
            """-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100)
);

-- Create posts table
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(200),
    content TEXT
);

-- Create index
CREATE INDEX idx_posts_user_id ON posts(user_id);

-- Sample select
SELECT u.name, COUNT(p.id) as post_count
FROM users u
LEFT JOIN posts p ON u.id = p.user_id
GROUP BY u.name;
""",
        )
        chunks = chunk_file(src, "sql")

        # Check for different statement types
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "create_table_statement" in chunk_types
        assert "create_index_statement" in chunk_types
        assert "select_statement" in chunk_types
        assert "comment" in chunk_types

        # Verify we have 2 CREATE TABLE statements
        create_table_chunks = [
            c for c in chunks if c.node_type == "create_table_statement"
        ]
        assert len(create_table_chunks) == 2

    def test_create_function(self, tmp_path):
        """Test CREATE FUNCTION statement."""
        src = tmp_path / "functions.sql"
        src.write_text(
            """CREATE FUNCTION calculate_age(birth_date DATE)
RETURNS INTEGER AS $$
BEGIN
    RETURN DATE_PART('year', AGE(birth_date));
END;
$$ LANGUAGE plpgsql;
""",
        )
        chunks = chunk_file(src, "sql")

        # Check for function definition
        function_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(function_chunks) >= 1
        assert any("calculate_age" in c.content for c in function_chunks)

    def test_create_procedure(self, tmp_path):
        """Test CREATE PROCEDURE statement."""
        src = tmp_path / "procedures.sql"
        src.write_text(
            """CREATE PROCEDURE update_user_stats()
LANGUAGE SQL
AS $$
    UPDATE users
    SET last_active = NOW()
    WHERE id = current_user_id();
$$;
""",
        )
        chunks = chunk_file(src, "sql")

        # Check for procedure definition
        procedure_chunks = [c for c in chunks if "procedure" in c.node_type]
        assert len(procedure_chunks) >= 1
        assert any("update_user_stats" in c.content for c in procedure_chunks)

    def test_complex_select_with_cte(self, tmp_path):
        """Test complex SELECT with Common Table Expression."""
        src = tmp_path / "complex_query.sql"
        src.write_text(
            """WITH user_stats AS (
    SELECT
        user_id,
        COUNT(*) as post_count,
        MAX(created_at) as last_post
    FROM posts
    GROUP BY user_id
)
SELECT
    u.name,
    us.post_count,
    us.last_post
FROM users u
INNER JOIN user_stats us ON u.id = us.user_id
WHERE us.post_count > 10
ORDER BY us.post_count DESC;
""",
        )
        chunks = chunk_file(src, "sql")

        # Should have chunks for CTE and main SELECT
        assert any("WITH user_stats AS" in c.content for c in chunks)
        select_chunks = [c for c in chunks if c.node_type == "select_statement"]
        assert len(select_chunks) >= 1


class TestSQLContractCompliance:
    """Test ExtendedLanguagePluginContract compliance."""

    def test_implements_contract(self):
        """Verify SQLPlugin implements ExtendedLanguagePluginContract."""
        assert issubclass(SQLPlugin, ExtendedLanguagePluginContract)

    def test_get_semantic_chunks(self, tmp_path):
        """Test get_semantic_chunks method."""
        plugin = SQLPlugin()

        # Create a simple SQL file
        source = b"""CREATE TABLE test (id INT);
SELECT * FROM test;
"""

        # Parse the source (mock tree-sitter node)
        from chunker import get_parser

        parser = get_parser("sql")
        plugin.set_parser(parser)
        tree = parser.parse(source)

        chunks = plugin.get_semantic_chunks(tree.root_node, source)
        assert len(chunks) >= 2
        assert all("type" in chunk for chunk in chunks)
        assert all("start_line" in chunk for chunk in chunks)
        assert all("end_line" in chunk for chunk in chunks)
        assert all("content" in chunk for chunk in chunks)

    def test_get_chunk_node_types(self):
        """Test get_chunk_node_types method."""
        plugin = SQLPlugin()
        node_types = plugin.get_chunk_node_types()

        assert isinstance(node_types, set)
        assert len(node_types) > 0
        assert "create_table_statement" in node_types
        assert "select_statement" in node_types
        assert "function_definition" in node_types

    def test_should_chunk_node(self):
        """Test should_chunk_node method."""
        plugin = SQLPlugin()

        # Mock nodes
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type

        # Test statement nodes
        assert plugin.should_chunk_node(MockNode("create_table_statement"))
        assert plugin.should_chunk_node(MockNode("select_statement"))
        assert plugin.should_chunk_node(MockNode("function_definition"))
        assert plugin.should_chunk_node(MockNode("comment"))

        # Test non-chunk nodes
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("string"))

    def test_get_node_context(self):
        """Test get_node_context method."""
        plugin = SQLPlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test CREATE context
        node = MockNode("create_table_statement")
        context = plugin.get_node_context(node, b"CREATE TABLE users")
        assert context is not None
        assert "CREATE TABLE" in context


class TestSQLEdgeCases:
    """Test edge cases in SQL parsing."""

    def test_empty_sql_file(self, tmp_path):
        """Test empty SQL file."""
        src = tmp_path / "empty.sql"
        src.write_text("")
        chunks = chunk_file(src, "sql")
        assert len(chunks) == 0

    def test_sql_with_only_comments(self, tmp_path):
        """Test SQL file with only comments."""
        src = tmp_path / "comments.sql"
        src.write_text(
            """-- This is a comment
-- Another comment
/* Multi-line
   comment */
""",
        )
        chunks = chunk_file(src, "sql")
        assert all(c.node_type == "comment" for c in chunks)

    def test_sql_with_transactions(self, tmp_path):
        """Test SQL with transaction blocks."""
        src = tmp_path / "transaction.sql"
        src.write_text(
            """BEGIN;

INSERT INTO users (name) VALUES ('Alice');
INSERT INTO users (name) VALUES ('Bob');

UPDATE users SET active = true WHERE name IN ('Alice', 'Bob');

COMMIT;
""",
        )
        chunks = chunk_file(src, "sql")

        # Check for INSERT and UPDATE statements
        insert_chunks = [c for c in chunks if c.node_type == "insert_statement"]
        assert len(insert_chunks) == 2

        update_chunks = [c for c in chunks if c.node_type == "update_statement"]
        assert len(update_chunks) == 1

    def test_sql_with_views(self, tmp_path):
        """Test SQL with CREATE VIEW statements."""
        src = tmp_path / "views.sql"
        src.write_text(
            """CREATE VIEW active_users AS
SELECT id, name, email
FROM users
WHERE active = true AND deleted_at IS NULL;

CREATE OR REPLACE VIEW user_statistics AS
SELECT
    u.id,
    u.name,
    COUNT(p.id) as post_count,
    COUNT(c.id) as comment_count
FROM users u
LEFT JOIN posts p ON u.id = p.user_id
LEFT JOIN comments c ON u.id = c.user_id
GROUP BY u.id, u.name;
""",
        )
        chunks = chunk_file(src, "sql")

        # Check for CREATE VIEW statements
        view_chunks = [c for c in chunks if c.node_type == "create_view_statement"]
        assert len(view_chunks) >= 2
        assert any("active_users" in c.content for c in view_chunks)
        assert any("user_statistics" in c.content for c in view_chunks)

    def test_sql_with_triggers(self, tmp_path):
        """Test SQL with CREATE TRIGGER statements."""
        src = tmp_path / "triggers.sql"
        src.write_text(
            """CREATE TRIGGER update_modified_time
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER log_user_changes
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW
EXECUTE FUNCTION audit_user_changes();
""",
        )
        chunks = chunk_file(src, "sql")

        # Check for CREATE TRIGGER statements
        trigger_chunks = [c for c in chunks if "trigger" in c.node_type]
        assert len(trigger_chunks) >= 2
        assert any("update_modified_time" in c.content for c in trigger_chunks)
        assert any("log_user_changes" in c.content for c in trigger_chunks)

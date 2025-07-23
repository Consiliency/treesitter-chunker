#!/usr/bin/env python3
"""Demo script showing PostgreSQL exporter advanced features."""

from pathlib import Path
import tempfile
from chunker.types import CodeChunk
from chunker.export.postgres_exporter import PostgresExporter


def create_sample_chunks():
    """Create sample chunks for demonstration."""
    return [
        CodeChunk(
            file_path="src/models/user.py",
            start_line=1,
            end_line=50,
            byte_start=0,
            byte_end=1500,
            content="""
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
    
    def validate_email(self):
        return '@' in self.email
""",
            node_type="class",
            language="python",
            parent_context="module",
            metadata={
                "name": "User",
                "chunk_type": "class",
                "cyclomatic_complexity": 3,
                "token_count": 45,
                "has_docstring": False,
                "methods": ["__init__", "validate_email"]
            }
        ),
        CodeChunk(
            file_path="src/services/auth.py",
            start_line=10,
            end_line=30,
            byte_start=200,
            byte_end=800,
            content="""
def authenticate(username, password):
    user = User.find_by_username(username)
    if user and user.check_password(password):
        return generate_token(user)
    return None
""",
            node_type="function",
            language="python",
            parent_context="module",
            metadata={
                "name": "authenticate",
                "chunk_type": "function",
                "cyclomatic_complexity": 5,
                "token_count": 55,
                "has_docstring": True,
                "parameters": ["username", "password"],
                "calls": ["User.find_by_username", "generate_token"],
                "returns": "str|None"
            }
        ),
        CodeChunk(
            file_path="src/utils/validators.py",
            start_line=1,
            end_line=15,
            byte_start=0,
            byte_end=400,
            content="""
def validate_password(password):
    '''Validate password strength'''
    if len(password) < 8:
        return False
    return True
""",
            node_type="function",
            language="python",
            parent_context="module",
            metadata={
                "name": "validate_password",
                "chunk_type": "function",
                "cyclomatic_complexity": 2,
                "token_count": 25,
                "has_docstring": True,
                "security_related": True
            }
        )
    ]


def main():
    """Demonstrate PostgreSQL exporter features."""
    print("=== PostgreSQL Exporter Demo ===\n")
    
    # Create exporter and add chunks
    exporter = PostgresExporter()
    chunks = create_sample_chunks()
    exporter.add_chunks(chunks)
    
    # Add relationships
    exporter.add_relationship(
        chunks[1], chunks[0],  # authenticate -> User
        "IMPORTS",
        {"module": "models.user", "import_type": "class"}
    )
    
    exporter.add_relationship(
        chunks[1], chunks[2],  # authenticate -> validate_password
        "CALLS",
        {"line": 15, "context": "password_validation"}
    )
    
    # Create output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Export as SQL
        print("1. Exporting as SQL file...")
        sql_file = output_dir / "export.sql"
        exporter.export(sql_file, format="sql")
        
        # Show schema features
        print("\n2. Advanced PostgreSQL features in schema:")
        schema = exporter.get_schema_ddl()
        
        if "JSONB" in schema:
            print("   ✓ JSONB columns for flexible metadata storage")
        if "PARTITION BY" in schema:
            print("   ✓ Table partitioning for scalability")
        if "MATERIALIZED VIEW" in schema:
            print("   ✓ Materialized views for analytics")
        if "CREATE OR REPLACE FUNCTION" in schema:
            print("   ✓ Custom functions for graph traversal")
        if "gin_trgm_ops" in schema:
            print("   ✓ Trigram indexes for fuzzy search")
        if "GENERATED ALWAYS AS" in schema:
            print("   ✓ Generated columns for computed values")
        
        # Export as COPY format
        print("\n3. Exporting as COPY format...")
        copy_base = output_dir / "export"
        exporter.export(copy_base, format="copy")
        
        print("   Generated files:")
        for file in sorted(output_dir.glob("export*")):
            print(f"   - {file.name}")
        
        # Show sample queries
        print("\n4. Advanced query examples:")
        queries = exporter.get_advanced_queries()
        
        for query_name in ["similarity_search", "full_text_search", "jsonb_metadata_query"]:
            if query_name in queries:
                print(f"\n   {query_name}:")
                # Show first few lines of query
                lines = queries[query_name].strip().split('\n')[:3]
                for line in lines:
                    if line.strip():
                        print(f"   {line}")
        
        print("\n5. Sample SQL content:")
        content = sql_file.read_text()
        # Show some key parts
        if "INSERT INTO chunks" in content:
            print("   ✓ Chunk data insertion with JSONB metadata")
        if "ON CONFLICT" in content:
            print("   ✓ Upsert support with ON CONFLICT")
        if "REFRESH MATERIALIZED VIEW" in content:
            print("   ✓ Materialized view refresh commands")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
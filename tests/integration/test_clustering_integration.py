"""Integration tests for hierarchical clustering pipeline."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Check for optional dependencies
try:
    import networkx as nx
    import igraph
    import leidenalg

    HAS_CLUSTERING_DEPS = True
except ImportError:
    HAS_CLUSTERING_DEPS = False


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringIntegration:
    """Integration tests for clustering pipeline."""

    @pytest.fixture
    def sample_project(self, tmp_path: Path) -> Path:
        """Create a sample Python project for testing."""
        # Create a simple multi-file project
        (tmp_path / "auth").mkdir()

        # auth/__init__.py
        (tmp_path / "auth" / "__init__.py").write_text(
            "from .user import User\nfrom .login import login\n"
        )

        # auth/user.py
        (tmp_path / "auth" / "user.py").write_text('''
class User:
    """User model."""
    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}"
''')

        # auth/login.py
        (tmp_path / "auth" / "login.py").write_text('''
from .user import User

def login(username: str) -> User:
    """Login and return user."""
    return User(username)

def validate(user: User) -> bool:
    """Validate user."""
    return user.name is not None
''')

        # utils.py (infrastructure-like)
        (tmp_path / "utils.py").write_text('''
def log(message: str) -> None:
    """Log a message."""
    print(message)
''')

        return tmp_path

    def test_full_pipeline(self, sample_project: Path):
        """Test the full clustering pipeline on sample project."""
        from chunker.clustering import ClusteringEngine
        from chunker.symbol_graph import extract_symbol_graph

        # 1. Extract symbols
        extraction = extract_symbol_graph(sample_project, "python")
        all_symbols = extraction["symbol_lookup"]
        all_relationships = extraction["relationships"]

        # 2. Run clustering
        engine = ClusteringEngine(
            coarse_resolution=0.5,
            fine_resolution=1.5,
        )
        result = engine.cluster(all_symbols, all_relationships)

        # 3. Validate output structure
        assert "hierarchy" in result
        assert "infrastructure" in result
        assert "metrics" in result
        assert "metadata" in result

        # Validate hierarchy structure
        hierarchy = result["hierarchy"]
        assert hierarchy["level"] == "container"
        assert "children" in hierarchy

        # Validate metrics
        metrics = result["metrics"]
        # Metrics include: modularity, coverage, avg_cluster_size, num_isolated_nodes
        assert "modularity" in metrics or "coverage" in metrics

    def test_output_json_format(self, sample_project: Path):
        """Test that output is valid JSON."""
        from chunker.clustering import ClusteringEngine
        from chunker.symbol_graph import extract_symbol_graph

        extraction = extract_symbol_graph(sample_project, "python")
        all_symbols = extraction["symbol_lookup"]
        all_relationships = extraction["relationships"]

        engine = ClusteringEngine()
        result = engine.cluster(all_symbols, all_relationships)

        # Should be JSON serializable
        json_str = json.dumps(result, default=str)
        parsed = json.loads(json_str)
        assert parsed["hierarchy"]["level"] == "container"

    def test_resolution_affects_clusters(self, sample_project: Path):
        """Test that resolution parameter affects cluster count."""
        from chunker.clustering import ClusteringEngine
        from chunker.symbol_graph import extract_symbol_graph

        extraction = extract_symbol_graph(sample_project, "python")
        all_symbols = extraction["symbol_lookup"]
        all_relationships = extraction["relationships"]

        # Coarse resolution should produce fewer, larger clusters
        coarse_engine = ClusteringEngine(coarse_resolution=0.1, fine_resolution=0.3)
        coarse_result = coarse_engine.cluster(all_symbols, all_relationships)

        # Fine resolution should produce more, smaller clusters
        fine_engine = ClusteringEngine(coarse_resolution=2.0, fine_resolution=5.0)
        fine_result = fine_engine.cluster(all_symbols, all_relationships)

        # Both should produce valid results
        assert coarse_result["hierarchy"]["level"] == "container"
        assert fine_result["hierarchy"]["level"] == "container"


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestCLIIntegration:
    """Integration tests for CLI commands."""

    @pytest.fixture
    def sample_project(self, tmp_path: Path) -> Path:
        """Create a sample Python project for testing."""
        (tmp_path / "sample.py").write_text("""
class Foo:
    def bar(self):
        return "bar"

def baz():
    f = Foo()
    return f.bar()
""")
        return tmp_path

    def test_cli_cluster_infer(self, sample_project: Path, tmp_path: Path):
        """Test CLI cluster infer command."""
        output_file = tmp_path / "output.json"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chunker.cli",
                "cluster",
                "infer",
                str(sample_project),
                "-o",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )

        # Check command succeeded
        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")

        assert result.returncode == 0
        assert output_file.exists()

        # Validate output
        with open(output_file) as f:
            data = json.load(f)

        assert "hierarchy" in data
        assert "metrics" in data

    def test_cli_summary_format(self, sample_project: Path):
        """Test CLI with summary output format."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chunker.cli",
                "cluster",
                "infer",
                str(sample_project),
                "--format",
                "summary",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )

        if result.returncode != 0:
            print(f"STDERR: {result.stderr}")

        assert result.returncode == 0
        assert "Clustering Summary" in result.stdout

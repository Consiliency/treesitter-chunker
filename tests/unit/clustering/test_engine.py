"""Unit tests for chunker.clustering.engine module."""

import pytest

# Check for optional dependencies
try:
    import networkx as nx
    import igraph
    import leidenalg

    HAS_CLUSTERING_DEPS = all((nx, igraph, leidenalg))
except ImportError:
    HAS_CLUSTERING_DEPS = False

from chunker.clustering.weights import EdgeWeightConfig


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngine:
    """Tests for ClusteringEngine class."""

    def test_init_default(self):
        """Test initialization with defaults."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()
        assert engine.coarse_resolution == 0.5
        assert engine.fine_resolution == 1.5
        assert engine.detect_infrastructure is True
        assert engine.weight_config is not None

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        from chunker.clustering.engine import ClusteringEngine

        config = EdgeWeightConfig(import_weight=2.0)
        engine = ClusteringEngine(
            weight_config=config,
            coarse_resolution=0.3,
            fine_resolution=0.8,
            detect_infrastructure=False,
        )
        assert engine.coarse_resolution == 0.3
        assert engine.fine_resolution == 0.8
        assert engine.detect_infrastructure is False
        assert engine.weight_config.import_weight == 2.0

    def test_empty_symbols(self):
        """Test clustering with no symbols."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()
        result = engine.cluster({}, [])

        assert "hierarchy" in result
        assert "infrastructure" in result
        assert "metrics" in result
        assert "metadata" in result

    def test_single_symbol(self):
        """Test clustering with a single symbol."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"}
        }
        result = engine.cluster(symbols, [])

        assert result["metadata"]["num_symbols"] == 1

    def test_connected_symbols(self):
        """Test clustering with connected symbols."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:C": {
                "name": "C",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "inherits"},
            {"from": "mod:C", "to": "mod:A", "type": "calls"},
        ]

        result = engine.cluster(symbols, relationships)

        assert result["metadata"]["num_symbols"] == 3
        assert "hierarchy" in result
        assert result["hierarchy"]["level"] == "container"

    def test_build_graph(self):
        """Test graph building from symbols."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "imports"},
        ]

        graph = engine._build_graph(symbols, relationships)

        assert "mod:A" in graph.nodes()
        assert "mod:B" in graph.nodes()
        assert graph.has_edge("mod:A", "mod:B")

    def test_infrastructure_detection(self):
        """Test that infrastructure detection can be toggled."""
        from chunker.clustering.engine import ClusteringEngine

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:util": {
                "name": "util",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }
        relationships = []

        # With detection
        engine = ClusteringEngine(detect_infrastructure=True)
        result = engine.cluster(symbols, relationships)
        assert "infrastructure" in result

        # Without detection
        engine = ClusteringEngine(detect_infrastructure=False)
        result = engine.cluster(symbols, relationships)
        assert result["infrastructure"] == []

    def test_metadata_includes_parameters(self):
        """Test that metadata includes clustering parameters."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine(
            coarse_resolution=0.4,
            fine_resolution=1.2,
        )

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"}
        }
        result = engine.cluster(symbols, [])

        assert result["metadata"]["coarse_resolution"] == 0.4
        assert result["metadata"]["fine_resolution"] == 1.2
        assert (
            "algorithm" not in result["metadata"]
            or result["metadata"].get("algorithm") == "leiden"
        )


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineEdgeCases:
    """Tests for edge cases in ClusteringEngine."""

    def test_self_referential_relationship(self):
        """Test that self-referential relationships are ignored."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:A", "type": "calls"},  # Self-reference
        ]

        graph = engine._build_graph(symbols, relationships)

        # Self-loop should not exist
        assert not graph.has_edge("mod:A", "mod:A")

    def test_relationship_with_missing_from_symbol(self):
        """Test that relationships with missing 'from' symbol are skipped."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:MISSING", "to": "mod:A", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        # Only the valid symbol should be a node
        assert "mod:A" in graph.nodes()
        assert "mod:MISSING" not in graph.nodes()
        assert graph.number_of_edges() == 0

    def test_relationship_with_missing_to_symbol(self):
        """Test that relationships with missing 'to' symbol are skipped."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:MISSING", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        assert "mod:A" in graph.nodes()
        assert graph.number_of_edges() == 0

    def test_relationship_with_empty_from(self):
        """Test that relationships with empty 'from' field are skipped."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "", "to": "mod:A", "type": "calls"},
            {"from": None, "to": "mod:A", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        assert graph.number_of_edges() == 0

    def test_relationship_with_empty_to(self):
        """Test that relationships with empty 'to' field are skipped."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "", "type": "calls"},
            {"from": "mod:A", "to": None, "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        assert graph.number_of_edges() == 0

    def test_multiple_relationships_same_pair(self):
        """Test that multiple relationships between same symbols accumulate weights."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "imports"},
            {"from": "mod:A", "to": "mod:B", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        # Should have one edge with accumulated weight
        assert graph.has_edge("mod:A", "mod:B")
        # Weight should be greater than just one relationship
        edge_data = graph.get_edge_data("mod:A", "mod:B")
        assert edge_data["weight"] > 0

    def test_unknown_relationship_type(self):
        """Test that unknown relationship types result in zero weight edges not being added."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "unknown_type"},
        ]

        graph = engine._build_graph(symbols, relationships)

        # Zero weight edges should not be added
        assert not graph.has_edge("mod:A", "mod:B")

    def test_disconnected_components(self):
        """Test clustering with disconnected components."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:C": {"name": "C", "kind": "class", "module": "mod", "file": "b.py"},
            "mod:D": {"name": "D", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "imports"},
            {"from": "mod:C", "to": "mod:D", "type": "imports"},
        ]

        result = engine.cluster(symbols, relationships)

        assert result["metadata"]["num_symbols"] == 4
        assert result["metadata"]["num_relationships"] == 2

    def test_two_symbols_same_file(self):
        """Test that same-file bonus is applied correctly."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "same.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "same.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        # Should have edge with same-file bonus applied
        assert graph.has_edge("mod:A", "mod:B")
        edge_data = graph.get_edge_data("mod:A", "mod:B")
        # call_weight (0.7) + same_file_bonus (0.3) = 1.0
        assert edge_data["weight"] == pytest.approx(1.0)

    def test_two_symbols_different_files(self):
        """Test weight without same-file bonus."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        # Should have edge without same-file bonus
        assert graph.has_edge("mod:A", "mod:B")
        edge_data = graph.get_edge_data("mod:A", "mod:B")
        # call_weight (0.7) without bonus
        assert edge_data["weight"] == pytest.approx(0.7)


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineLeiden:
    """Tests for Leiden algorithm execution in ClusteringEngine."""

    def test_run_leiden_empty_graph(self):
        """Test Leiden with empty graph returns empty clusters."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()
        engine._graph = None

        result = engine._run_leiden(0.5)

        assert result == {}

    def test_run_leiden_single_node(self):
        """Test Leiden with single node returns single cluster."""
        from chunker.clustering.engine import ClusteringEngine
        import networkx as nx

        engine = ClusteringEngine()
        engine._graph = nx.Graph()
        engine._graph.add_node("single")

        result = engine._run_leiden(0.5)

        assert len(result) == 1
        assert "single" in result["0"]

    def test_run_leiden_no_edges(self):
        """Test Leiden with nodes but no edges returns individual clusters."""
        from chunker.clustering.engine import ClusteringEngine
        import networkx as nx

        engine = ClusteringEngine()
        engine._graph = nx.Graph()
        engine._graph.add_nodes_from(["A", "B", "C"])

        result = engine._run_leiden(0.5)

        # Each node should be in its own cluster
        assert len(result) == 3
        all_members = []
        for members in result.values():
            all_members.extend(members)
        assert set(all_members) == {"A", "B", "C"}

    def test_run_leiden_connected_graph(self):
        """Test Leiden with connected graph produces clusters."""
        from chunker.clustering.engine import ClusteringEngine
        import networkx as nx

        engine = ClusteringEngine()
        engine._graph = nx.Graph()
        engine._graph.add_edge("A", "B", weight=1.0)
        engine._graph.add_edge("B", "C", weight=1.0)
        engine._graph.add_edge("A", "C", weight=1.0)

        result = engine._run_leiden(0.5)

        # Should return some clusters
        assert len(result) >= 1
        all_members = []
        for members in result.values():
            all_members.extend(members)
        assert set(all_members) == {"A", "B", "C"}


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineInfrastructure:
    """Tests for infrastructure detection in ClusteringEngine."""

    def test_detect_infrastructure_empty_graph(self):
        """Test infrastructure detection with no graph."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()
        engine._graph = None

        result = engine._detect_infrastructure()

        assert result == []

    def test_detect_infrastructure_disabled(self):
        """Test that infrastructure detection returns empty when disabled."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine(detect_infrastructure=False)

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:C": {"name": "C", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "calls"},
            {"from": "mod:C", "to": "mod:B", "type": "calls"},
        ]

        result = engine.cluster(symbols, relationships)

        assert result["infrastructure"] == []

    def test_detect_infrastructure_star_topology(self):
        """Test infrastructure detection with hub node."""
        from chunker.clustering.engine import ClusteringEngine
        import networkx as nx

        engine = ClusteringEngine(infrastructure_threshold=0.5)

        # Create a star graph where 'hub' is the center
        engine._graph = nx.Graph()
        for i in range(5):
            engine._graph.add_edge("hub", f"spoke_{i}", weight=1.0)

        result = engine._detect_infrastructure()

        # The hub node should have high betweenness and be identified
        assert "hub" in result


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineMetrics:
    """Tests for overall metrics calculation in ClusteringEngine."""

    def test_metrics_empty_graph(self):
        """Test metrics calculation with empty graph."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        result = engine.cluster({}, [])

        assert result["metrics"]["modularity"] == 0.0
        assert result["metrics"]["coverage"] == 0.0
        assert result["metrics"]["avg_cluster_size"] == 0.0
        assert result["metrics"]["num_isolated_nodes"] == 0

    def test_metrics_single_cluster(self):
        """Test metrics with all nodes in one cluster."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine(
            coarse_resolution=0.1
        )  # Low resolution = fewer clusters

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "inherits"},
        ]

        result = engine.cluster(symbols, relationships)

        # Coverage should be 1.0 if all nodes are clustered
        assert result["metrics"]["coverage"] == pytest.approx(1.0)

    def test_metadata_timestamp(self):
        """Test that metadata includes a timestamp."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"}
        }
        result = engine.cluster(symbols, [])

        assert "timestamp" in result["metadata"]
        # Timestamp should be ISO format
        from datetime import datetime

        try:
            datetime.fromisoformat(result["metadata"]["timestamp"])
        except ValueError:
            pytest.fail("Timestamp is not in valid ISO format")


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineHierarchy:
    """Tests for hierarchy building in ClusteringEngine."""

    def test_hierarchy_structure(self):
        """Test that hierarchy has correct structure."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "inherits"},
        ]

        result = engine.cluster(symbols, relationships)

        hierarchy = result["hierarchy"]
        assert hierarchy["id"] == "root"
        assert hierarchy["level"] == "container"
        assert "children" in hierarchy
        assert "members" in hierarchy

    def test_hierarchy_root_contains_all_symbols(self):
        """Test that root node's members contain all symbols."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:C": {"name": "C", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = []

        result = engine.cluster(symbols, relationships)

        hierarchy = result["hierarchy"]
        assert set(hierarchy["members"]) == {"mod:A", "mod:B", "mod:C"}

    def test_hierarchy_serialization(self):
        """Test that hierarchy can be serialized and deserialized."""
        from chunker.clustering.engine import ClusteringEngine
        from chunker.clustering.hierarchy import ClusterNode
        import json

        engine = ClusteringEngine()

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }

        result = engine.cluster(symbols, [])

        # Should be JSON serializable
        json_str = json.dumps(result["hierarchy"])
        loaded = json.loads(json_str)

        # Should be deserializable back to ClusterNode
        node = ClusterNode.from_dict(loaded)
        assert node.id == "root"


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineCustomWeights:
    """Tests for ClusteringEngine with custom weight configurations."""

    def test_custom_import_weight(self):
        """Test that custom import weight is applied."""
        from chunker.clustering.engine import ClusteringEngine

        config = EdgeWeightConfig(import_weight=5.0)
        engine = ClusteringEngine(weight_config=config)

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "imports"},
        ]

        graph = engine._build_graph(symbols, relationships)

        edge_data = graph.get_edge_data("mod:A", "mod:B")
        assert edge_data["weight"] == pytest.approx(5.0)

    def test_custom_call_weight(self):
        """Test that custom call weight is applied."""
        from chunker.clustering.engine import ClusteringEngine

        config = EdgeWeightConfig(call_weight=3.0)
        engine = ClusteringEngine(weight_config=config)

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        edge_data = graph.get_edge_data("mod:A", "mod:B")
        assert edge_data["weight"] == pytest.approx(3.0)

    def test_custom_inherit_weight(self):
        """Test that custom inherit weight is applied."""
        from chunker.clustering.engine import ClusteringEngine

        config = EdgeWeightConfig(inherit_weight=4.0)
        engine = ClusteringEngine(weight_config=config)

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "inherits"},
        ]

        graph = engine._build_graph(symbols, relationships)

        edge_data = graph.get_edge_data("mod:A", "mod:B")
        assert edge_data["weight"] == pytest.approx(4.0)

    def test_custom_type_ref_weight(self):
        """Test that custom type_ref weight is applied."""
        from chunker.clustering.engine import ClusteringEngine

        config = EdgeWeightConfig(type_ref_weight=2.0)
        engine = ClusteringEngine(weight_config=config)

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "a.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "b.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "type_ref"},
        ]

        graph = engine._build_graph(symbols, relationships)

        edge_data = graph.get_edge_data("mod:A", "mod:B")
        assert edge_data["weight"] == pytest.approx(2.0)

    def test_custom_same_file_bonus(self):
        """Test that custom same_file_bonus is applied."""
        from chunker.clustering.engine import ClusteringEngine

        config = EdgeWeightConfig(call_weight=1.0, same_file_bonus=1.0)
        engine = ClusteringEngine(weight_config=config)

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "same.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "same.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:B", "type": "calls"},
        ]

        graph = engine._build_graph(symbols, relationships)

        edge_data = graph.get_edge_data("mod:A", "mod:B")
        # call_weight (1.0) + same_file_bonus (1.0) = 2.0
        assert edge_data["weight"] == pytest.approx(2.0)


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineResolution:
    """Tests for different resolution parameters in ClusteringEngine."""

    def test_low_resolution_fewer_clusters(self):
        """Test that lower resolution produces fewer/larger clusters."""
        from chunker.clustering.engine import ClusteringEngine

        # Create a graph with clear community structure
        symbols = {
            f"mod:node_{i}": {
                "name": f"node_{i}",
                "kind": "class",
                "module": "mod",
                "file": "mod.py",
            }
            for i in range(10)
        }
        relationships = []

        # Create two cliques
        for i in range(5):
            for j in range(i + 1, 5):
                relationships.append(
                    {"from": f"mod:node_{i}", "to": f"mod:node_{j}", "type": "calls"}
                )
        for i in range(5, 10):
            for j in range(i + 1, 10):
                relationships.append(
                    {"from": f"mod:node_{i}", "to": f"mod:node_{j}", "type": "calls"}
                )

        # Connect the two cliques weakly
        relationships.append(
            {"from": "mod:node_0", "to": "mod:node_5", "type": "imports"}
        )

        low_res_engine = ClusteringEngine(coarse_resolution=0.1, fine_resolution=0.5)
        high_res_engine = ClusteringEngine(coarse_resolution=1.0, fine_resolution=3.0)

        low_res_result = low_res_engine.cluster(symbols, relationships)
        high_res_result = high_res_engine.cluster(symbols, relationships)

        # Lower resolution should produce fewer or equal number of coarse clusters
        assert (
            low_res_result["metadata"]["num_coarse_clusters"]
            <= high_res_result["metadata"]["num_coarse_clusters"]
        )

    def test_infrastructure_threshold_parameter(self):
        """Test that infrastructure_threshold affects detection."""
        from chunker.clustering.engine import ClusteringEngine

        symbols = {
            "mod:hub": {
                "name": "hub",
                "kind": "class",
                "module": "mod",
                "file": "mod.py",
            },
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {"name": "B", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:C": {"name": "C", "kind": "class", "module": "mod", "file": "mod.py"},
        }
        relationships = [
            {"from": "mod:A", "to": "mod:hub", "type": "calls"},
            {"from": "mod:B", "to": "mod:hub", "type": "calls"},
            {"from": "mod:C", "to": "mod:hub", "type": "calls"},
        ]

        # Low threshold - more likely to detect infrastructure
        low_threshold_engine = ClusteringEngine(infrastructure_threshold=0.5)
        low_result = low_threshold_engine.cluster(symbols, relationships)

        # High threshold - less likely to detect infrastructure
        high_threshold_engine = ClusteringEngine(infrastructure_threshold=0.99)
        high_result = high_threshold_engine.cluster(symbols, relationships)

        # Both should successfully complete
        assert "infrastructure" in low_result
        assert "infrastructure" in high_result


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestClusteringEngineLargeGraph:
    """Tests for ClusteringEngine with larger graphs."""

    def test_moderate_size_graph(self):
        """Test clustering with a moderately sized graph."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        # Create 50 symbols
        symbols = {
            f"mod:node_{i}": {
                "name": f"node_{i}",
                "kind": "class",
                "module": "mod",
                "file": f"file_{i % 5}.py",
            }
            for i in range(50)
        }

        # Create relationships (each node connected to next 3 nodes)
        relationships = []
        for i in range(50):
            for j in range(1, 4):
                target = (i + j) % 50
                relationships.append(
                    {
                        "from": f"mod:node_{i}",
                        "to": f"mod:node_{target}",
                        "type": ["imports", "calls", "inherits"][j - 1],
                    }
                )

        result = engine.cluster(symbols, relationships)

        assert result["metadata"]["num_symbols"] == 50
        assert result["metadata"]["num_relationships"] == 150
        assert len(result["hierarchy"]["members"]) == 50

    def test_graph_with_many_relationships(self):
        """Test clustering with many relationships between few symbols."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            f"mod:node_{i}": {
                "name": f"node_{i}",
                "kind": "class",
                "module": "mod",
                "file": "mod.py",
            }
            for i in range(5)
        }

        # Create a complete graph (all pairs connected)
        relationships = []
        for i in range(5):
            for j in range(i + 1, 5):
                relationships.append(
                    {"from": f"mod:node_{i}", "to": f"mod:node_{j}", "type": "calls"}
                )
                relationships.append(
                    {"from": f"mod:node_{i}", "to": f"mod:node_{j}", "type": "imports"}
                )

        result = engine.cluster(symbols, relationships)

        assert result["metadata"]["num_symbols"] == 5
        # 10 pairs * 2 types = 20 relationships
        assert result["metadata"]["num_relationships"] == 20


@pytest.mark.skipif(
    not HAS_CLUSTERING_DEPS, reason="clustering dependencies not installed"
)
class TestModuleDependencies:
    """Tests for module dependency computation (fixes #60)."""

    def test_module_dependencies_without_is_internal_flag(self):
        """Test that module_dependencies works without is_internal flag set.

        This is a regression test for issue #60 where relationships without
        the is_internal flag would always result in empty module_dependencies.
        """
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        # Two modules with symbols
        symbols = {
            "module_a:ClassA": {
                "name": "ClassA",
                "kind": "class",
                "module": "module_a",
                "file": "module_a.py",
            },
            "module_a:func_a": {
                "name": "func_a",
                "kind": "function",
                "module": "module_a",
                "file": "module_a.py",
            },
            "module_b:ClassB": {
                "name": "ClassB",
                "kind": "class",
                "module": "module_b",
                "file": "module_b.py",
            },
            "module_b:func_b": {
                "name": "func_b",
                "kind": "function",
                "module": "module_b",
                "file": "module_b.py",
            },
        }

        # Cross-module relationships WITHOUT is_internal flag
        relationships = [
            {"from": "module_a:ClassA", "to": "module_b:ClassB", "type": "imports"},
            {"from": "module_a:func_a", "to": "module_b:func_b", "type": "calls"},
            {"from": "module_b:ClassB", "to": "module_a:ClassA", "type": "inherits"},
        ]

        result = engine.cluster(symbols, relationships)

        # module_dependencies should NOT be empty
        assert len(result["module_dependencies"]) > 0, (
            "module_dependencies should not be empty when relationships exist "
            "between symbols in the symbol lookup"
        )

        # Verify the structure
        for dep in result["module_dependencies"]:
            assert "from_module" in dep
            assert "to_module" in dep
            assert "count" in dep
            assert dep["count"] > 0

    def test_module_dependencies_filters_external_relationships(self):
        """Test that relationships to symbols not in lookup are excluded."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "module_a:ClassA": {
                "name": "ClassA",
                "kind": "class",
                "module": "module_a",
                "file": "module_a.py",
            },
        }

        # Relationship where 'to' symbol doesn't exist in symbols
        relationships = [
            {"from": "module_a:ClassA", "to": "external:SomeClass", "type": "imports"},
        ]

        result = engine.cluster(symbols, relationships)

        # Should be empty since external:SomeClass is not in symbols
        assert len(result["module_dependencies"]) == 0

    def test_module_dependencies_with_is_internal_flag_still_works(self):
        """Test backward compatibility - is_internal flag is ignored now."""
        from chunker.clustering.engine import ClusteringEngine

        engine = ClusteringEngine()

        symbols = {
            "module_a:ClassA": {
                "name": "ClassA",
                "kind": "class",
                "module": "module_a",
                "file": "module_a.py",
            },
            "module_b:ClassB": {
                "name": "ClassB",
                "kind": "class",
                "module": "module_b",
                "file": "module_b.py",
            },
        }

        # Relationship WITH is_internal=False but both symbols exist
        # The fix should include this relationship since both endpoints exist
        relationships = [
            {
                "from": "module_a:ClassA",
                "to": "module_b:ClassB",
                "type": "imports",
                "is_internal": False,
            },
        ]

        result = engine.cluster(symbols, relationships)

        # Should still include the relationship since both symbols exist
        assert len(result["module_dependencies"]) == 1

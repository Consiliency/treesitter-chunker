"""Unit tests for chunker.clustering.metrics module."""

import pytest

# We need to mock networkx if not installed
try:
    import networkx as nx

    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from chunker.clustering.metrics import ClusterMetrics, MetricsCalculator


class TestClusterMetrics:
    """Tests for ClusterMetrics dataclass."""

    def test_quality_score_high_cohesion(self):
        """Test quality score with high cohesion."""
        metrics = ClusterMetrics(
            cluster_id="test",
            size=5,
            internal_edges=10,
            external_edges=2,
            density=0.8,
            cohesion=0.9,
            coupling=0.1,
            modularity_contribution=0.15,
        )
        # quality = 0.9 / (0.9 + 0.1 + 0.001) ≈ 0.899
        assert metrics.quality_score > 0.89
        assert metrics.quality_score < 0.91

    def test_quality_score_high_coupling(self):
        """Test quality score with high coupling."""
        metrics = ClusterMetrics(
            cluster_id="test",
            size=5,
            internal_edges=2,
            external_edges=10,
            density=0.2,
            cohesion=0.1,
            coupling=0.9,
            modularity_contribution=0.05,
        )
        assert metrics.quality_score < 0.11

    def test_quality_score_zero_cohesion(self):
        """Test quality score with zero cohesion."""
        metrics = ClusterMetrics(
            cluster_id="test",
            size=5,
            internal_edges=0,
            external_edges=5,
            density=0.0,
            cohesion=0.0,
            coupling=0.5,
            modularity_contribution=0.0,
        )
        assert metrics.quality_score == 0.0

    def test_quality_score_zero_coupling(self):
        """Test quality score with zero coupling (fully cohesive)."""
        metrics = ClusterMetrics(
            cluster_id="test",
            size=5,
            internal_edges=10,
            external_edges=0,
            density=1.0,
            cohesion=1.0,
            coupling=0.0,
            modularity_contribution=0.2,
        )
        # quality = 1.0 / (1.0 + 0.0 + 0.001) ≈ 0.999
        assert metrics.quality_score > 0.99

    def test_quality_score_balanced(self):
        """Test quality score with balanced cohesion and coupling."""
        metrics = ClusterMetrics(
            cluster_id="test",
            size=5,
            internal_edges=5,
            external_edges=5,
            density=0.5,
            cohesion=0.5,
            coupling=0.5,
            modularity_contribution=0.1,
        )
        # quality = 0.5 / (0.5 + 0.5 + 0.001) ≈ 0.4995
        assert 0.49 < metrics.quality_score < 0.51

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = ClusterMetrics(
            cluster_id="test_cluster",
            size=10,
            internal_edges=15,
            external_edges=5,
            density=0.75,
            cohesion=0.8,
            coupling=0.2,
            modularity_contribution=0.1,
        )
        d = metrics.to_dict()
        assert d["cluster_id"] == "test_cluster"
        assert d["size"] == 10
        assert d["internal_edges"] == 15
        assert d["external_edges"] == 5
        assert d["density"] == 0.75
        assert d["cohesion"] == 0.8
        assert d["coupling"] == 0.2
        assert d["modularity_contribution"] == 0.1
        assert "quality_score" in d
        assert isinstance(d["quality_score"], float)

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        d = {
            "cluster_id": "test",
            "size": 5,
            "internal_edges": 10,
            "external_edges": 2,
            "density": 0.8,
            "cohesion": 0.9,
            "coupling": 0.1,
            "modularity_contribution": 0.15,
        }
        metrics = ClusterMetrics.from_dict(d)
        assert metrics.cluster_id == "test"
        assert metrics.size == 5
        assert metrics.internal_edges == 10
        assert metrics.external_edges == 2
        assert metrics.density == 0.8
        assert metrics.cohesion == 0.9
        assert metrics.coupling == 0.1
        assert metrics.modularity_contribution == 0.15

    def test_from_dict_ignores_quality_score(self):
        """Test that from_dict ignores quality_score field."""
        d = {
            "cluster_id": "test",
            "size": 5,
            "internal_edges": 10,
            "external_edges": 2,
            "density": 0.8,
            "cohesion": 0.9,
            "coupling": 0.1,
            "modularity_contribution": 0.15,
            "quality_score": 0.0,  # This should be ignored
        }
        metrics = ClusterMetrics.from_dict(d)
        # Quality score should be computed, not taken from dict
        assert metrics.quality_score > 0.89

    def test_to_dict_from_dict_roundtrip(self):
        """Test roundtrip serialization/deserialization."""
        original = ClusterMetrics(
            cluster_id="roundtrip_test",
            size=7,
            internal_edges=12,
            external_edges=3,
            density=0.67,
            cohesion=0.75,
            coupling=0.25,
            modularity_contribution=0.12,
        )
        d = original.to_dict()
        restored = ClusterMetrics.from_dict(d)

        assert restored.cluster_id == original.cluster_id
        assert restored.size == original.size
        assert restored.internal_edges == original.internal_edges
        assert restored.external_edges == original.external_edges
        assert restored.density == original.density
        assert restored.cohesion == original.cohesion
        assert restored.coupling == original.coupling
        assert restored.modularity_contribution == original.modularity_contribution
        # Quality scores should be identical since they're computed
        assert abs(restored.quality_score - original.quality_score) < 0.0001


@pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
class TestMetricsCalculator:
    """Tests for MetricsCalculator class."""

    def test_empty_graph(self):
        """Test with empty graph."""
        graph = nx.Graph()
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("empty", [])
        assert metrics.size == 0
        assert metrics.density == 0.0
        assert metrics.cohesion == 0.0
        assert metrics.coupling == 0.0
        assert metrics.internal_edges == 0
        assert metrics.external_edges == 0
        assert metrics.modularity_contribution == 0.0

    def test_single_node_cluster(self):
        """Test cluster with single node."""
        graph = nx.Graph()
        graph.add_node("A")
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("single", ["A"])
        assert metrics.size == 1
        assert metrics.internal_edges == 0
        assert metrics.density == 0.0
        assert metrics.cohesion == 0.0

    def test_two_node_connected_cluster(self):
        """Test cluster with two connected nodes."""
        graph = nx.Graph()
        graph.add_edge("A", "B")
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("pair", ["A", "B"])
        assert metrics.size == 2
        assert metrics.internal_edges == 1
        assert metrics.external_edges == 0
        assert metrics.density == 1.0  # Fully connected for 2 nodes

    def test_two_node_disconnected_cluster(self):
        """Test cluster with two disconnected nodes."""
        graph = nx.Graph()
        graph.add_node("A")
        graph.add_node("B")
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("disconnected", ["A", "B"])
        assert metrics.size == 2
        assert metrics.internal_edges == 0
        assert metrics.density == 0.0

    def test_connected_cluster(self):
        """Test fully connected cluster."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("A", "C")])
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("connected", ["A", "B", "C"])
        assert metrics.size == 3
        assert metrics.internal_edges == 3
        assert metrics.density == 1.0  # Fully connected
        assert metrics.cohesion == 1.0  # All nodes fully connected internally

    def test_cluster_with_external_edges(self):
        """Test cluster that has edges to outside nodes."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])
        calc = MetricsCalculator(graph)
        # Cluster is just A and B
        metrics = calc.calculate_cluster_metrics("partial", ["A", "B"])
        assert metrics.size == 2
        assert metrics.internal_edges == 1
        assert metrics.external_edges == 1  # B->C

    def test_cluster_with_multiple_external_edges(self):
        """Test cluster with multiple external connections."""
        graph = nx.Graph()
        # Create a cluster of A, B with external connections
        graph.add_edges_from(
            [
                ("A", "B"),  # Internal
                ("A", "X"),  # External
                ("A", "Y"),  # External
                ("B", "Z"),  # External
            ]
        )
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("multi_ext", ["A", "B"])
        assert metrics.size == 2
        assert metrics.internal_edges == 1
        assert metrics.external_edges == 3  # A->X, A->Y, B->Z

    def test_cluster_node_not_in_graph(self):
        """Test cluster with nodes not present in graph."""
        graph = nx.Graph()
        graph.add_edge("A", "B")
        calc = MetricsCalculator(graph)
        # "C" is not in graph
        metrics = calc.calculate_cluster_metrics("missing", ["A", "B", "C"])
        assert metrics.size == 3
        # Internal edges only count existing nodes
        assert metrics.internal_edges == 1

    def test_linear_cluster(self):
        """Test linear chain cluster (A-B-C-D)."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("linear", ["A", "B", "C", "D"])
        assert metrics.size == 4
        assert metrics.internal_edges == 3
        # Density = 3 / (4*3/2) = 3/6 = 0.5
        assert metrics.density == 0.5

    def test_identify_infrastructure_nodes(self):
        """Test infrastructure node detection."""
        # Create a star graph where center has high betweenness
        graph = nx.star_graph(5)
        # Relabel nodes to strings
        mapping = {i: f"node_{i}" for i in range(6)}
        graph = nx.relabel_nodes(graph, mapping)

        calc = MetricsCalculator(graph)
        infra = calc.identify_infrastructure_nodes(threshold_percentile=80)
        # node_0 is the center and should have high betweenness
        assert "node_0" in infra

    def test_identify_infrastructure_nodes_empty_graph(self):
        """Test infrastructure detection on empty graph."""
        graph = nx.Graph()
        calc = MetricsCalculator(graph)
        infra = calc.identify_infrastructure_nodes()
        assert infra == []

    def test_identify_infrastructure_nodes_single_node(self):
        """Test infrastructure detection on single node graph."""
        graph = nx.Graph()
        graph.add_node("A")
        calc = MetricsCalculator(graph)
        infra = calc.identify_infrastructure_nodes()
        assert infra == []  # Single node has zero betweenness

    def test_identify_infrastructure_nodes_line_graph(self):
        """Test infrastructure detection on line graph."""
        # In a line: A-B-C-D-E, middle nodes have higher betweenness
        graph = nx.path_graph(5)
        mapping = {i: f"node_{i}" for i in range(5)}
        graph = nx.relabel_nodes(graph, mapping)

        calc = MetricsCalculator(graph)
        infra = calc.identify_infrastructure_nodes(threshold_percentile=80)
        # Middle node (node_2) should have highest betweenness
        assert "node_2" in infra

    def test_identify_infrastructure_low_threshold(self):
        """Test infrastructure detection with low threshold."""
        graph = nx.star_graph(5)
        mapping = {i: f"node_{i}" for i in range(6)}
        graph = nx.relabel_nodes(graph, mapping)

        calc = MetricsCalculator(graph)
        # With low threshold, more nodes might be included
        infra = calc.identify_infrastructure_nodes(threshold_percentile=0)
        # Should still only include node_0 since others have zero betweenness
        assert "node_0" in infra

    def test_calculate_density_empty_members(self):
        """Test density calculation with empty members list."""
        graph = nx.Graph()
        graph.add_edge("A", "B")
        calc = MetricsCalculator(graph)
        density = calc.calculate_density([])
        assert density == 0.0

    def test_calculate_density_single_member(self):
        """Test density calculation with single member."""
        graph = nx.Graph()
        graph.add_node("A")
        calc = MetricsCalculator(graph)
        density = calc.calculate_density(["A"])
        assert density == 0.0

    def test_calculate_cohesion_empty_members(self):
        """Test cohesion calculation with empty members list."""
        graph = nx.Graph()
        graph.add_edge("A", "B")
        calc = MetricsCalculator(graph)
        cohesion = calc.calculate_cohesion([])
        assert cohesion == 0.0

    def test_calculate_cohesion_single_member(self):
        """Test cohesion calculation with single member."""
        graph = nx.Graph()
        graph.add_node("A")
        calc = MetricsCalculator(graph)
        cohesion = calc.calculate_cohesion(["A"])
        assert cohesion == 0.0

    def test_calculate_coupling_empty_members(self):
        """Test coupling calculation with empty members list."""
        graph = nx.Graph()
        graph.add_edge("A", "B")
        calc = MetricsCalculator(graph)
        coupling = calc.calculate_coupling([])
        assert coupling == 0.0

    def test_calculate_coupling_isolated_cluster(self):
        """Test coupling for isolated cluster (no external edges)."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("A", "C")])
        calc = MetricsCalculator(graph)
        coupling = calc.calculate_coupling(["A", "B", "C"])
        assert coupling == 0.0

    def test_calculate_coupling_high_external(self):
        """Test coupling with high external connectivity."""
        graph = nx.Graph()
        graph.add_edges_from(
            [
                ("A", "X"),
                ("A", "Y"),
                ("A", "Z"),
            ]
        )
        calc = MetricsCalculator(graph)
        # Cluster is just A, all edges are external
        coupling = calc.calculate_coupling(["A"])
        assert coupling == 1.0  # All edges are external

    def test_modularity_contribution_no_edges(self):
        """Test modularity contribution for graph with no edges."""
        graph = nx.Graph()
        graph.add_node("A")
        graph.add_node("B")
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("no_edges", ["A", "B"])
        assert metrics.modularity_contribution == 0.0

    def test_modularity_contribution_positive(self):
        """Test positive modularity contribution for well-separated cluster."""
        # Create two well-separated clusters
        graph = nx.Graph()
        # Cluster 1
        graph.add_edges_from([("A", "B"), ("B", "C"), ("A", "C")])
        # Cluster 2
        graph.add_edges_from([("X", "Y"), ("Y", "Z"), ("X", "Z")])
        # One connecting edge
        graph.add_edge("C", "X")

        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("cluster1", ["A", "B", "C"])
        # Should have positive modularity contribution
        assert metrics.modularity_contribution > 0

    def test_large_cluster(self):
        """Test metrics calculation on larger cluster."""
        graph = nx.complete_graph(10)
        mapping = {i: f"node_{i}" for i in range(10)}
        graph = nx.relabel_nodes(graph, mapping)

        calc = MetricsCalculator(graph)
        members = [f"node_{i}" for i in range(10)]
        metrics = calc.calculate_cluster_metrics("large", members)

        assert metrics.size == 10
        # Complete graph has n*(n-1)/2 edges = 10*9/2 = 45
        assert metrics.internal_edges == 45
        assert metrics.density == 1.0
        assert metrics.cohesion == 1.0
        assert metrics.external_edges == 0

    def test_partial_cluster_of_complete_graph(self):
        """Test metrics for partial cluster in a complete graph."""
        graph = nx.complete_graph(6)
        mapping = {i: f"node_{i}" for i in range(6)}
        graph = nx.relabel_nodes(graph, mapping)

        calc = MetricsCalculator(graph)
        # Only include half the nodes
        members = [f"node_{i}" for i in range(3)]
        metrics = calc.calculate_cluster_metrics("partial", members)

        assert metrics.size == 3
        assert metrics.internal_edges == 3  # 3 nodes fully connected
        # External edges: each of 3 nodes connects to 3 external nodes
        assert metrics.external_edges == 9


@pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
class TestMetricsCalculatorEdgeCases:
    """Additional edge case tests for MetricsCalculator."""

    def test_self_loop_handling(self):
        """Test that self-loops are handled correctly."""
        graph = nx.Graph()
        graph.add_edge("A", "A")  # Self-loop
        graph.add_edge("A", "B")
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("selfloop", ["A", "B"])
        # Self-loops shouldn't affect metrics incorrectly
        assert metrics.size == 2

    def test_weighted_graph(self):
        """Test metrics on weighted graph (weights should be ignored)."""
        graph = nx.Graph()
        graph.add_edge("A", "B", weight=5.0)
        graph.add_edge("B", "C", weight=10.0)
        graph.add_edge("A", "C", weight=1.0)
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("weighted", ["A", "B", "C"])
        # Weights shouldn't affect edge counts
        assert metrics.internal_edges == 3
        assert metrics.density == 1.0

    def test_directed_graph_converted(self):
        """Test metrics on undirected view of directed graph."""
        # Note: MetricsCalculator uses nx.Graph (undirected)
        digraph = nx.DiGraph()
        digraph.add_edge("A", "B")
        digraph.add_edge("B", "A")
        digraph.add_edge("B", "C")
        # Convert to undirected
        graph = digraph.to_undirected()
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("directed", ["A", "B", "C"])
        assert metrics.internal_edges == 2

    def test_multigraph_not_supported(self):
        """Test that MultiGraph is handled (parallel edges as single)."""
        # Note: nx.Graph doesn't support multi-edges, this tests what happens
        # if someone passes a converted multigraph
        mgraph = nx.MultiGraph()
        mgraph.add_edge("A", "B")
        mgraph.add_edge("A", "B")  # Parallel edge
        mgraph.add_edge("B", "C")
        # Convert to simple graph
        graph = nx.Graph(mgraph)
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("multi", ["A", "B", "C"])
        # Should treat parallel edges as single edge
        assert metrics.internal_edges == 2

    def test_unicode_node_names(self):
        """Test metrics with unicode node names."""
        graph = nx.Graph()
        graph.add_edges_from(
            [
                ("alpha_alpha", "beta_beta"),
                ("beta_beta", "gamma_gamma"),
            ]
        )
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics(
            "unicode", ["alpha_alpha", "beta_beta", "gamma_gamma"]
        )
        assert metrics.size == 3
        assert metrics.internal_edges == 2

    def test_numeric_node_names(self):
        """Test metrics with numeric node names converted to strings."""
        graph = nx.Graph()
        graph.add_edges_from([(1, 2), (2, 3)])
        calc = MetricsCalculator(graph)
        # Pass integer nodes
        metrics = calc.calculate_cluster_metrics("numeric", [1, 2, 3])
        assert metrics.size == 3
        assert metrics.internal_edges == 2

    def test_very_sparse_graph(self):
        """Test metrics on very sparse graph."""
        graph = nx.Graph()
        # 10 nodes but only 2 edges
        for i in range(10):
            graph.add_node(f"node_{i}")
        graph.add_edge("node_0", "node_1")
        graph.add_edge("node_5", "node_6")

        calc = MetricsCalculator(graph)
        members = [f"node_{i}" for i in range(10)]
        metrics = calc.calculate_cluster_metrics("sparse", members)

        assert metrics.size == 10
        assert metrics.internal_edges == 2
        # Density = 2 / 45 ≈ 0.044
        assert metrics.density < 0.05

    def test_disconnected_subgraphs(self):
        """Test cluster spanning disconnected components."""
        graph = nx.Graph()
        # Component 1
        graph.add_edge("A", "B")
        # Component 2
        graph.add_edge("X", "Y")

        calc = MetricsCalculator(graph)
        # Cluster includes nodes from both components
        metrics = calc.calculate_cluster_metrics("disconnected", ["A", "B", "X", "Y"])
        assert metrics.size == 4
        assert metrics.internal_edges == 2  # A-B and X-Y
        # Density should be low since not all connected
        assert metrics.density < 0.5

    def test_empty_cluster_in_nonempty_graph(self):
        """Test empty cluster in graph with nodes."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C")])
        calc = MetricsCalculator(graph)
        metrics = calc.calculate_cluster_metrics("empty_cluster", [])
        assert metrics.size == 0
        assert metrics.modularity_contribution == 0.0

    def test_infrastructure_nodes_all_same_betweenness(self):
        """Test infrastructure detection when all nodes have same betweenness."""
        # In a complete graph, all nodes have equal betweenness
        graph = nx.complete_graph(4)
        mapping = {i: f"node_{i}" for i in range(4)}
        graph = nx.relabel_nodes(graph, mapping)

        calc = MetricsCalculator(graph)
        # All nodes should have equal betweenness, so at threshold_percentile=95
        # we should get at least one node
        infra = calc.identify_infrastructure_nodes(threshold_percentile=95)
        # At high threshold, should get few or no nodes (betweenness > 0 filter)
        # In complete graph, betweenness is 0 for all nodes
        assert len(infra) == 0  # No node has betweenness > 0 in complete graph

"""Main clustering orchestration module.

This module provides the ClusteringEngine class which orchestrates the
hierarchical clustering of code symbols using the Leiden algorithm.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import igraph as ig
import leidenalg
import networkx as nx

from .hierarchy import ClusterNode, HierarchyBuilder
from .metrics import ClusterMetrics, MetricsCalculator
from .weights import EdgeWeightCalculator, EdgeWeightConfig


class ClusteringEngine:
    """Main engine for hierarchical clustering of code symbols.

    This class orchestrates the complete clustering pipeline:
    1. Building a weighted graph from symbols and relationships
    2. Running Leiden algorithm at multiple resolutions
    3. Detecting infrastructure/utility nodes
    4. Constructing the hierarchical cluster tree

    Attributes:
        weight_config: Configuration for edge weight calculation.
        coarse_resolution: Resolution parameter for coarse-grained clustering.
        fine_resolution: Resolution parameter for fine-grained clustering.
        detect_infrastructure: Whether to detect infrastructure nodes.
        infrastructure_threshold: Betweenness centrality percentile threshold.
    """

    def __init__(
        self,
        weight_config: EdgeWeightConfig | None = None,
        coarse_resolution: float = 0.5,
        fine_resolution: float = 1.5,
        detect_infrastructure: bool = True,
        infrastructure_threshold: float = 0.95,
    ) -> None:
        """Initialize the clustering engine.

        Args:
            weight_config: Configuration for edge weights. If None, uses defaults.
            coarse_resolution: Resolution for coarse clustering (lower = fewer clusters).
            fine_resolution: Resolution for fine clustering (higher = more clusters).
            detect_infrastructure: Whether to identify infrastructure nodes.
            infrastructure_threshold: Percentile threshold (0-1) for betweenness
                centrality to identify infrastructure nodes.
        """
        self.weight_config = weight_config or EdgeWeightConfig()
        self.coarse_resolution = coarse_resolution
        self.fine_resolution = fine_resolution
        self.detect_infrastructure = detect_infrastructure
        self.infrastructure_threshold = infrastructure_threshold
        self._graph: nx.Graph | None = None
        self._symbols: dict[str, Any] = {}

    def cluster(
        self,
        symbols: dict[str, Any],
        relationships: list[dict],
    ) -> dict[str, Any]:
        """Main entry point: cluster symbols and return hierarchical result.

        Args:
            symbols: Dict mapping symbol_id to symbol dict. Each symbol dict
                should contain keys like 'name', 'kind', 'file', 'module'.
            relationships: List of relationship dicts with "from", "to", "type" keys.
                The "type" can be "imports", "calls", "inherits", or "type_ref".

        Returns:
            Dictionary containing:
                - "hierarchy": Serialized ClusterNode tree (from to_dict())
                - "infrastructure": List of symbol IDs for cross-cutting concerns
                - "metrics": Overall clustering metrics dictionary
                - "metadata": Clustering parameters and timestamp
        """
        # Handle empty input
        if not symbols:
            return self._empty_result()

        self._symbols = symbols

        # Build the weighted graph
        self._graph = self._build_graph(symbols, relationships)

        # Handle edge cases
        if self._graph.number_of_nodes() == 0:
            return self._empty_result()

        # Detect infrastructure nodes before clustering
        infrastructure_symbols: list[str] = []
        if self.detect_infrastructure:
            infrastructure_symbols = self._detect_infrastructure()

        # Run Leiden at two resolutions
        coarse_clusters = self._run_leiden(self.coarse_resolution)
        fine_clusters = self._run_leiden(self.fine_resolution)

        # Build hierarchical structure
        hierarchy = self._build_hierarchy(coarse_clusters, fine_clusters, symbols)

        # Calculate overall metrics
        metrics = self._calculate_overall_metrics(coarse_clusters, fine_clusters)

        # Build metadata
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "coarse_resolution": self.coarse_resolution,
            "fine_resolution": self.fine_resolution,
            "detect_infrastructure": self.detect_infrastructure,
            "infrastructure_threshold": self.infrastructure_threshold,
            "num_symbols": len(symbols),
            "num_relationships": len(relationships),
            "num_coarse_clusters": len(coarse_clusters),
            "num_fine_clusters": len(fine_clusters),
        }

        # Compute cross-cluster edges for visualization
        cluster_edges = self._compute_cluster_edges(coarse_clusters, relationships)

        # Compute module-level dependencies for visualization
        module_dependencies = self._compute_module_dependencies(relationships)

        return {
            "hierarchy": hierarchy.to_dict(),
            "infrastructure": infrastructure_symbols,
            "metrics": metrics,
            "metadata": metadata,
            "relationships": relationships,  # Original relationships
            "cluster_edges": cluster_edges,  # Aggregated edges between clusters
            "module_dependencies": module_dependencies,  # Module-level aggregated deps
        }

    def _build_graph(
        self,
        symbols: dict[str, Any],
        relationships: list[dict],
    ) -> nx.Graph:
        """Build weighted NetworkX graph from symbols and relationships.

        Args:
            symbols: Dict mapping symbol_id to symbol dict.
            relationships: List of relationship dicts.

        Returns:
            NetworkX Graph with nodes for symbols and weighted edges for
            relationships.
        """
        graph = nx.Graph()
        weight_calculator = EdgeWeightCalculator(self.weight_config)

        # Add nodes for all symbols
        for symbol_id, symbol_data in symbols.items():
            graph.add_node(symbol_id, **symbol_data)

        # Add weighted edges for relationships
        for rel in relationships:
            from_id = rel.get("from")
            to_id = rel.get("to")

            # Skip invalid relationships
            if not from_id or not to_id:
                continue
            if from_id not in symbols or to_id not in symbols:
                continue
            if from_id == to_id:
                continue

            from_symbol = symbols[from_id]
            to_symbol = symbols[to_id]

            weight = weight_calculator.calculate_weight(rel, from_symbol, to_symbol)

            if weight > 0:
                # If edge already exists, add to existing weight
                if graph.has_edge(from_id, to_id):
                    graph[from_id][to_id]["weight"] += weight
                else:
                    graph.add_edge(from_id, to_id, weight=weight)

        return graph

    def _run_leiden(
        self,
        resolution: float,
    ) -> dict[str, list[str]]:
        """Run Leiden algorithm at specified resolution.

        Args:
            resolution: Resolution parameter for Leiden algorithm.
                Higher values produce more (smaller) clusters.

        Returns:
            Dict mapping cluster_id (string) to list of symbol_ids.
        """
        if self._graph is None or self._graph.number_of_nodes() == 0:
            return {}

        # Handle single-node case
        if self._graph.number_of_nodes() == 1:
            single_node = list(self._graph.nodes())[0]
            return {"0": [single_node]}

        # Handle no-edges case
        if self._graph.number_of_edges() == 0:
            # Each node is its own cluster
            return {
                str(i): [node]
                for i, node in enumerate(self._graph.nodes())
            }

        # Convert NetworkX graph to igraph
        # Create mapping from node names to indices
        node_list = list(self._graph.nodes())
        node_to_idx = {node: idx for idx, node in enumerate(node_list)}

        # Create igraph graph
        ig_graph = ig.Graph()
        ig_graph.add_vertices(len(node_list))

        # Add edges with weights
        edges = []
        weights = []
        for u, v, data in self._graph.edges(data=True):
            edges.append((node_to_idx[u], node_to_idx[v]))
            weights.append(data.get("weight", 1.0))

        ig_graph.add_edges(edges)
        ig_graph.es["weight"] = weights

        # Run Leiden algorithm
        partition = leidenalg.find_partition(
            ig_graph,
            leidenalg.RBConfigurationVertexPartition,
            weights=weights,
            resolution_parameter=resolution,
        )

        # Convert partition back to dict[cluster_id, list[symbol_id]]
        clusters: dict[str, list[str]] = {}
        for cluster_idx, cluster_members in enumerate(partition):
            cluster_id = str(cluster_idx)
            symbol_ids = [node_list[member_idx] for member_idx in cluster_members]
            if symbol_ids:
                clusters[cluster_id] = symbol_ids

        return clusters

    def _detect_infrastructure(self) -> list[str]:
        """Identify infrastructure/utility nodes via betweenness centrality.

        Infrastructure nodes are those with high betweenness centrality,
        indicating they serve as bridges between many parts of the codebase.
        These often represent utilities, base classes, or shared services.

        Returns:
            List of symbol IDs identified as infrastructure nodes.
        """
        if self._graph is None or self._graph.number_of_nodes() == 0:
            return []

        metrics_calculator = MetricsCalculator(self._graph)

        # Convert threshold from 0-1 to 0-100 percentile
        percentile = self.infrastructure_threshold * 100

        return metrics_calculator.identify_infrastructure_nodes(
            threshold_percentile=percentile
        )

    def _build_hierarchy(
        self,
        coarse: dict[str, list[str]],
        fine: dict[str, list[str]],
        symbols: dict[str, Any],
    ) -> ClusterNode:
        """Construct hierarchical ClusterNode tree.

        Args:
            coarse: Coarse-grained cluster assignments.
            fine: Fine-grained cluster assignments.
            symbols: Symbol metadata dictionary.

        Returns:
            Root ClusterNode of the hierarchy tree.
        """
        if self._graph is None:
            # Create minimal graph for metrics calculation
            graph = nx.Graph()
            for symbol_id in symbols:
                graph.add_node(symbol_id)
        else:
            graph = self._graph

        metrics_calculator = MetricsCalculator(graph)

        builder = HierarchyBuilder(
            coarse_clusters=coarse,
            fine_clusters=fine,
            symbols=symbols,
            metrics_calculator=metrics_calculator,
        )

        return builder.build()

    def _calculate_overall_metrics(
        self,
        coarse: dict[str, list[str]],
        fine: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Calculate overall clustering quality metrics.

        Args:
            coarse: Coarse-grained cluster assignments.
            fine: Fine-grained cluster assignments.

        Returns:
            Dictionary containing overall metrics.
        """
        if self._graph is None or self._graph.number_of_nodes() == 0:
            return {
                "modularity": 0.0,
                "coverage": 0.0,
                "avg_cluster_size": 0.0,
                "num_isolated_nodes": 0,
            }

        metrics_calculator = MetricsCalculator(self._graph)

        # Calculate modularity for coarse clusters
        total_modularity = 0.0
        for cluster_id, members in coarse.items():
            cluster_metrics = metrics_calculator.calculate_cluster_metrics(
                cluster_id, members
            )
            total_modularity += cluster_metrics.modularity_contribution

        # Calculate coverage (fraction of nodes in clusters)
        all_clustered_nodes = set()
        for members in coarse.values():
            all_clustered_nodes.update(members)
        coverage = (
            len(all_clustered_nodes) / self._graph.number_of_nodes()
            if self._graph.number_of_nodes() > 0
            else 0.0
        )

        # Calculate average cluster size
        avg_cluster_size = (
            sum(len(m) for m in coarse.values()) / len(coarse)
            if coarse
            else 0.0
        )

        # Count isolated nodes (not in any cluster)
        all_nodes = set(self._graph.nodes())
        isolated_nodes = all_nodes - all_clustered_nodes

        return {
            "modularity": total_modularity,
            "coverage": coverage,
            "avg_cluster_size": avg_cluster_size,
            "num_isolated_nodes": len(isolated_nodes),
        }

    def _compute_cluster_edges(
        self,
        clusters: dict[str, list[str]],
        relationships: list[dict],
    ) -> list[dict]:
        """Compute aggregated edges between clusters using the graph.

        Uses the internal graph edges which have correct node IDs that
        match the cluster member IDs.

        Args:
            clusters: Mapping of cluster IDs to symbol ID lists.
            relationships: Original symbol-level relationships (unused, kept for API).

        Returns:
            List of cluster edge dicts with "from_cluster", "to_cluster",
            "weight" (edge count), and "types" (relationship types).
        """
        if self._graph is None:
            return []

        # Build reverse mapping: symbol -> cluster
        symbol_to_cluster: dict[str, str] = {}
        for cluster_id, symbol_ids in clusters.items():
            for symbol_id in symbol_ids:
                symbol_to_cluster[symbol_id] = f"component_{cluster_id}"

        # Aggregate edges between clusters using graph edges
        edge_counts: dict[tuple[str, str], dict] = {}

        for from_id, to_id, data in self._graph.edges(data=True):
            from_cluster = symbol_to_cluster.get(from_id)
            to_cluster = symbol_to_cluster.get(to_id)

            if not from_cluster or not to_cluster:
                continue

            # Skip self-loops (within same cluster)
            if from_cluster == to_cluster:
                continue

            # Use edge weight from graph
            weight = data.get("weight", 1.0)

            edge_key = (from_cluster, to_cluster)
            if edge_key not in edge_counts:
                edge_counts[edge_key] = {"weight": 0.0, "types": set()}

            edge_counts[edge_key]["weight"] += weight
            edge_counts[edge_key]["types"].add("dependency")

        # Convert to list of dicts
        cluster_edges = []
        for (from_cluster, to_cluster), data in edge_counts.items():
            cluster_edges.append({
                "from_cluster": from_cluster,
                "to_cluster": to_cluster,
                "weight": int(data["weight"]),  # Round to int
                "types": list(data["types"]),
            })

        # Sort by weight descending
        cluster_edges.sort(key=lambda e: e["weight"], reverse=True)

        return cluster_edges

    def _compute_module_dependencies(
        self,
        relationships: list[dict],
    ) -> list[dict]:
        """Compute module-level dependencies from relationships.

        Aggregates cross-module internal relationships into module pairs
        with call counts and examples. Internal relationships are determined
        by checking if both endpoints exist in the symbol lookup.

        Args:
            relationships: List of relationship dicts with "from" and "to" keys.

        Returns:
            List of module dependency dicts sorted by call count
        """
        module_deps: dict[tuple[str, str], dict] = {}

        for rel in relationships:
            # Determine if relationship is internal by checking if both endpoints
            # exist in the symbol lookup (fixes #60 - is_internal flag not always set)
            from_id = rel.get("from")
            to_id = rel.get("to")
            if not from_id or not to_id:
                continue
            if from_id not in self._symbols or to_id not in self._symbols:
                continue

            from_mod = from_id.split(":")[0]
            to_mod = to_id.split(":")[0]
            if from_mod == to_mod:
                continue

            key = (from_mod, to_mod)
            if key not in module_deps:
                module_deps[key] = {
                    "from_module": from_mod,
                    "to_module": to_mod,
                    "count": 0,
                    "examples": [],
                }
            module_deps[key]["count"] += 1
            if len(module_deps[key]["examples"]) < 3:
                module_deps[key]["examples"].append({
                    "from": rel["from"],
                    "to": rel["to"],
                    "type": rel.get("type", "calls"),
                })

        return sorted(
            module_deps.values(),
            key=lambda d: -d["count"],
        )

    def _empty_result(self) -> dict[str, Any]:
        """Return an empty clustering result for edge cases.

        Returns:
            Dictionary with empty/default values for all result fields.
        """
        empty_root = ClusterNode(
            id="root",
            level="container",
            label=None,
            members=[],
            children=[],
            metrics=None,
            parent_id=None,
        )

        return {
            "hierarchy": empty_root.to_dict(),
            "infrastructure": [],
            "metrics": {
                "modularity": 0.0,
                "coverage": 0.0,
                "avg_cluster_size": 0.0,
                "num_isolated_nodes": 0,
            },
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "coarse_resolution": self.coarse_resolution,
                "fine_resolution": self.fine_resolution,
                "detect_infrastructure": self.detect_infrastructure,
                "infrastructure_threshold": self.infrastructure_threshold,
                "num_symbols": 0,
                "num_relationships": 0,
                "num_coarse_clusters": 0,
                "num_fine_clusters": 0,
            },
            "relationships": [],
            "cluster_edges": [],
            "module_dependencies": [],
        }

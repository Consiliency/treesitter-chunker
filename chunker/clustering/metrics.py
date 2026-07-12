"""Quality metrics for cluster evaluation.

This module provides tools for calculating and evaluating cluster quality metrics
including density, cohesion, coupling, and modularity contribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass
class ClusterMetrics:
    """Metrics for evaluating the quality of a single cluster.

    Attributes:
        cluster_id: Unique identifier for the cluster.
        size: Number of symbols in the cluster.
        internal_edges: Number of edges within the cluster.
        external_edges: Number of edges leaving the cluster.
        density: Ratio of internal edges to maximum possible edges.
        cohesion: Normalized internal connectivity (0-1).
        coupling: Normalized external connectivity (0-1).
        modularity_contribution: Contribution to overall modularity score.
    """

    cluster_id: str
    size: int
    internal_edges: int
    external_edges: int
    density: float
    cohesion: float
    coupling: float
    modularity_contribution: float

    @property
    def quality_score(self) -> float:
        """Calculate combined quality score.

        Returns a value between 0 and 1, where higher values indicate
        better cluster quality. The formula balances cohesion against
        coupling, with a small epsilon to avoid division by zero.

        Returns:
            Quality score in range [0, 1].
        """
        return self.cohesion / (self.cohesion + self.coupling + 0.001)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary representation.

        Returns:
            Dictionary containing all metric fields and computed quality_score.
        """
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "internal_edges": self.internal_edges,
            "external_edges": self.external_edges,
            "density": self.density,
            "cohesion": self.cohesion,
            "coupling": self.coupling,
            "modularity_contribution": self.modularity_contribution,
            "quality_score": self.quality_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClusterMetrics:
        """Create ClusterMetrics from dictionary.

        Args:
            data: Dictionary containing metric fields. The 'quality_score'
                field is ignored as it's computed from other fields.

        Returns:
            New ClusterMetrics instance.
        """
        return cls(
            cluster_id=data["cluster_id"],
            size=data["size"],
            internal_edges=data["internal_edges"],
            external_edges=data["external_edges"],
            density=data["density"],
            cohesion=data["cohesion"],
            coupling=data["coupling"],
            modularity_contribution=data["modularity_contribution"],
        )


class MetricsCalculator:
    """Calculator for cluster quality metrics.

    Uses a networkx graph to compute various metrics that measure
    cluster quality including density, cohesion, and coupling.

    Attributes:
        graph: The networkx graph to analyze.
    """

    def __init__(self, graph: nx.Graph) -> None:
        """Initialize the metrics calculator.

        Args:
            graph: A networkx Graph representing symbol relationships.
        """
        self.graph = graph

    def calculate_cluster_metrics(
        self, cluster_id: str, members: list[str]
    ) -> ClusterMetrics:
        """Calculate comprehensive metrics for a cluster.

        Args:
            cluster_id: Unique identifier for the cluster.
            members: List of node identifiers belonging to the cluster.

        Returns:
            ClusterMetrics instance with all computed metrics.
        """
        size = len(members)

        if size == 0:
            return ClusterMetrics(
                cluster_id=cluster_id,
                size=0,
                internal_edges=0,
                external_edges=0,
                density=0.0,
                cohesion=0.0,
                coupling=0.0,
                modularity_contribution=0.0,
            )

        member_set = set(members)
        internal_edges = 0
        external_edges = 0

        # Count internal and external edges
        for member in members:
            if member not in self.graph:
                continue
            for neighbor in self.graph.neighbors(member):
                if neighbor in member_set:
                    internal_edges += 1
                else:
                    external_edges += 1

        # Internal edges are counted twice (once from each endpoint)
        internal_edges //= 2

        density = self.calculate_density(members)
        cohesion = self.calculate_cohesion(members)
        coupling = self.calculate_coupling(members)

        # Calculate modularity contribution
        modularity_contribution = self._calculate_modularity_contribution(
            members, internal_edges, external_edges
        )

        return ClusterMetrics(
            cluster_id=cluster_id,
            size=size,
            internal_edges=internal_edges,
            external_edges=external_edges,
            density=density,
            cohesion=cohesion,
            coupling=coupling,
            modularity_contribution=modularity_contribution,
        )

    def calculate_density(self, members: list[str]) -> float:
        """Calculate the density of a cluster.

        Density is the ratio of actual internal edges to the maximum
        possible edges in a complete graph of the same size.

        Args:
            members: List of node identifiers in the cluster.

        Returns:
            Density value in range [0, 1]. Returns 0 for empty clusters
            or clusters with fewer than 2 members.
        """
        size = len(members)
        if size < 2:
            return 0.0

        member_set = set(members)
        internal_edges = 0

        for member in members:
            if member not in self.graph:
                continue
            for neighbor in self.graph.neighbors(member):
                if neighbor in member_set:
                    internal_edges += 1

        # Edges counted twice, divide by 2
        internal_edges //= 2

        # Maximum possible edges in a complete graph
        max_edges = size * (size - 1) // 2

        return internal_edges / max_edges if max_edges > 0 else 0.0

    def calculate_cohesion(self, members: list[str]) -> float:
        """Calculate the cohesion of a cluster.

        Cohesion measures the normalized internal connectivity, representing
        how well-connected the members are to each other relative to their
        potential connections.

        Args:
            members: List of node identifiers in the cluster.

        Returns:
            Cohesion value in range [0, 1]. Returns 0 for empty clusters
            or clusters with a single member.
        """
        size = len(members)
        if size < 2:
            return 0.0

        member_set = set(members)
        total_internal_degree = 0

        for member in members:
            if member not in self.graph:
                continue
            for neighbor in self.graph.neighbors(member):
                if neighbor in member_set:
                    total_internal_degree += 1

        # Maximum internal degree: each node connected to all others
        max_internal_degree = size * (size - 1)

        return (
            total_internal_degree / max_internal_degree
            if max_internal_degree > 0
            else 0.0
        )

    def calculate_coupling(self, members: list[str]) -> float:
        """Calculate the coupling of a cluster.

        Coupling measures the normalized external connectivity, representing
        how many connections exist between cluster members and non-members.

        Args:
            members: List of node identifiers in the cluster.

        Returns:
            Coupling value in range [0, 1]. Returns 0 for empty clusters
            or when there are no external connections.
        """
        size = len(members)
        if size == 0:
            return 0.0

        member_set = set(members)
        external_edges = 0
        total_degree = 0

        for member in members:
            if member not in self.graph:
                continue
            for neighbor in self.graph.neighbors(member):
                total_degree += 1
                if neighbor not in member_set:
                    external_edges += 1

        # Normalize by total degree to get coupling ratio
        return external_edges / total_degree if total_degree > 0 else 0.0

    def _calculate_modularity_contribution(
        self, members: list[str], internal_edges: int, external_edges: int
    ) -> float:
        """Calculate the modularity contribution of a cluster.

        Modularity measures how much better the cluster structure is
        compared to a random graph with the same degree sequence.

        Args:
            members: List of node identifiers in the cluster.
            internal_edges: Number of edges within the cluster.
            external_edges: Number of edges leaving the cluster.

        Returns:
            Modularity contribution value, typically in range [-0.5, 1].
        """
        if not members:
            return 0.0

        total_edges = self.graph.number_of_edges()
        if total_edges == 0:
            return 0.0

        # Calculate sum of degrees for cluster members
        degree_sum = 0
        for member in members:
            if member in self.graph:
                degree_sum += self.graph.degree(member)

        # Actual fraction of edges within cluster
        # internal_edges represents undirected edges
        e_ii = internal_edges / total_edges

        # Expected fraction based on degree sum
        # (degree_sum / (2 * total_edges))^2
        a_i = degree_sum / (2 * total_edges)

        return e_ii - (a_i * a_i)

    def identify_infrastructure_nodes(
        self, threshold_percentile: float = 95
    ) -> list[str]:
        """Identify high-betweenness nodes that are cross-cutting concerns.

        Infrastructure nodes are those with high betweenness centrality,
        indicating they serve as bridges between many parts of the graph.
        These often represent utilities, base classes, or shared services.

        Args:
            threshold_percentile: Percentile threshold for betweenness
                centrality (0-100). Nodes above this threshold are
                considered infrastructure. Defaults to 95.

        Returns:
            List of node identifiers for infrastructure nodes.
        """
        if self.graph.number_of_nodes() == 0:
            return []

        # Calculate betweenness centrality for all nodes
        betweenness = nx.betweenness_centrality(self.graph)

        if not betweenness:
            return []

        # Get the threshold value
        values = sorted(betweenness.values())
        if not values:
            return []

        # Calculate the index for the percentile
        index = int(len(values) * threshold_percentile / 100)
        index = min(index, len(values) - 1)
        threshold_value = values[index]

        # Find nodes above the threshold
        infrastructure_nodes = [
            node
            for node, centrality in betweenness.items()
            if centrality >= threshold_value and centrality > 0
        ]

        return infrastructure_nodes

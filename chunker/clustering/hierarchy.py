"""Hierarchical structure building from flat clusters.

This module provides functionality to build hierarchical cluster structures
from flat cluster assignments, organizing them into a tree structure with
multiple levels (container, component, code).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .metrics import ClusterMetrics, MetricsCalculator


@dataclass
class ClusterNode:
    """A node in the cluster hierarchy tree.

    Represents a cluster at any level of the hierarchy, containing
    member symbols and potentially child clusters.

    Attributes:
        id: Unique identifier for this cluster node.
        level: Hierarchy level ('container', 'component', or 'code').
        label: Human-readable name for the cluster, None if not yet labeled.
        members: List of symbol IDs that belong to this cluster.
        children: List of child cluster nodes.
        metrics: Quality metrics for this cluster, None if not computed.
        parent_id: ID of the parent cluster, None for root nodes.
    """

    id: str
    level: str
    label: str | None = None
    members: list[str] = field(default_factory=list)
    children: list[ClusterNode] = field(default_factory=list)
    metrics: ClusterMetrics | None = None
    parent_id: str | None = None

    def to_dict(self) -> dict:
        """Serialize the cluster node to a dictionary.

        Recursively converts this node and all children to a dictionary
        structure suitable for JSON serialization.

        Returns:
            Dictionary representation of this cluster node.
        """
        result = {
            "id": self.id,
            "level": self.level,
            "label": self.label,
            "members": self.members.copy(),
            "children": [child.to_dict() for child in self.children],
            "parent_id": self.parent_id,
        }

        if self.metrics is not None:
            # Assume ClusterMetrics has a to_dict method or is a dataclass
            if hasattr(self.metrics, "to_dict"):
                result["metrics"] = self.metrics.to_dict()
            elif hasattr(self.metrics, "__dict__"):
                result["metrics"] = {
                    k: v
                    for k, v in self.metrics.__dict__.items()
                    if not k.startswith("_")
                }
            else:
                result["metrics"] = self.metrics
        else:
            result["metrics"] = None

        return result

    @classmethod
    def from_dict(cls, data: dict) -> ClusterNode:
        """Deserialize a cluster node from a dictionary.

        Recursively reconstructs the cluster node tree from a dictionary
        structure.

        Args:
            data: Dictionary containing cluster node data.

        Returns:
            Reconstructed ClusterNode instance.

        Note:
            The metrics field is stored as a raw dictionary since we cannot
            reconstruct the ClusterMetrics object without its class definition.
            Callers should handle metrics reconstruction separately if needed.
        """
        children = [
            cls.from_dict(child_data) for child_data in data.get("children", [])
        ]

        return cls(
            id=data["id"],
            level=data["level"],
            label=data.get("label"),
            members=data.get("members", []).copy(),
            children=children,
            metrics=data.get("metrics"),  # Stored as dict, reconstruct separately
            parent_id=data.get("parent_id"),
        )


class HierarchyBuilder:
    """Builds hierarchical cluster structures from flat cluster assignments.

    Takes coarse (component-level) and fine (sub-component-level) cluster
    assignments and constructs a tree structure with proper nesting.

    The hierarchy follows a simplified C4-inspired model:
    - Level 0 (depth 0): Container - the root encompassing all clusters
    - Level 1 (depth 1): Component - coarse-grained functional groupings
    - Level 2+ (depth 2+): Code - fine-grained code-level clusters

    Attributes:
        coarse_clusters: Mapping of cluster IDs to lists of symbol IDs
            at the component level.
        fine_clusters: Mapping of cluster IDs to lists of symbol IDs
            at the sub-component level.
        symbols: Mapping of symbol IDs to symbol metadata dictionaries.
        metrics_calculator: Calculator for computing cluster quality metrics.
    """

    def __init__(
        self,
        coarse_clusters: dict[str, list[str]],
        fine_clusters: dict[str, list[str]],
        symbols: dict[str, dict],
        metrics_calculator: MetricsCalculator,
    ) -> None:
        """Initialize the hierarchy builder.

        Args:
            coarse_clusters: Mapping of cluster IDs to symbol ID lists
                at the component level.
            fine_clusters: Mapping of cluster IDs to symbol ID lists
                at the sub-component level.
            symbols: Mapping of symbol IDs to symbol metadata dictionaries
                containing keys like 'name', 'kind', 'module', 'file', etc.
            metrics_calculator: Calculator instance for computing cluster
                quality metrics.
        """
        self.coarse_clusters = coarse_clusters
        self.fine_clusters = fine_clusters
        self.symbols = symbols
        self.metrics_calculator = metrics_calculator

    def build(self) -> ClusterNode:
        """Build the complete cluster hierarchy from root.

        Constructs a tree structure with a single root container node
        containing component nodes, which in turn contain code-level nodes.

        Returns:
            The root ClusterNode representing the entire hierarchy.
        """
        # Create the root container node
        all_symbol_ids = list(self.symbols.keys())
        root = ClusterNode(
            id="root",
            level=self._assign_level(0),
            label=None,
            members=all_symbol_ids,
            children=[],
            metrics=None,
            parent_id=None,
        )

        # Create and attach component-level nodes
        component_nodes = self._create_component_nodes()
        for component in component_nodes:
            component.parent_id = root.id
            root.children.append(component)

        # Calculate metrics for root if calculator is available
        if self.metrics_calculator is not None:
            try:
                root.metrics = self.metrics_calculator.calculate(root)
            except Exception:
                # Gracefully handle metrics calculation failures
                pass

        return root

    def _create_component_nodes(self) -> list[ClusterNode]:
        """Create component-level cluster nodes from coarse clusters.

        Returns:
            List of ClusterNode instances at the component level.
        """
        component_nodes = []

        for cluster_id, symbol_ids in self.coarse_clusters.items():
            # Filter to only valid symbol IDs
            valid_symbol_ids = [sid for sid in symbol_ids if sid in self.symbols]

            if not valid_symbol_ids:
                continue

            # Auto-generate label from common module prefix
            label = self._infer_label(valid_symbol_ids)

            component = ClusterNode(
                id=f"component_{cluster_id}",
                level=self._assign_level(1),
                label=label,
                members=valid_symbol_ids,
                children=[],
                metrics=None,
                parent_id=None,  # Will be set by caller
            )

            # Nest fine-grained clusters within this component
            code_nodes = self._nest_fine_clusters(component)
            for code_node in code_nodes:
                code_node.parent_id = component.id
                component.children.append(code_node)

            # Calculate metrics for component if calculator is available
            if self.metrics_calculator is not None:
                try:
                    component.metrics = self.metrics_calculator.calculate(component)
                except Exception:
                    # Gracefully handle metrics calculation failures
                    pass

            component_nodes.append(component)

        return component_nodes

    def _nest_fine_clusters(self, component: ClusterNode) -> list[ClusterNode]:
        """Nest fine-grained clusters within a component.

        Finds fine clusters whose symbols overlap with the component's
        members and creates code-level nodes for them.

        Args:
            component: The parent component node.

        Returns:
            List of ClusterNode instances at the code level.
        """
        code_nodes = []
        component_member_set = set(component.members)
        assigned_symbols = set()

        for cluster_id, symbol_ids in self.fine_clusters.items():
            # Find symbols that belong to both this fine cluster and the component
            overlapping_symbols = [
                sid
                for sid in symbol_ids
                if sid in component_member_set and sid in self.symbols
            ]

            if not overlapping_symbols:
                continue

            code_node = ClusterNode(
                id=f"code_{component.id}_{cluster_id}",
                level=self._assign_level(2),
                label=None,
                members=overlapping_symbols,
                children=[],
                metrics=None,
                parent_id=None,  # Will be set by caller
            )

            # Calculate metrics for code node if calculator is available
            if self.metrics_calculator is not None:
                try:
                    code_node.metrics = self.metrics_calculator.calculate(code_node)
                except Exception:
                    # Gracefully handle metrics calculation failures
                    pass

            code_nodes.append(code_node)
            assigned_symbols.update(overlapping_symbols)

        # Handle any symbols not assigned to fine clusters
        unassigned_symbols = [
            sid
            for sid in component.members
            if sid not in assigned_symbols and sid in self.symbols
        ]

        if unassigned_symbols:
            # Create individual code nodes for unassigned symbols
            orphan_nodes = self._create_code_nodes(unassigned_symbols)
            code_nodes.extend(orphan_nodes)

        return code_nodes

    def _create_code_nodes(self, symbol_ids: list[str]) -> list[ClusterNode]:
        """Create code-level nodes for individual symbols.

        Used for symbols that don't belong to any fine-grained cluster.

        Args:
            symbol_ids: List of symbol IDs to create nodes for.

        Returns:
            List of ClusterNode instances, one per symbol.
        """
        code_nodes = []

        for symbol_id in symbol_ids:
            if symbol_id not in self.symbols:
                continue

            symbol = self.symbols[symbol_id]
            # Use symbol name as a hint for the node ID
            symbol_name = symbol.get("name", symbol_id)

            code_node = ClusterNode(
                id=f"code_orphan_{symbol_id}",
                level=self._assign_level(2),
                label=symbol_name,
                members=[symbol_id],
                children=[],
                metrics=None,
                parent_id=None,  # Will be set by caller
            )

            # Calculate metrics for code node if calculator is available
            if self.metrics_calculator is not None:
                try:
                    code_node.metrics = self.metrics_calculator.calculate(code_node)
                except Exception:
                    # Gracefully handle metrics calculation failures
                    pass

            code_nodes.append(code_node)

        return code_nodes

    def _assign_level(self, depth: int) -> str:
        """Map tree depth to C4-style level name.

        Args:
            depth: The depth in the hierarchy tree (0 = root).

        Returns:
            Level name string: 'container', 'component', or 'code'.
        """
        level_mapping = {
            0: "container",
            1: "component",
        }
        # Depth 2 and beyond are all 'code' level
        return level_mapping.get(depth, "code")

    def _infer_label(self, symbol_ids: list[str]) -> str | None:
        """Infer a human-readable label for a cluster based on its members.

        Looks for common module prefixes or file paths among the symbols
        to generate a meaningful cluster name.

        Args:
            symbol_ids: List of symbol IDs in the cluster.

        Returns:
            Inferred label string, or None if no good label can be determined.
        """
        if not symbol_ids:
            return None

        # Extract module names from symbol IDs (format: "module:ClassName" or "module:func")
        modules = []
        for sid in symbol_ids:
            if ":" in sid:
                module = sid.split(":")[0]
                modules.append(module)
            else:
                # Fallback: try to get from symbol metadata
                sym = self.symbols.get(sid, {})
                if "module" in sym:
                    modules.append(sym["module"])
                elif "file" in sym:
                    # Use file path as fallback
                    modules.append(sym["file"])

        if not modules:
            return None

        # Find common prefix among modules
        if len(modules) == 1:
            return modules[0]

        # Find longest common prefix
        common = modules[0]
        for module in modules[1:]:
            # Find common prefix
            new_common = ""
            for i, (a, b) in enumerate(zip(common, module)):
                if a == b:
                    new_common += a
                else:
                    break
            common = new_common
            if not common:
                break

        # Clean up the prefix (remove trailing dots, underscores)
        common = common.rstrip("._/")

        if common:
            return common

        # Fallback: use the most common module
        from collections import Counter

        counter = Counter(modules)
        most_common = counter.most_common(1)
        if most_common:
            return most_common[0][0]

        return None

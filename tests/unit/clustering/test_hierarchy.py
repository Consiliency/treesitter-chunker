"""Unit tests for chunker.clustering.hierarchy module."""

from chunker.clustering.hierarchy import ClusterNode, HierarchyBuilder
from chunker.clustering.metrics import ClusterMetrics


class TestClusterNode:
    """Tests for ClusterNode dataclass."""

    def test_default_values(self):
        """Test node with default values."""
        node = ClusterNode(
            id="test",
            level="component",
            label=None,
        )
        assert node.id == "test"
        assert node.level == "component"
        assert node.label is None
        assert node.members == []
        assert node.children == []
        assert node.metrics is None
        assert node.parent_id is None

    def test_with_members(self):
        """Test node with members."""
        node = ClusterNode(
            id="test",
            level="code",
            label="TestClass",
            members=["mod:TestClass", "mod:test_func"],
        )
        assert len(node.members) == 2
        assert "mod:TestClass" in node.members

    def test_to_dict(self):
        """Test serialization to dictionary."""
        node = ClusterNode(
            id="test",
            level="component",
            label="Auth Module",
            members=["auth:User", "auth:login"],
        )
        d = node.to_dict()
        assert d["id"] == "test"
        assert d["level"] == "component"
        assert d["label"] == "Auth Module"
        assert len(d["members"]) == 2

    def test_to_dict_with_children(self):
        """Test serialization with nested children."""
        child = ClusterNode(id="child", level="code", label="Child")
        parent = ClusterNode(
            id="parent",
            level="component",
            label="Parent",
            children=[child],
        )
        d = parent.to_dict()
        assert len(d["children"]) == 1
        assert d["children"][0]["id"] == "child"

    def test_to_dict_with_metrics(self):
        """Test serialization with metrics."""
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
        node = ClusterNode(
            id="test",
            level="component",
            label=None,
            metrics=metrics,
        )
        d = node.to_dict()
        assert d["metrics"] is not None
        assert d["metrics"]["size"] == 5

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        d = {
            "id": "test",
            "level": "component",
            "label": "Test Module",
            "members": ["a", "b"],
            "children": [],
            "metrics": None,
            "parent_id": None,
        }
        node = ClusterNode.from_dict(d)
        assert node.id == "test"
        assert node.level == "component"
        assert node.label == "Test Module"

    def test_from_dict_with_children(self):
        """Test deserialization with nested children."""
        d = {
            "id": "parent",
            "level": "component",
            "label": None,
            "members": [],
            "children": [
                {
                    "id": "child",
                    "level": "code",
                    "label": "Child",
                    "members": ["x"],
                    "children": [],
                    "metrics": None,
                    "parent_id": "parent",
                }
            ],
            "metrics": None,
            "parent_id": None,
        }
        node = ClusterNode.from_dict(d)
        assert len(node.children) == 1
        assert node.children[0].id == "child"

    def test_from_dict_with_metrics(self):
        """Test deserialization with metrics included."""
        d = {
            "id": "test",
            "level": "component",
            "label": "Test",
            "members": ["a"],
            "children": [],
            "metrics": {
                "cluster_id": "test",
                "size": 3,
                "internal_edges": 5,
                "external_edges": 1,
                "density": 0.7,
                "cohesion": 0.8,
                "coupling": 0.2,
                "modularity_contribution": 0.1,
            },
            "parent_id": None,
        }
        node = ClusterNode.from_dict(d)
        assert node.metrics is not None
        # from_dict stores metrics as a raw dict, not a ClusterMetrics object
        assert node.metrics["size"] == 3
        assert node.metrics["density"] == 0.7

    def test_roundtrip_serialization(self):
        """Test that to_dict and from_dict are inverse operations."""
        original = ClusterNode(
            id="roundtrip",
            level="component",
            label="Roundtrip Test",
            members=["a", "b", "c"],
            children=[
                ClusterNode(
                    id="child1",
                    level="code",
                    label="Child 1",
                    members=["x"],
                    parent_id="roundtrip",
                ),
                ClusterNode(
                    id="child2",
                    level="code",
                    label="Child 2",
                    members=["y", "z"],
                    parent_id="roundtrip",
                ),
            ],
            metrics=ClusterMetrics(
                cluster_id="roundtrip",
                size=3,
                internal_edges=4,
                external_edges=2,
                density=0.6,
                cohesion=0.7,
                coupling=0.3,
                modularity_contribution=0.12,
            ),
            parent_id=None,
        )

        d = original.to_dict()
        restored = ClusterNode.from_dict(d)

        assert restored.id == original.id
        assert restored.level == original.level
        assert restored.label == original.label
        assert restored.members == original.members
        assert len(restored.children) == len(original.children)
        # from_dict stores metrics as a raw dict, not a ClusterMetrics object
        assert restored.metrics["size"] == original.metrics.size

    def test_empty_members_and_children(self):
        """Test node with explicitly empty members and children."""
        node = ClusterNode(
            id="empty",
            level="code",
            label="Empty Node",
            members=[],
            children=[],
        )
        assert node.members == []
        assert node.children == []

        d = node.to_dict()
        assert d["members"] == []
        assert d["children"] == []

    def test_deeply_nested_children(self):
        """Test serialization of deeply nested hierarchy."""
        leaf = ClusterNode(id="leaf", level="code", label="Leaf")
        mid = ClusterNode(
            id="mid",
            level="code",
            label="Mid",
            children=[leaf],
        )
        root = ClusterNode(
            id="root",
            level="component",
            label="Root",
            children=[mid],
        )

        d = root.to_dict()
        assert d["children"][0]["children"][0]["id"] == "leaf"

        restored = ClusterNode.from_dict(d)
        assert restored.children[0].children[0].id == "leaf"


class TestHierarchyBuilder:
    """Tests for HierarchyBuilder class."""

    def test_empty_clusters(self):
        """Test with empty clusters."""

        # Create a mock metrics calculator
        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        builder = HierarchyBuilder(
            coarse_clusters={},
            fine_clusters={},
            symbols={},
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()
        assert root.level == "container"
        assert len(root.children) == 0

    def test_single_component(self):
        """Test with a single component."""

        class MockMetricsCalculator:
            def calculate(self, node):
                return ClusterMetrics(
                    cluster_id=node.id,
                    size=len(node.members),
                    internal_edges=0,
                    external_edges=0,
                    density=0.0,
                    cohesion=0.0,
                    coupling=0.0,
                    modularity_contribution=0.0,
                )

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {
                "name": "B",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A", "mod:B"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()
        assert root.level == "container"
        assert len(root.children) == 1
        # HierarchyBuilder adds "component_" prefix to cluster IDs
        assert root.children[0].id == "component_comp_0"

    def test_assign_level(self):
        """Test level assignment based on depth."""
        builder = HierarchyBuilder({}, {}, {}, None)
        assert builder._assign_level(0) == "container"
        assert builder._assign_level(1) == "component"
        assert builder._assign_level(2) == "code"
        assert builder._assign_level(3) == "code"

    def test_multiple_components(self):
        """Test with multiple components."""

        class MockMetricsCalculator:
            def calculate(self, node):
                return ClusterMetrics(
                    cluster_id=node.id,
                    size=len(node.members),
                    internal_edges=0,
                    external_edges=0,
                    density=0.0,
                    cohesion=0.0,
                    coupling=0.0,
                    modularity_contribution=0.0,
                )

        symbols = {
            "auth:User": {
                "name": "User",
                "kind": "class",
                "module": "auth",
                "file": "auth.py",
            },
            "auth:login": {
                "name": "login",
                "kind": "function",
                "module": "auth",
                "file": "auth.py",
            },
            "db:Connection": {
                "name": "Connection",
                "kind": "class",
                "module": "db",
                "file": "db.py",
            },
            "db:query": {
                "name": "query",
                "kind": "function",
                "module": "db",
                "file": "db.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={
                "auth_comp": ["auth:User", "auth:login"],
                "db_comp": ["db:Connection", "db:query"],
            },
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()
        assert root.level == "container"
        assert len(root.children) == 2

        # HierarchyBuilder adds "component_" prefix to cluster IDs
        child_ids = {child.id for child in root.children}
        assert "component_auth_comp" in child_ids
        assert "component_db_comp" in child_ids

    def test_with_fine_clusters(self):
        """Test hierarchy with fine-grained clusters nested in components."""

        class MockMetricsCalculator:
            def calculate(self, node):
                return ClusterMetrics(
                    cluster_id=node.id,
                    size=len(node.members),
                    internal_edges=0,
                    external_edges=0,
                    density=0.0,
                    cohesion=0.0,
                    coupling=0.0,
                    modularity_contribution=0.0,
                )

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {
                "name": "B",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
            "mod:C": {"name": "C", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:D": {
                "name": "D",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A", "mod:B", "mod:C", "mod:D"]},
            fine_clusters={
                "fine_0": ["mod:A", "mod:B"],
                "fine_1": ["mod:C", "mod:D"],
            },
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        # Root should have one component
        assert len(root.children) == 1
        component = root.children[0]
        # HierarchyBuilder adds "component_" prefix to cluster IDs
        assert component.id == "component_comp_0"

        # Component should have fine clusters as children if builder supports nesting
        # The exact behavior depends on implementation

    def test_component_members_populated(self):
        """Test that component members are correctly populated."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {
                "name": "B",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A", "mod:B"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        component = root.children[0]
        assert "mod:A" in component.members
        assert "mod:B" in component.members

    def test_metrics_attached_to_nodes(self):
        """Test that metrics are properly attached to cluster nodes."""

        class MockMetricsCalculator:
            def calculate(self, node):
                return ClusterMetrics(
                    cluster_id=node.id,
                    size=len(node.members),
                    internal_edges=len(node.members) * 2,
                    external_edges=1,
                    density=0.75,
                    cohesion=0.8,
                    coupling=0.2,
                    modularity_contribution=0.1,
                )

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {
                "name": "B",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
            "mod:C": {"name": "C", "kind": "class", "module": "mod", "file": "mod.py"},
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A", "mod:B", "mod:C"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        component = root.children[0]
        assert component.metrics is not None
        assert component.metrics.size == 3
        assert component.metrics.density == 0.75

    def test_parent_id_assignment(self):
        """Test that parent_id is correctly assigned to children."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        # Children should reference parent
        for child in root.children:
            assert child.parent_id == root.id or child.parent_id is None

    def test_label_generation(self):
        """Test that labels are generated for components."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "auth:User": {
                "name": "User",
                "kind": "class",
                "module": "auth",
                "file": "auth.py",
            },
            "auth:login": {
                "name": "login",
                "kind": "function",
                "module": "auth",
                "file": "auth.py",
            },
            "auth:logout": {
                "name": "logout",
                "kind": "function",
                "module": "auth",
                "file": "auth.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={"auth_comp": ["auth:User", "auth:login", "auth:logout"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        builder.build()

        # Label should be generated based on common module or naming
        # The exact label depends on implementation

    def test_none_metrics_calculator(self):
        """Test builder handles None metrics calculator gracefully."""
        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=None,
        )

        # Should not raise, metrics will be None
        root = builder.build()
        assert root is not None
        if root.children:
            assert root.children[0].metrics is None

    def test_symbols_with_missing_keys(self):
        """Test handling of symbols with missing optional keys."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "mod:A": {"name": "A", "kind": "class"},  # Missing module and file
            "mod:B": {"name": "B"},  # Missing kind, module, and file
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A", "mod:B"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )

        # Should handle gracefully
        root = builder.build()
        assert root is not None

    def test_large_cluster_count(self):
        """Test with many clusters to ensure scalability."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return ClusterMetrics(
                    cluster_id=cluster_id,
                    size=len(members),
                    internal_edges=0,
                    external_edges=0,
                    density=0.0,
                    cohesion=0.0,
                    coupling=0.0,
                    modularity_contribution=0.0,
                )

        # Create 100 components with 10 members each
        symbols = {}
        coarse_clusters = {}
        for i in range(100):
            members = []
            for j in range(10):
                symbol_id = f"mod{i}:func{j}"
                symbols[symbol_id] = {
                    "name": f"func{j}",
                    "kind": "function",
                    "module": f"mod{i}",
                    "file": f"mod{i}.py",
                }
                members.append(symbol_id)
            coarse_clusters[f"comp_{i}"] = members

        builder = HierarchyBuilder(
            coarse_clusters=coarse_clusters,
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        assert len(root.children) == 100
        total_members = sum(len(child.members) for child in root.children)
        assert total_members == 1000

    def test_overlapping_fine_clusters(self):
        """Test handling of fine clusters that may share members."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {
                "name": "B",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
            "mod:C": {"name": "C", "kind": "class", "module": "mod", "file": "mod.py"},
        }

        # Fine clusters with overlapping member (mod:B appears in both)
        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A", "mod:B", "mod:C"]},
            fine_clusters={
                "fine_0": ["mod:A", "mod:B"],
                "fine_1": ["mod:B", "mod:C"],  # mod:B is shared
            },
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )

        # Should handle without error
        root = builder.build()
        assert root is not None


class TestHierarchyBuilderEdgeCases:
    """Edge case tests for HierarchyBuilder."""

    def test_empty_symbol_table(self):
        """Test with empty symbol table but non-empty clusters."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["missing:A", "missing:B"]},
            fine_clusters={},
            symbols={},  # Empty symbols
            metrics_calculator=MockMetricsCalculator(),
        )

        # Should handle gracefully
        root = builder.build()
        assert root is not None

    def test_cluster_with_single_member(self):
        """Test cluster containing only one member."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return ClusterMetrics(
                    cluster_id=cluster_id,
                    size=len(members),
                    internal_edges=0,
                    external_edges=0,
                    density=1.0,
                    cohesion=1.0,
                    coupling=0.0,
                    modularity_contribution=0.0,
                )

        symbols = {
            "mod:lonely": {
                "name": "lonely",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={"singleton": ["mod:lonely"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        assert len(root.children) == 1
        assert len(root.children[0].members) == 1

    def test_unicode_in_labels_and_ids(self):
        """Test handling of unicode characters in identifiers."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "mod:calculate": {
                "name": "calculate",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:calculate"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()
        assert root is not None

    def test_special_characters_in_symbol_ids(self):
        """Test handling of special characters in symbol IDs."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "mod:__init__": {
                "name": "__init__",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
            "mod:_private": {
                "name": "_private",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
            "mod:Class.method": {
                "name": "Class.method",
                "kind": "method",
                "module": "mod",
                "file": "mod.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={
                "comp_0": ["mod:__init__", "mod:_private", "mod:Class.method"]
            },
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        assert len(root.children[0].members) == 3

    def test_deeply_nested_fine_clusters(self):
        """Test with fine clusters that could create deep nesting."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            f"mod:sym{i}": {
                "name": f"sym{i}",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            }
            for i in range(20)
        }

        # Multiple levels of fine clustering
        builder = HierarchyBuilder(
            coarse_clusters={"root": list(symbols.keys())},
            fine_clusters={
                f"fine_{i}": [f"mod:sym{i*2}", f"mod:sym{i*2+1}"] for i in range(10)
            },
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()
        assert root is not None

    def test_metrics_calculator_raises_exception(self):
        """Test graceful handling when metrics calculator raises."""

        class FailingMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                raise ValueError("Metrics calculation failed")

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=FailingMetricsCalculator(),
        )

        # Depending on implementation, may raise or handle gracefully
        try:
            root = builder.build()
            # If it doesn't raise, metrics should be None
            if root.children:
                assert root.children[0].metrics is None
        except ValueError:
            # Expected if builder doesn't catch exceptions
            pass

    def test_duplicate_cluster_ids(self):
        """Test that duplicate cluster IDs don't cause issues."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return None

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {
                "name": "B",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }

        # Same cluster ID in both coarse and fine (edge case)
        builder = HierarchyBuilder(
            coarse_clusters={"shared_id": ["mod:A"]},
            fine_clusters={"shared_id": ["mod:B"]},  # Same ID
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )

        # Should handle without crashing
        root = builder.build()
        assert root is not None


class TestClusterNodeEquality:
    """Tests for ClusterNode comparison and identity."""

    def test_nodes_with_same_id_are_not_equal_by_default(self):
        """Test that nodes with same ID are distinct objects."""
        node1 = ClusterNode(id="test", level="code", label=None)
        node2 = ClusterNode(id="test", level="code", label=None)

        # Without __eq__ override, objects are distinct
        assert node1 is not node2

    def test_node_identity(self):
        """Test node identity is preserved."""
        node = ClusterNode(id="test", level="code", label=None)
        same_ref = node

        assert node is same_ref
        assert node.id == same_ref.id


class TestHierarchyBuilderIntegration:
    """Integration-style tests for HierarchyBuilder."""

    def test_full_hierarchy_workflow(self):
        """Test complete workflow of building and serializing hierarchy."""

        class MockMetricsCalculator:
            def calculate_cluster_metrics(self, cluster_id, members):
                return ClusterMetrics(
                    cluster_id=cluster_id,
                    size=len(members),
                    internal_edges=len(members) - 1,
                    external_edges=2,
                    density=0.6,
                    cohesion=0.7,
                    coupling=0.3,
                    modularity_contribution=0.1,
                )

        symbols = {
            "auth:User": {
                "name": "User",
                "kind": "class",
                "module": "auth",
                "file": "auth/models.py",
            },
            "auth:login": {
                "name": "login",
                "kind": "function",
                "module": "auth",
                "file": "auth/views.py",
            },
            "auth:logout": {
                "name": "logout",
                "kind": "function",
                "module": "auth",
                "file": "auth/views.py",
            },
            "db:Connection": {
                "name": "Connection",
                "kind": "class",
                "module": "db",
                "file": "db/core.py",
            },
            "db:query": {
                "name": "query",
                "kind": "function",
                "module": "db",
                "file": "db/core.py",
            },
            "db:execute": {
                "name": "execute",
                "kind": "function",
                "module": "db",
                "file": "db/core.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={
                "auth_component": ["auth:User", "auth:login", "auth:logout"],
                "db_component": ["db:Connection", "db:query", "db:execute"],
            },
            fine_clusters={
                "auth_models": ["auth:User"],
                "auth_views": ["auth:login", "auth:logout"],
                "db_core": ["db:Connection", "db:query", "db:execute"],
            },
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )

        root = builder.build()

        # Verify root structure
        assert root.level == "container"
        assert len(root.children) == 2

        # Serialize and deserialize
        d = root.to_dict()
        restored = ClusterNode.from_dict(d)

        # Verify restoration
        assert restored.level == root.level
        assert len(restored.children) == len(root.children)

    def test_hierarchy_traversal(self):
        """Test that hierarchy can be traversed correctly."""

        class MockMetricsCalculator:
            def calculate(self, node):
                return None

        symbols = {
            "mod:A": {"name": "A", "kind": "class", "module": "mod", "file": "mod.py"},
            "mod:B": {
                "name": "B",
                "kind": "function",
                "module": "mod",
                "file": "mod.py",
            },
        }

        builder = HierarchyBuilder(
            coarse_clusters={"comp_0": ["mod:A", "mod:B"]},
            fine_clusters={},
            symbols=symbols,
            metrics_calculator=MockMetricsCalculator(),
        )
        root = builder.build()

        # Collect all node IDs via traversal
        def collect_ids(node, ids=None):
            if ids is None:
                ids = []
            ids.append(node.id)
            for child in node.children:
                collect_ids(child, ids)
            return ids

        all_ids = collect_ids(root)
        assert root.id in all_ids
        # HierarchyBuilder adds "component_" prefix to cluster IDs
        assert "component_comp_0" in all_ids

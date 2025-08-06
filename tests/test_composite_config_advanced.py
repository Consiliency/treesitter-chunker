"""Advanced tests for CompositeLanguageConfig."""

from chunker.languages.base import ChunkRule, CompositeLanguageConfig, LanguageConfig


class MockLanguageConfig(LanguageConfig):
    """Mock language configuration for testing."""

    def __init__(
        self,
        language_id: str,
        chunk_types: set[str],
        ignore_types: set[str] | None = None,
    ):
        self._language_id = language_id
        self._chunk_types = chunk_types
        self._ignore_types = ignore_types or set()
        self._chunk_rules = []
        self._validate_config()

    @property
    def language_id(self) -> str:
        return self._language_id

    @property
    def chunk_types(self) -> set[str]:
        return self._chunk_types


class MockCompositeConfig(CompositeLanguageConfig):
    """Mock composite configuration for testing."""

    def __init__(self, language_id: str, *parent_configs):
        self._language_id = language_id
        super().__init__(*parent_configs)

    @property
    def language_id(self) -> str:
        return self._language_id


class TestCompositeConfigAdvanced:
    """Test advanced features of CompositeLanguageConfig."""

    @classmethod
    def test_diamond_inheritance(cls):
        """Test diamond inheritance pattern resolution."""
        base = MockLanguageConfig(
            language_id="base",
            chunk_types={"base_function"},
            ignore_types={"base_ignore"},
        )
        base.add_chunk_rule(
            ChunkRule(
                node_types={"base_rule"},
                priority=5,
                metadata={"source": "base"},
            ),
        )
        left = MockCompositeConfig("left", base)
        left.add_chunk_type("left_function")
        left.add_ignore_type("left_ignore")
        left.add_chunk_rule(
            ChunkRule(
                node_types={"left_rule"},
                priority=10,
                metadata={"source": "left"},
            ),
        )
        right = MockCompositeConfig("right", base)
        right.add_chunk_type("right_function")
        right.add_ignore_type("right_ignore")
        right.add_chunk_rule(
            ChunkRule(
                node_types={"right_rule"},
                priority=8,
                metadata={"source": "right"},
            ),
        )
        diamond = MockCompositeConfig("diamond", left, right)
        diamond.add_chunk_type("diamond_function")
        expected_chunks = {
            "base_function",
            "left_function",
            "right_function",
            "diamond_function",
        }
        assert diamond.chunk_types == expected_chunks
        expected_ignores = {"base_ignore", "left_ignore", "right_ignore"}
        assert diamond.ignore_types == expected_ignores
        rules = diamond.chunk_rules
        assert len(rules) == 4
        assert rules[0].metadata["source"] == "left"
        assert rules[1].metadata["source"] == "right"
        assert rules[2].metadata["source"] == "base"
        assert rules[3].metadata["source"] == "base"

    @classmethod
    def test_circular_inheritance_protection(cls):
        """Test that circular inheritance is handled gracefully."""
        config_a = MockLanguageConfig("a", {"func_a"})
        config_b = MockCompositeConfig("b", config_a)
        config_b.add_chunk_type("func_b")
        config_c = MockCompositeConfig("c", config_b)
        config_c.add_chunk_type("func_c")
        assert "func_a" in config_c.chunk_types
        assert "func_b" in config_c.chunk_types
        assert "func_c" in config_c.chunk_types

    @classmethod
    def test_deep_inheritance_chains(cls):
        """Test performance and correctness with deep inheritance."""
        configs = []
        base = MockLanguageConfig("level_0", {"func_0"})
        base.add_chunk_rule(
            ChunkRule(node_types={"rule_0"}, priority=0, metadata={"level": 0}),
        )
        configs.append(base)
        for i in range(1, 20):
            parent = configs[i - 1]
            config = MockCompositeConfig(f"level_{i}", parent)
            config.add_chunk_type(f"func_{i}")
            config.add_ignore_type(f"ignore_{i}")
            config.add_chunk_rule(
                ChunkRule(node_types={f"rule_{i}"}, priority=i, metadata={"level": i}),
            )
            configs.append(config)
        deepest = configs[-1]
        assert len(deepest.chunk_types) == 20
        for i in range(20):
            assert f"func_{i}" in deepest.chunk_types
        assert len(deepest.ignore_types) == 19
        for i in range(1, 20):
            assert f"ignore_{i}" in deepest.ignore_types
        rules = deepest.chunk_rules
        assert len(rules) == 20
        for i in range(20):
            assert rules[i].metadata["level"] == 19 - i

    @classmethod
    def test_multiple_inheritance_order(cls):
        """Test that parent order matters in multiple inheritance."""
        config1 = MockLanguageConfig("config1", {"shared_func"})
        config1.add_chunk_rule(
            ChunkRule(
                node_types={"shared_rule"},
                priority=5,
                metadata={"from": "config1", "value": 1},
            ),
        )
        config2 = MockLanguageConfig("config2", {"shared_func"})
        config2.add_chunk_rule(
            ChunkRule(
                node_types={"shared_rule"},
                priority=5,
                metadata={"from": "config2", "value": 2},
            ),
        )
        child1 = MockCompositeConfig("child1", config1, config2)
        child2 = MockCompositeConfig("child2", config2, config1)
        assert child1.chunk_types == child2.chunk_types
        rules1 = child1.chunk_rules
        rules2 = child2.chunk_rules
        assert rules1[0].metadata["from"] == "config1"
        assert rules1[1].metadata["from"] == "config2"
        assert rules2[0].metadata["from"] == "config2"
        assert rules2[1].metadata["from"] == "config1"

    @classmethod
    def test_parent_modification_propagation(cls):
        """Test that parent modifications affect child (current behavior)."""
        parent = MockLanguageConfig("parent", {"parent_func"})
        child = MockCompositeConfig("child", parent)
        child.add_chunk_type("child_func")
        assert child.chunk_types == {"parent_func", "child_func"}
        parent._chunk_types.add("new_parent_func")
        parent.add_ignore_type("new_ignore")
        assert "new_parent_func" in child.chunk_types
        assert "new_ignore" in child.ignore_types
        assert "new_parent_func" in parent.chunk_types
        assert "new_ignore" in parent.ignore_types

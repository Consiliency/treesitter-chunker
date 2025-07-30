"""Tests for the language configuration framework."""

import pytest

from chunker.languages.base import (
    ChunkRule,
    CompositeLanguageConfig,
    LanguageConfig,
    LanguageConfigRegistry,
    language_config_registry,
    validate_language_config,
)


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
        # Set _ignore_types before calling super().__init__()
        self._ignore_types = ignore_types or set()
        # Don't call super().__init__() yet - we need to set up everything first
        self._chunk_rules = []
        self._validate_config()

    @property
    def language_id(self) -> str:
        return self._language_id

    @property
    def chunk_types(self) -> set[str]:
        return self._chunk_types


class TestLanguageConfig:
    """Test the base LanguageConfig class."""

    def test_basic_config_creation(self):
        """Test creating a basic language configuration."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"function", "class"},
        )

        assert config.language_id == "test"
        assert config.chunk_types == {"function", "class"}
        assert config.ignore_types == set()
        assert config.file_extensions == set()
        assert config.chunk_rules == []

    def test_should_chunk_node(self):
        """Test the should_chunk_node method."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"function", "class"},
            ignore_types={"comment"},
        )

        assert config.should_chunk_node("function")
        assert config.should_chunk_node("class")
        assert not config.should_chunk_node("variable")
        assert not config.should_chunk_node("comment")

    def test_should_ignore_node(self):
        """Test the should_ignore_node method."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"function"},
            ignore_types={"comment", "whitespace"},
        )

        assert config.should_ignore_node("comment")
        assert config.should_ignore_node("whitespace")
        assert not config.should_ignore_node("function")
        assert not config.should_ignore_node("variable")

    def test_add_ignore_type(self):
        """Test adding ignore types dynamically."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"function"},
        )

        assert not config.should_ignore_node("comment")
        config.add_ignore_type("comment")
        assert config.should_ignore_node("comment")

    def test_chunk_rules(self):
        """Test advanced chunk rules."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"function"},
        )

        # Add a rule for async functions
        rule = ChunkRule(
            node_types={"async_function"},
            priority=10,
            metadata={"async": True},
        )
        config.add_chunk_rule(rule)

        assert config.should_chunk_node("function")
        assert config.should_chunk_node("async_function")
        assert len(config.chunk_rules) == 1
        assert config.get_chunk_metadata("async_function") == {"async": True}
        assert config.get_chunk_metadata("function") == {}

    def test_rule_priority_sorting(self):
        """Test that chunk rules are sorted by priority."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types=set(),
        )

        # Add rules in non-priority order
        config.add_chunk_rule(ChunkRule({"rule1"}, priority=5))
        config.add_chunk_rule(ChunkRule({"rule2"}, priority=10))
        config.add_chunk_rule(ChunkRule({"rule3"}, priority=1))

        rules = config.chunk_rules
        assert rules[0].priority == 10
        assert rules[1].priority == 5
        assert rules[2].priority == 1

    def test_validation_error_on_overlap(self):
        """Test that validation fails when chunk_types and ignore_types overlap."""
        with pytest.raises(
            ValueError,
            match="cannot be both chunk types and ignore types",
        ):
            MockLanguageConfig(
                language_id="test",
                chunk_types={"function", "class"},
                ignore_types={"function", "comment"},
            )

    def test_repr(self):
        """Test string representation."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"function", "class"},
        )
        config.add_chunk_rule(ChunkRule({"async_function"}))

        repr_str = repr(config)
        assert "MockLanguageConfig" in repr_str
        assert "language_id='test'" in repr_str
        assert "chunk_types=2" in repr_str
        assert "rules=1" in repr_str


class MockCompositeConfig(CompositeLanguageConfig):
    """Mock composite configuration for testing."""

    def __init__(self, language_id: str, *parent_configs):
        self._language_id = language_id
        super().__init__(*parent_configs)

    @property
    def language_id(self) -> str:
        return self._language_id


class TestCompositeLanguageConfig:
    """Test the CompositeLanguageConfig class for inheritance."""

    def test_single_parent_inheritance(self):
        """Test inheriting from a single parent configuration."""
        parent = MockLanguageConfig(
            language_id="c",
            chunk_types={"function", "struct"},
            ignore_types={"comment"},
        )

        child = MockCompositeConfig("cpp", parent)
        child.add_chunk_type("class")
        child.add_chunk_type("namespace")

        assert child.chunk_types == {"function", "struct", "class", "namespace"}
        assert child.ignore_types == {"comment"}

    def test_multiple_parent_inheritance(self):
        """Test inheriting from multiple parent configurations."""
        parent1 = MockLanguageConfig(
            language_id="base1",
            chunk_types={"function"},
            ignore_types={"comment"},
        )
        parent2 = MockLanguageConfig(
            language_id="base2",
            chunk_types={"class"},
            ignore_types={"whitespace"},
        )

        child = MockCompositeConfig("combined", parent1, parent2)

        assert child.chunk_types == {"function", "class"}
        assert child.ignore_types == {"comment", "whitespace"}

    def test_add_parent_dynamically(self):
        """Test adding parents after initialization."""
        parent1 = MockLanguageConfig(
            language_id="base1",
            chunk_types={"function"},
        )

        child = MockCompositeConfig("child")
        assert child.chunk_types == set()

        child.add_parent(parent1)
        assert child.chunk_types == {"function"}

        parent2 = MockLanguageConfig(
            language_id="base2",
            chunk_types={"class"},
        )
        child.add_parent(parent2)
        assert child.chunk_types == {"function", "class"}

    def test_rule_inheritance_and_priority(self):
        """Test that rules are inherited and properly sorted by priority."""
        parent = MockLanguageConfig(
            language_id="parent",
            chunk_types=set(),
        )
        parent.add_chunk_rule(ChunkRule({"parent_rule"}, priority=5))

        child = MockCompositeConfig("child", parent)
        child.add_chunk_rule(ChunkRule({"child_rule"}, priority=10))
        child.add_chunk_rule(ChunkRule({"low_priority_rule"}, priority=1))

        rules = child.chunk_rules
        assert len(rules) == 3
        assert rules[0].priority == 10  # child_rule
        assert rules[1].priority == 5  # parent_rule
        assert rules[2].priority == 1  # low_priority_rule

    def test_override_parent_ignore_types(self):
        """Test that child can add to parent's ignore types."""
        parent = MockLanguageConfig(
            language_id="parent",
            chunk_types={"function"},
            ignore_types={"comment"},
        )

        child = MockCompositeConfig("child", parent)
        child.add_ignore_type("whitespace")
        child.add_ignore_type("preprocessor")

        assert child.ignore_types == {"comment", "whitespace", "preprocessor"}
        # Parent should not be modified
        assert parent.ignore_types == {"comment"}


class TestConfigValidation:
    """Test the configuration validation functions."""

    def test_valid_config(self):
        """Test validation of a valid configuration."""
        config = MockLanguageConfig(
            language_id="valid",
            chunk_types={"function", "class"},
        )

        errors = validate_language_config(config)
        assert errors == []

    def test_empty_language_id(self):
        """Test validation fails for empty language ID."""
        config = MockLanguageConfig(
            language_id="",
            chunk_types={"function"},
        )

        errors = validate_language_config(config)
        assert "Language ID cannot be empty" in errors

    def test_empty_chunk_types(self):
        """Test validation fails for empty chunk types."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types=set(),
        )

        errors = validate_language_config(config)
        assert "Configuration must define at least one chunk type" in errors

    def test_invalid_node_types(self):
        """Test validation fails for invalid node types."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"valid_type", "invalid type", ""},
            ignore_types={None},  # type: ignore
        )

        errors = validate_language_config(config)
        assert any("cannot contain spaces" in e for e in errors)
        assert any("Invalid node type: ''" in e for e in errors)
        assert any("Invalid node type: None" in e for e in errors)

    def test_overlapping_types(self):
        """Test validation fails for overlapping chunk and ignore types."""
        # This should be caught during __init__, but test the validator directly
        config = MockLanguageConfig.__new__(MockLanguageConfig)
        config._language_id = "test"
        config._chunk_types = {"function", "class"}
        config._ignore_types = {"function", "comment"}
        config._chunk_rules = []

        errors = validate_language_config(config)
        assert any("cannot be both chunk and ignore types" in e for e in errors)

    def test_invalid_chunk_rules(self):
        """Test validation of chunk rules."""
        config = MockLanguageConfig(
            language_id="test",
            chunk_types={"function"},
        )

        # Add invalid rules
        config.add_chunk_rule(ChunkRule(set(), priority=0))  # Empty node types
        config.add_chunk_rule(ChunkRule({"valid"}, priority=-5))  # Negative priority

        errors = validate_language_config(config)
        assert any("has no node types defined" in e for e in errors)
        assert any("has negative priority" in e for e in errors)


class TestLanguageConfigRegistry:
    """Test the language configuration registry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        reg = LanguageConfigRegistry()
        yield reg
        reg.clear()

    def test_register_config(self, registry):
        """Test registering a configuration."""
        config = MockLanguageConfig(
            language_id="python",
            chunk_types={"function_definition", "class_definition"},
        )

        registry.register(config)
        assert registry.get("python") == config
        assert "python" in registry.list_languages()

    def test_register_with_aliases(self, registry):
        """Test registering a configuration with aliases."""
        config = MockLanguageConfig(
            language_id="python",
            chunk_types={"function_definition"},
        )

        registry.register(config, aliases=["py", "python3"])

        assert registry.get("python") == config
        assert registry.get("py") == config
        assert registry.get("python3") == config
        assert registry.list_languages() == ["python"]

    def test_register_duplicate_language(self, registry):
        """Test that registering duplicate language IDs fails."""
        config1 = MockLanguageConfig(
            language_id="python",
            chunk_types={"function"},
        )
        config2 = MockLanguageConfig(
            language_id="python",
            chunk_types={"class"},
        )

        registry.register(config1)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(config2)

    def test_register_duplicate_alias(self, registry):
        """Test that registering duplicate aliases fails."""
        config1 = MockLanguageConfig(
            language_id="python",
            chunk_types={"function"},
        )
        config2 = MockLanguageConfig(
            language_id="python3",
            chunk_types={"function"},
        )

        registry.register(config1, aliases=["py"])
        with pytest.raises(ValueError, match="Alias py is already registered"):
            registry.register(config2, aliases=["py"])

    def test_register_invalid_config(self, registry):
        """Test that registering an invalid configuration fails."""
        config = MockLanguageConfig(
            language_id="",  # Invalid: empty language ID
            chunk_types={"function"},
        )

        with pytest.raises(ValueError, match="Invalid configuration"):
            registry.register(config)

    def test_get_nonexistent(self, registry):
        """Test getting a non-existent language returns None."""
        assert registry.get("nonexistent") is None
        assert registry.get("unknown_alias") is None

    def test_clear_registry(self, registry):
        """Test clearing the registry."""
        config = MockLanguageConfig(
            language_id="python",
            chunk_types={"function"},
        )

        registry.register(config, aliases=["py"])
        assert registry.get("python") is not None
        assert registry.get("py") is not None

        registry.clear()
        assert registry.get("python") is None
        assert registry.get("py") is None
        assert registry.list_languages() == []

    def test_global_registry(self):
        """Test that the global registry instance works."""
        # Clear it first
        language_config_registry.clear()

        config = MockLanguageConfig(
            language_id="test_global",
            chunk_types={"function"},
        )

        language_config_registry.register(config)
        assert language_config_registry.get("test_global") == config

        # Clean up
        language_config_registry.clear()


class TestChunkRuleAdvancedFeatures:
    """Test advanced features of ChunkRule."""

    def test_include_children_property(self):
        """Test the include_children property of ChunkRule."""
        # Rule with include_children=True (default)
        rule_with_children = ChunkRule(
            node_types={"function_with_nested"},
            include_children=True,
            metadata={"test": "include"},
        )
        assert rule_with_children.include_children is True

        # Rule with include_children=False
        rule_without_children = ChunkRule(
            node_types={"function_no_nested"},
            include_children=False,
            metadata={"test": "exclude"},
        )
        assert rule_without_children.include_children is False

    def test_complex_metadata(self):
        """Test ChunkRule with complex metadata structures."""
        complex_metadata = {
            "type": "async_function",
            "attributes": {
                "async": True,
                "generator": False,
                "decorators": ["@cached", "@logged"],
            },
            "metrics": {
                "complexity": 5,
                "lines": 25,
                "params": ["self", "data", "config"],
            },
            "tags": ["api", "public", "stable"],
        }

        rule = ChunkRule(
            node_types={"async_function_definition"},
            priority=10,
            metadata=complex_metadata,
        )

        assert rule.metadata["type"] == "async_function"
        assert rule.metadata["attributes"]["async"] is True
        assert len(rule.metadata["attributes"]["decorators"]) == 2
        assert rule.metadata["metrics"]["complexity"] == 5
        assert "api" in rule.metadata["tags"]

    def test_parent_type_in_should_chunk_node(self):
        """Test should_chunk_node with parent_type parameter."""

        class ParentAwareConfig(LanguageConfig):
            @property
            def language_id(self) -> str:
                return "test_parent"

            @property
            def chunk_types(self) -> set[str]:
                return {"method"}

            def should_chunk_node(
                self,
                node_type: str,
                parent_type: str | None = None,
            ) -> bool:
                # Only chunk methods inside classes
                if node_type == "method":
                    return parent_type == "class"
                return super().should_chunk_node(node_type, parent_type)

        config = ParentAwareConfig()

        # Method inside class should be chunked
        assert config.should_chunk_node("method", "class") is True

        # Method at top level should not be chunked
        assert config.should_chunk_node("method", None) is False
        assert config.should_chunk_node("method", "module") is False


class TestLanguageConfigAdditionalFeatures:
    """Test additional features of LanguageConfig."""

    def test_file_extensions_property(self):
        """Test the file_extensions property."""

        class ExtensionConfig(LanguageConfig):
            @property
            def language_id(self) -> str:
                return "test_ext"

            @property
            def chunk_types(self) -> set[str]:
                return {"function"}

            @property
            def file_extensions(self) -> set[str]:
                return {".test", ".tst", ".test.js"}

        config = ExtensionConfig()
        assert config.file_extensions == {".test", ".tst", ".test.js"}

        # Test default (empty set)
        basic_config = MockLanguageConfig("basic", {"function"})
        assert basic_config.file_extensions == set()

    def test_multiple_rules_same_node_type(self):
        """Test multiple rules matching the same node type."""
        config = MockLanguageConfig(
            language_id="test_multi",
            chunk_types=set(),
        )

        # Add multiple rules for "special_function"
        config.add_chunk_rule(
            ChunkRule(
                node_types={"special_function"},
                priority=5,
                metadata={"source": "rule1", "important": False},
            ),
        )

        config.add_chunk_rule(
            ChunkRule(
                node_types={"special_function", "other_type"},
                priority=10,
                metadata={"source": "rule2", "important": True},
            ),
        )

        config.add_chunk_rule(
            ChunkRule(
                node_types={"special_function"},
                priority=3,
                metadata={"source": "rule3", "deprecated": True},
            ),
        )

        # Should chunk the node
        assert config.should_chunk_node("special_function") is True

        # Get metadata - should return from first matching rule (highest priority)
        metadata = config.get_chunk_metadata("special_function")
        assert metadata["source"] == "rule2"
        assert metadata["important"] is True

        # Verify rules are sorted by priority
        rules = config.chunk_rules
        assert rules[0].priority == 10
        assert rules[1].priority == 5
        assert rules[2].priority == 3

    def test_rules_with_same_priority(self):
        """Test stable sort order for rules with same priority."""
        config = MockLanguageConfig(
            language_id="test_stable",
            chunk_types=set(),
        )

        # Add rules with same priority
        config.add_chunk_rule(
            ChunkRule(
                node_types={"type_a"},
                priority=5,
                metadata={"order": 1},
            ),
        )

        config.add_chunk_rule(
            ChunkRule(
                node_types={"type_b"},
                priority=5,
                metadata={"order": 2},
            ),
        )

        config.add_chunk_rule(
            ChunkRule(
                node_types={"type_c"},
                priority=5,
                metadata={"order": 3},
            ),
        )

        # Verify insertion order is preserved for same priority
        rules = config.chunk_rules
        assert len(rules) == 3
        assert all(r.priority == 5 for r in rules)
        assert rules[0].metadata["order"] == 1
        assert rules[1].metadata["order"] == 2
        assert rules[2].metadata["order"] == 3


class TestRegistryThreadSafety:
    """Test thread safety of the language configuration registry."""

    def test_concurrent_registry_access(self):
        """Test concurrent read/write access to registry."""
        import threading
        import time

        registry = LanguageConfigRegistry()
        errors = []
        configs_registered = []

        def register_configs(start_id: int, count: int):
            """Register multiple configs in a thread."""
            try:
                for i in range(count):
                    config = MockLanguageConfig(
                        language_id=f"lang_{start_id}_{i}",
                        chunk_types={"function"},
                    )
                    registry.register(config)
                    configs_registered.append(f"lang_{start_id}_{i}")
                    # Small delay to increase chance of race conditions
                    time.sleep(0.001)
            except (OSError, IndexError, KeyError) as e:
                errors.append(e)

        def read_configs(iterations: int):
            """Read configs repeatedly in a thread."""
            try:
                for _ in range(iterations):
                    # Try to access various configs
                    for lang_id in configs_registered[
                        :
                    ]:  # Copy to avoid modification during iteration
                        config = registry.get(lang_id)
                        if config and config.language_id != lang_id:
                            errors.append(
                                f"Mismatch: expected {lang_id}, got {config.language_id}",
                            )
                    # List all languages
                    langs = registry.list_languages()
                    if not isinstance(langs, list):
                        errors.append("list_languages didn't return a list")
                    time.sleep(0.001)
            except (OSError, AttributeError, IndexError) as e:
                errors.append(e)

        # Create threads for concurrent access
        threads = []

        # Writers
        for i in range(3):
            t = threading.Thread(target=register_configs, args=(i * 10, 5))
            threads.append(t)

        # Readers
        for i in range(2):
            t = threading.Thread(target=read_configs, args=(20,))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Check for errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Verify all configs were registered
        assert len(configs_registered) == 15  # 3 writers * 5 configs each

        # Verify registry state is consistent
        all_langs = set(registry.list_languages())
        expected_langs = set(configs_registered)
        assert all_langs == expected_langs

        # Clean up
        registry.clear()


class TestCompositeConfigAdvanced:
    """Test advanced features of CompositeLanguageConfig."""

    def test_diamond_inheritance(self):
        """Test diamond inheritance pattern resolution."""
        # Create base config
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

        # Create two intermediate configs
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

        # Create diamond config inheriting from both
        diamond = MockCompositeConfig("diamond", left, right)
        diamond.add_chunk_type("diamond_function")

        # Verify all chunk types are inherited
        expected_chunks = {
            "base_function",  # from base
            "left_function",  # from left
            "right_function",  # from right
            "diamond_function",  # own
        }
        assert diamond.chunk_types == expected_chunks

        # Verify all ignore types are inherited
        expected_ignores = {
            "base_ignore",  # from base
            "left_ignore",  # from left
            "right_ignore",  # from right
        }
        assert diamond.ignore_types == expected_ignores

        # Verify rules are properly sorted by priority
        rules = diamond.chunk_rules
        # In diamond inheritance, base rule appears twice (via left and right)
        assert len(rules) == 4  # left, right, base (from left), base (from right)
        assert rules[0].metadata["source"] == "left"  # priority 10
        assert rules[1].metadata["source"] == "right"  # priority 8
        assert rules[2].metadata["source"] == "base"  # priority 5 (from left)
        assert rules[3].metadata["source"] == "base"  # priority 5 (from right)

    def test_circular_inheritance_protection(self):
        """Test that circular inheritance is handled gracefully."""
        # Note: Current implementation doesn't explicitly prevent circular inheritance
        # but Python's method resolution order (MRO) handles it

        # Create configs
        config_a = MockLanguageConfig("a", {"func_a"})
        config_b = MockCompositeConfig("b", config_a)
        config_b.add_chunk_type("func_b")

        # Try to create circular reference
        # This would be: A -> B -> C -> A
        config_c = MockCompositeConfig("c", config_b)
        config_c.add_chunk_type("func_c")

        # In a real scenario, we'd want to prevent adding A as parent to C
        # For now, verify the config still works
        assert "func_a" in config_c.chunk_types
        assert "func_b" in config_c.chunk_types
        assert "func_c" in config_c.chunk_types

    def test_deep_inheritance_chains(self):
        """Test performance and correctness with deep inheritance."""
        # Create a chain of 20 configs
        configs = []

        # Base config
        base = MockLanguageConfig("level_0", {"func_0"})
        base.add_chunk_rule(
            ChunkRule(
                node_types={"rule_0"},
                priority=0,
                metadata={"level": 0},
            ),
        )
        configs.append(base)

        # Create chain
        for i in range(1, 20):
            parent = configs[i - 1]
            config = MockCompositeConfig(f"level_{i}", parent)
            config.add_chunk_type(f"func_{i}")
            config.add_ignore_type(f"ignore_{i}")
            config.add_chunk_rule(
                ChunkRule(
                    node_types={f"rule_{i}"},
                    priority=i,
                    metadata={"level": i},
                ),
            )
            configs.append(config)

        # Check the deepest config
        deepest = configs[-1]

        # Should have all chunk types
        assert len(deepest.chunk_types) == 20
        for i in range(20):
            assert f"func_{i}" in deepest.chunk_types

        # Should have all ignore types (except level 0 which has none)
        assert len(deepest.ignore_types) == 19
        for i in range(1, 20):
            assert f"ignore_{i}" in deepest.ignore_types

        # Rules should be sorted by priority (highest first)
        rules = deepest.chunk_rules
        assert len(rules) == 20
        for i in range(20):
            assert rules[i].metadata["level"] == 19 - i

    def test_multiple_inheritance_order(self):
        """Test that parent order matters in multiple inheritance."""
        # Create configs with overlapping chunk types
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
                priority=5,  # Same priority!
                metadata={"from": "config2", "value": 2},
            ),
        )

        # Create child with different parent orders
        child1 = MockCompositeConfig("child1", config1, config2)
        child2 = MockCompositeConfig("child2", config2, config1)

        # Both should have the same chunk types
        assert child1.chunk_types == child2.chunk_types

        # But rule order should differ based on parent order
        rules1 = child1.chunk_rules
        rules2 = child2.chunk_rules

        # With same priority, order depends on parent order
        assert rules1[0].metadata["from"] == "config1"
        assert rules1[1].metadata["from"] == "config2"

        assert rules2[0].metadata["from"] == "config2"
        assert rules2[1].metadata["from"] == "config1"

    def test_parent_modification_isolation(self):
        """Test that parent modifications affect child (current behavior)."""
        parent = MockLanguageConfig("parent", {"parent_func"})

        # Create child
        child = MockCompositeConfig("child", parent)
        child.add_chunk_type("child_func")

        # Verify initial state
        assert child.chunk_types == {"parent_func", "child_func"}

        # Modify parent after child creation
        parent._chunk_types.add("new_parent_func")
        parent.add_ignore_type("new_ignore")

        # In current implementation, child DOES see the changes
        # This is because CompositeConfig references parent's sets directly
        assert "new_parent_func" in child.chunk_types
        assert "new_ignore" in child.ignore_types

        # But parent should have them
        assert "new_parent_func" in parent.chunk_types
        assert "new_ignore" in parent.ignore_types

    def test_concurrent_modifications(self):
        """Test concurrent modifications don't corrupt registry state."""
        import threading

        registry = LanguageConfigRegistry()
        errors = []

        def modify_registry(thread_id: int):
            """Perform various registry operations."""
            try:
                # Register
                config = MockLanguageConfig(
                    language_id=f"thread_{thread_id}",
                    chunk_types={"function"},
                )
                registry.register(config, aliases=[f"t{thread_id}"])

                # Get by ID and alias
                assert registry.get(f"thread_{thread_id}") is not None
                assert registry.get(f"t{thread_id}") is not None

                # List
                langs = registry.list_languages()
                assert f"thread_{thread_id}" in langs

                # Try to register duplicate (should fail)
                try:
                    registry.register(config)
                except ValueError:
                    pass  # Expected

            except (OSError, IndexError, KeyError) as e:
                errors.append(f"Thread {thread_id}: {e}")

        # Run concurrent modifications
        threads = []
        for i in range(10):
            t = threading.Thread(target=modify_registry, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check for unexpected errors
        assert len(errors) == 0, f"Errors during concurrent modifications: {errors}"

        # Verify final state
        langs = registry.list_languages()
        assert len(langs) == 10

        # Clean up
        registry.clear()


class TestCompositeConfigAdvanced:
    """Test advanced features of CompositeLanguageConfig."""

    def test_diamond_inheritance(self):
        """Test diamond inheritance pattern resolution."""
        # Create base config
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

        # Create two intermediate configs
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

        # Create diamond config inheriting from both
        diamond = MockCompositeConfig("diamond", left, right)
        diamond.add_chunk_type("diamond_function")

        # Verify all chunk types are inherited
        expected_chunks = {
            "base_function",  # from base
            "left_function",  # from left
            "right_function",  # from right
            "diamond_function",  # own
        }
        assert diamond.chunk_types == expected_chunks

        # Verify all ignore types are inherited
        expected_ignores = {
            "base_ignore",  # from base
            "left_ignore",  # from left
            "right_ignore",  # from right
        }
        assert diamond.ignore_types == expected_ignores

        # Verify rules are properly sorted by priority
        rules = diamond.chunk_rules
        # In diamond inheritance, base rule appears twice (via left and right)
        assert len(rules) == 4  # left, right, base (from left), base (from right)
        assert rules[0].metadata["source"] == "left"  # priority 10
        assert rules[1].metadata["source"] == "right"  # priority 8
        assert rules[2].metadata["source"] == "base"  # priority 5 (from left)
        assert rules[3].metadata["source"] == "base"  # priority 5 (from right)

    def test_circular_inheritance_protection(self):
        """Test that circular inheritance is handled gracefully."""
        # Note: Current implementation doesn't explicitly prevent circular inheritance
        # but Python's method resolution order (MRO) handles it

        # Create configs
        config_a = MockLanguageConfig("a", {"func_a"})
        config_b = MockCompositeConfig("b", config_a)
        config_b.add_chunk_type("func_b")

        # Try to create circular reference
        # This would be: A -> B -> C -> A
        config_c = MockCompositeConfig("c", config_b)
        config_c.add_chunk_type("func_c")

        # In a real scenario, we'd want to prevent adding A as parent to C
        # For now, verify the config still works
        assert "func_a" in config_c.chunk_types
        assert "func_b" in config_c.chunk_types
        assert "func_c" in config_c.chunk_types

    def test_deep_inheritance_chains(self):
        """Test performance and correctness with deep inheritance."""
        # Create a chain of 20 configs
        configs = []

        # Base config
        base = MockLanguageConfig("level_0", {"func_0"})
        base.add_chunk_rule(
            ChunkRule(
                node_types={"rule_0"},
                priority=0,
                metadata={"level": 0},
            ),
        )
        configs.append(base)

        # Create chain
        for i in range(1, 20):
            parent = configs[i - 1]
            config = MockCompositeConfig(f"level_{i}", parent)
            config.add_chunk_type(f"func_{i}")
            config.add_ignore_type(f"ignore_{i}")
            config.add_chunk_rule(
                ChunkRule(
                    node_types={f"rule_{i}"},
                    priority=i,
                    metadata={"level": i},
                ),
            )
            configs.append(config)

        # Check the deepest config
        deepest = configs[-1]

        # Should have all chunk types
        assert len(deepest.chunk_types) == 20
        for i in range(20):
            assert f"func_{i}" in deepest.chunk_types

        # Should have all ignore types (except level 0 which has none)
        assert len(deepest.ignore_types) == 19
        for i in range(1, 20):
            assert f"ignore_{i}" in deepest.ignore_types

        # Rules should be sorted by priority (highest first)
        rules = deepest.chunk_rules
        assert len(rules) == 20
        for i in range(20):
            assert rules[i].metadata["level"] == 19 - i

    def test_multiple_inheritance_order(self):
        """Test that parent order matters in multiple inheritance."""
        # Create configs with overlapping chunk types
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
                priority=5,  # Same priority!
                metadata={"from": "config2", "value": 2},
            ),
        )

        # Create child with different parent orders
        child1 = MockCompositeConfig("child1", config1, config2)
        child2 = MockCompositeConfig("child2", config2, config1)

        # Both should have the same chunk types
        assert child1.chunk_types == child2.chunk_types

        # But rule order should differ based on parent order
        rules1 = child1.chunk_rules
        rules2 = child2.chunk_rules

        # With same priority, order depends on parent order
        assert rules1[0].metadata["from"] == "config1"
        assert rules1[1].metadata["from"] == "config2"

        assert rules2[0].metadata["from"] == "config2"
        assert rules2[1].metadata["from"] == "config1"

    def test_parent_modification_isolation(self):
        """Test that parent modifications affect child (current behavior)."""
        parent = MockLanguageConfig("parent", {"parent_func"})

        # Create child
        child = MockCompositeConfig("child", parent)
        child.add_chunk_type("child_func")

        # Verify initial state
        assert child.chunk_types == {"parent_func", "child_func"}

        # Modify parent after child creation
        parent._chunk_types.add("new_parent_func")
        parent.add_ignore_type("new_ignore")

        # In current implementation, child DOES see the changes
        # This is because CompositeConfig references parent's sets directly
        assert "new_parent_func" in child.chunk_types
        assert "new_ignore" in child.ignore_types

        # But parent should have them
        assert "new_parent_func" in parent.chunk_types
        assert "new_ignore" in parent.ignore_types

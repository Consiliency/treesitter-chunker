"""Unit tests for chunker.clustering.weights module."""

from chunker.clustering.weights import EdgeWeightCalculator, EdgeWeightConfig


class TestEdgeWeightConfig:
    """Tests for EdgeWeightConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = EdgeWeightConfig()
        assert config.import_weight == 1.0
        assert config.call_weight == 0.7
        assert config.inherit_weight == 0.8
        assert config.type_ref_weight == 0.5
        assert config.same_file_bonus == 0.3

    def test_custom_values(self):
        """Test custom configuration values."""
        config = EdgeWeightConfig(
            import_weight=2.0,
            call_weight=1.0,
            inherit_weight=1.5,
            type_ref_weight=0.3,
            same_file_bonus=0.5,
        )
        assert config.import_weight == 2.0
        assert config.call_weight == 1.0

    def test_partial_custom_values(self):
        """Test that unspecified values use defaults."""
        config = EdgeWeightConfig(import_weight=2.5)
        assert config.import_weight == 2.5
        assert config.call_weight == 0.7  # default
        assert config.inherit_weight == 0.8  # default
        assert config.type_ref_weight == 0.5  # default
        assert config.same_file_bonus == 0.3  # default

    def test_zero_values(self):
        """Test configuration with zero values."""
        config = EdgeWeightConfig(
            import_weight=0.0,
            call_weight=0.0,
            same_file_bonus=0.0,
        )
        assert config.import_weight == 0.0
        assert config.call_weight == 0.0
        assert config.same_file_bonus == 0.0

    def test_negative_values(self):
        """Test that negative values are accepted (validation should happen elsewhere)."""
        config = EdgeWeightConfig(import_weight=-1.0)
        assert config.import_weight == -1.0


class TestEdgeWeightCalculator:
    """Tests for EdgeWeightCalculator class."""

    def test_default_config(self):
        """Test calculator with default config."""
        calc = EdgeWeightCalculator()
        assert calc.config is not None
        assert calc.config.import_weight == 1.0

    def test_custom_config(self):
        """Test calculator with custom config."""
        config = EdgeWeightConfig(import_weight=2.0)
        calc = EdgeWeightCalculator(config)
        assert calc.config.import_weight == 2.0

    def test_import_weight(self):
        """Test weight calculation for imports."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "imports"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 1.0

    def test_call_weight(self):
        """Test weight calculation for calls."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.7

    def test_inherit_weight(self):
        """Test weight calculation for inheritance."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "inherits"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.8

    def test_type_ref_weight(self):
        """Test weight calculation for type references."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "type_ref"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.5

    def test_same_file_bonus(self):
        """Test that same-file relationships get a bonus."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 1.0  # 0.7 + 0.3 bonus

    def test_same_file_bonus_with_imports(self):
        """Test same-file bonus with import relationships."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "imports"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 1.3  # 1.0 + 0.3 bonus

    def test_same_file_bonus_with_inheritance(self):
        """Test same-file bonus with inheritance relationships."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "inherits"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 1.1  # 0.8 + 0.3 bonus

    def test_unknown_relationship_type(self):
        """Test weight for unknown relationship type."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "unknown"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.0

    def test_unknown_type_with_same_file(self):
        """Test that unknown type with same file returns 0.0 (no bonus applied)."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "unknown"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        # Unknown type gives 0.0, and same file bonus is not applied when base weight is 0
        assert weight == 0.0

    def test_empty_relationship(self):
        """Test handling of empty/None inputs."""
        calc = EdgeWeightCalculator()
        assert calc.calculate_weight({}, {}, {}) == 0.0
        assert calc.calculate_weight(None, None, None) == 0.0

    def test_missing_type_field(self):
        """Test handling when relationship has no type field."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.0

    def test_missing_file_field(self):
        """Test handling when symbols have no file field."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"name": "A", "module": "mod"}
        to_sym = {"name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.7  # Base call weight, no file bonus

    def test_custom_config_affects_weights(self):
        """Test that custom config values are used in calculations."""
        config = EdgeWeightConfig(
            import_weight=5.0,
            call_weight=3.0,
            same_file_bonus=1.0,
        )
        calc = EdgeWeightCalculator(config)
        rel = {"from": "mod:A", "to": "mod:B", "type": "imports"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 5.0

    def test_custom_config_same_file_bonus(self):
        """Test custom same-file bonus in calculations."""
        config = EdgeWeightConfig(call_weight=1.0, same_file_bonus=2.0)
        calc = EdgeWeightCalculator(config)
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 3.0  # 1.0 + 2.0 bonus

    def test_different_file_paths_no_bonus(self):
        """Test that different file paths don't get same-file bonus."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "/path/to/a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "/path/to/b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.7  # No same-file bonus

    def test_same_absolute_file_paths_bonus(self):
        """Test that same absolute file paths get the bonus."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "/path/to/same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "/path/to/same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 1.0  # 0.7 + 0.3 bonus

    def test_relationship_with_extra_fields(self):
        """Test that extra fields in relationship don't affect calculation."""
        calc = EdgeWeightCalculator()
        rel = {
            "from": "mod:A",
            "to": "mod:B",
            "type": "calls",
            "extra": "data",
            "line": 42,
        }
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.7

    def test_symbol_with_extra_fields(self):
        """Test that extra fields in symbols don't affect calculation."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {
            "file": "a.py",
            "name": "A",
            "module": "mod",
            "line": 10,
            "kind": "function",
        }
        to_sym = {
            "file": "b.py",
            "name": "B",
            "module": "mod",
            "line": 20,
            "kind": "class",
        }

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.7


class TestEdgeWeightCalculatorEdgeCases:
    """Edge case tests for EdgeWeightCalculator."""

    def test_none_relationship_none_symbols(self):
        """Test with all None inputs."""
        calc = EdgeWeightCalculator()
        weight = calc.calculate_weight(None, None, None)
        assert weight == 0.0

    def test_none_from_symbol(self):
        """Test with None from_sym."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, None, to_sym)
        assert weight == 0.0  # Returns 0.0 when from_symbol is None

    def test_none_to_symbol(self):
        """Test with None to_sym."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, None)
        assert weight == 0.0  # Returns 0.0 when to_symbol is None

    def test_empty_string_file_paths(self):
        """Test with empty string file paths."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "", "name": "A", "module": "mod"}
        to_sym = {"file": "", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        # Empty strings are falsy, so no same-file bonus is applied
        assert weight == 0.7

    def test_case_sensitive_relationship_type(self):
        """Test that relationship type matching is case-sensitive."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "IMPORTS"}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.0  # "IMPORTS" != "imports"

    def test_whitespace_in_relationship_type(self):
        """Test relationship type with whitespace."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": " imports "}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        # Whitespace isn't stripped, so it won't match
        assert weight == 0.0

    def test_file_path_with_different_separators(self):
        """Test file paths with different path separators."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "path/to/file.py", "name": "A", "module": "mod"}
        to_sym = {"file": "path\\to\\file.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        # Different separators mean different strings
        assert weight == 0.7  # No same-file bonus

    def test_zero_weight_config(self):
        """Test with all weights set to zero."""
        config = EdgeWeightConfig(
            import_weight=0.0,
            call_weight=0.0,
            inherit_weight=0.0,
            type_ref_weight=0.0,
            same_file_bonus=0.0,
        )
        calc = EdgeWeightCalculator(config)
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.0

    def test_very_large_weight_values(self):
        """Test with very large weight values."""
        config = EdgeWeightConfig(
            import_weight=1e10,
            same_file_bonus=1e10,
        )
        calc = EdgeWeightCalculator(config)
        rel = {"from": "mod:A", "to": "mod:B", "type": "imports"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 2e10  # Both very large values added

    def test_float_precision(self):
        """Test floating point precision in weight calculations."""
        config = EdgeWeightConfig(
            call_weight=0.1,
            same_file_bonus=0.2,
        )
        calc = EdgeWeightCalculator(config)
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": "same.py", "name": "A", "module": "mod"}
        to_sym = {"file": "same.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        # 0.1 + 0.2 might have floating point issues
        assert abs(weight - 0.3) < 1e-10

    def test_relationship_type_none(self):
        """Test when relationship type is explicitly None."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": None}
        from_sym = {"file": "a.py", "name": "A", "module": "mod"}
        to_sym = {"file": "b.py", "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        assert weight == 0.0

    def test_file_field_none(self):
        """Test when file field is explicitly None."""
        calc = EdgeWeightCalculator()
        rel = {"from": "mod:A", "to": "mod:B", "type": "calls"}
        from_sym = {"file": None, "name": "A", "module": "mod"}
        to_sym = {"file": None, "name": "B", "module": "mod"}

        weight = calc.calculate_weight(rel, from_sym, to_sym)
        # Both None files - behavior depends on implementation
        # Could be treated as same (both None) or different
        assert weight >= 0.7  # At least base weight

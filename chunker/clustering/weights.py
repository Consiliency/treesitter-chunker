"""Edge weight configuration and calculation for clustering.

This module provides configuration and calculation utilities for determining
edge weights in the symbol relationship graph used for clustering.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class EdgeWeightConfig:
    """Configuration for edge weights in the symbol relationship graph.

    Attributes:
        import_weight: Weight for import relationships between symbols.
        call_weight: Weight for function/method call relationships.
        inherit_weight: Weight for class inheritance relationships.
        type_ref_weight: Weight for type reference relationships.
        same_file_bonus: Bonus weight added when symbols are in the same file.
    """

    import_weight: float = 1.0
    call_weight: float = 0.7
    inherit_weight: float = 0.8
    type_ref_weight: float = 0.5
    same_file_bonus: float = 0.3


class EdgeWeightCalculator:
    """Calculates edge weights for symbol relationships.

    This class computes weights for edges in the symbol relationship graph
    based on the type of relationship and locality of the symbols involved.

    Attributes:
        config: The edge weight configuration to use for calculations.
    """

    def __init__(self, config: Optional[EdgeWeightConfig] = None) -> None:
        """Initialize the edge weight calculator.

        Args:
            config: Optional edge weight configuration. If not provided,
                default configuration values will be used.
        """
        self.config = config if config is not None else EdgeWeightConfig()

    def calculate_weight(
        self,
        relationship: Dict[str, Any],
        from_symbol: Dict[str, Any],
        to_symbol: Dict[str, Any]
    ) -> float:
        """Calculate the weight for a relationship between two symbols.

        Args:
            relationship: Dictionary describing the relationship with keys:
                - "from": The source symbol identifier
                - "to": The target symbol identifier
                - "type": The relationship type ("imports", "calls", "inherits")
            from_symbol: Dictionary describing the source symbol with keys:
                - "file": The file path containing the symbol
                - "name": The symbol name
                - "kind": The symbol kind (e.g., "function", "class")
                - "module": The module containing the symbol
            to_symbol: Dictionary describing the target symbol with the same
                keys as from_symbol.

        Returns:
            The calculated edge weight as a float. Returns 0.0 if the
            relationship type is unknown or if required data is missing.
        """
        if not relationship or not from_symbol or not to_symbol:
            return 0.0

        rel_type = relationship.get("type", "")
        base_weight = self._base_weight_for_kind(rel_type)

        if base_weight == 0.0:
            return 0.0

        return self._apply_locality_bonus(base_weight, from_symbol, to_symbol)

    def _base_weight_for_kind(self, kind: str) -> float:
        """Get the base weight for a relationship kind.

        Args:
            kind: The relationship type string. Supported values are:
                - "imports": Import relationships
                - "calls": Function/method call relationships
                - "inherits": Class inheritance relationships
                - "type_ref": Type reference relationships

        Returns:
            The base weight for the given relationship kind, or 0.0 if
            the kind is not recognized.
        """
        weight_mapping = {
            "imports": self.config.import_weight,
            "calls": self.config.call_weight,
            "inherits": self.config.inherit_weight,
            "type_ref": self.config.type_ref_weight,
        }
        return weight_mapping.get(kind, 0.0)

    def _apply_locality_bonus(
        self,
        base_weight: float,
        from_symbol: Dict[str, Any],
        to_symbol: Dict[str, Any]
    ) -> float:
        """Apply locality bonus if symbols are in the same file.

        Args:
            base_weight: The base weight before applying any bonuses.
            from_symbol: Dictionary describing the source symbol.
            to_symbol: Dictionary describing the target symbol.

        Returns:
            The weight with locality bonus applied if both symbols are
            in the same file, otherwise the base weight unchanged.
        """
        from_file = from_symbol.get("file")
        to_file = to_symbol.get("file")

        if from_file and to_file and from_file == to_file:
            return base_weight + self.config.same_file_bonus

        return base_weight

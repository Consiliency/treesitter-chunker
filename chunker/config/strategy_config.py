"""Configuration management for chunking strategies."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StrategyConfig:
    """Configuration for a chunking strategy."""

    # Common parameters
    min_chunk_size: int = 10
    max_chunk_size: int = 200

    # Semantic strategy parameters
    semantic: dict[str, Any] = field(
        default_factory=lambda: {
            "complexity_threshold": 15.0,
            "coupling_threshold": 10.0,
            "cohesion_threshold": 0.7,
            "merge_related": True,
            "split_complex": True,
        },
    )

    # Hierarchical strategy parameters
    hierarchical: dict[str, Any] = field(
        default_factory=lambda: {
            "max_depth": 5,
            "granularity": "balanced",  # 'fine', 'balanced', 'coarse'
            "preserve_leaf_nodes": True,
            "include_intermediate": True,
        },
    )

    # Adaptive strategy parameters
    adaptive: dict[str, Any] = field(
        default_factory=lambda: {
            "base_chunk_size": 50,
            "complexity_factor": 0.5,
            "cohesion_factor": 0.3,
            "density_factor": 0.2,
            "high_complexity_threshold": 15.0,
            "low_complexity_threshold": 5.0,
            "high_cohesion_threshold": 0.8,
            "low_cohesion_threshold": 0.4,
            "preserve_boundaries": True,
            "balance_sizes": True,
            "adaptive_aggressiveness": 0.7,
        },
    )

    # Composite strategy parameters
    composite: dict[str, Any] = field(
        default_factory=lambda: {
            "strategy_weights": {
                "semantic": 1.0,
                "hierarchical": 0.8,
                "adaptive": 0.9,
            },
            "fusion_method": "consensus",  # 'union', 'intersection', 'consensus', 'weighted'
            "min_consensus_strategies": 2,
            "consensus_threshold": 0.6,
            "merge_overlaps": True,
            "overlap_threshold": 0.7,
            "apply_filters": True,
            "min_chunk_quality": 0.5,
        },
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyConfig":
        """Create from dictionary."""
        return cls(**data)

    def get_strategy_config(self, strategy_name: str) -> dict[str, Any]:
        """Get configuration for a specific strategy."""
        if strategy_name == "semantic":
            config = self.semantic.copy()
        elif strategy_name == "hierarchical":
            config = self.hierarchical.copy()
        elif strategy_name == "adaptive":
            config = self.adaptive.copy()
        elif strategy_name == "composite":
            config = self.composite.copy()
        else:
            config = {}

        # Add common parameters
        config["min_chunk_size"] = self.min_chunk_size
        config["max_chunk_size"] = self.max_chunk_size

        return config

    def update_strategy_config(self, strategy_name: str, updates: dict[str, Any]):
        """Update configuration for a specific strategy."""
        if strategy_name == "semantic":
            self.semantic.update(updates)
        elif strategy_name == "hierarchical":
            self.hierarchical.update(updates)
        elif strategy_name == "adaptive":
            self.adaptive.update(updates)
        elif strategy_name == "composite":
            self.composite.update(updates)

        # Update common parameters if provided
        if "min_chunk_size" in updates:
            self.min_chunk_size = updates["min_chunk_size"]
        if "max_chunk_size" in updates:
            self.max_chunk_size = updates["max_chunk_size"]


def load_strategy_config(path: str | Path) -> StrategyConfig:
    """Load strategy configuration from file."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    # Determine format from extension
    if path.suffix == ".json":
        with Path(path).open("r") as f:
            data = json.load(f)
    elif path.suffix in [".yaml", ".yml"]:
        with Path(path).open("r") as f:
            data = yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported configuration format: {path.suffix}")

    return StrategyConfig.from_dict(data)


def save_strategy_config(config: StrategyConfig, path: str | Path):
    """Save strategy configuration to file."""
    path = Path(path)

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Determine format from extension
    if path.suffix == ".json":
        with Path(path).open("w") as f:
            json.dump(config.to_dict(), f, indent=2)
    elif path.suffix in [".yaml", ".yml"]:
        with Path(path).open("w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False)
    else:
        raise ValueError(f"Unsupported configuration format: {path.suffix}")


# Default configurations for common use cases
DEFAULT_CONFIGS = {
    "default": StrategyConfig(),
    "fine_grained": StrategyConfig(
        min_chunk_size=5,
        max_chunk_size=50,
        semantic={"merge_related": False, "split_complex": True},
        hierarchical={"granularity": "fine"},
        adaptive={"base_chunk_size": 25, "adaptive_aggressiveness": 0.9},
    ),
    "coarse_grained": StrategyConfig(
        min_chunk_size=50,
        max_chunk_size=500,
        semantic={"merge_related": True, "split_complex": False},
        hierarchical={"granularity": "coarse"},
        adaptive={"base_chunk_size": 100, "adaptive_aggressiveness": 0.3},
    ),
    "complexity_aware": StrategyConfig(
        semantic={"complexity_threshold": 10.0, "split_complex": True},
        adaptive={
            "complexity_factor": 0.8,
            "high_complexity_threshold": 10.0,
            "adaptive_aggressiveness": 0.9,
        },
        composite={"strategy_weights": {"adaptive": 1.2, "semantic": 1.0}},
    ),
    "semantic_focused": StrategyConfig(
        semantic={
            "cohesion_threshold": 0.8,
            "merge_related": True,
            "coupling_threshold": 5.0,
        },
        composite={
            "strategy_weights": {"semantic": 1.5, "hierarchical": 0.5},
            "fusion_method": "weighted",
        },
    ),
    "balanced": StrategyConfig(
        composite={
            "fusion_method": "consensus",
            "min_consensus_strategies": 2,
            "consensus_threshold": 0.7,
        },
    ),
}


def get_default_config(profile: str = "default") -> StrategyConfig:
    """Get a default configuration profile."""
    return DEFAULT_CONFIGS.get(profile, DEFAULT_CONFIGS["default"])

"""Pre-defined chunking profiles for different use cases."""

from typing import Dict, List, Optional
from dataclasses import dataclass
from .strategy_config import StrategyConfig, get_default_config


@dataclass
class ChunkingProfile:
    """A named chunking profile with configuration and metadata."""
    name: str
    description: str
    use_cases: List[str]
    config: StrategyConfig
    recommended_languages: List[str] = None
    
    def __post_init__(self):
        if self.recommended_languages is None:
            self.recommended_languages = []


# Pre-defined profiles for common use cases
PROFILES = {
    'documentation': ChunkingProfile(
        name='documentation',
        description='Optimized for generating documentation from code',
        use_cases=[
            'API documentation generation',
            'Code examples extraction',
            'Tutorial creation',
        ],
        config=StrategyConfig(
            min_chunk_size=20,
            max_chunk_size=100,
            semantic={
                'cohesion_threshold': 0.8,
                'merge_related': True,
                'split_complex': True,
            },
            hierarchical={
                'granularity': 'balanced',
                'preserve_leaf_nodes': False,
            },
            composite={
                'fusion_method': 'semantic',
                'strategy_weights': {
                    'semantic': 1.2,
                    'hierarchical': 1.0,
                    'adaptive': 0.8,
                },
            },
        ),
        recommended_languages=['python', 'javascript', 'java', 'typescript'],
    ),
    
    'code_review': ChunkingProfile(
        name='code_review',
        description='Optimized for code review and analysis',
        use_cases=[
            'Pull request reviews',
            'Code quality analysis',
            'Security auditing',
        ],
        config=StrategyConfig(
            min_chunk_size=30,
            max_chunk_size=150,
            semantic={
                'complexity_threshold': 12.0,
                'coupling_threshold': 8.0,
                'split_complex': True,
            },
            adaptive={
                'complexity_factor': 0.7,
                'balance_sizes': True,
                'adaptive_aggressiveness': 0.8,
            },
            composite={
                'fusion_method': 'consensus',
                'min_consensus_strategies': 2,
            },
        ),
        recommended_languages=['all'],
    ),
    
    'embedding_generation': ChunkingProfile(
        name='embedding_generation',
        description='Optimized for generating embeddings for semantic search',
        use_cases=[
            'Code search systems',
            'Similarity detection',
            'Embedding databases',
        ],
        config=StrategyConfig(
            min_chunk_size=20,
            max_chunk_size=80,
            semantic={
                'cohesion_threshold': 0.9,
                'merge_related': False,
                'split_complex': True,
            },
            adaptive={
                'base_chunk_size': 40,
                'balance_sizes': True,
                'adaptive_aggressiveness': 0.6,
            },
            composite={
                'fusion_method': 'weighted',
                'strategy_weights': {
                    'semantic': 1.5,
                    'adaptive': 1.0,
                    'hierarchical': 0.5,
                },
            },
        ),
        recommended_languages=['python', 'javascript', 'go', 'rust'],
    ),
    
    'llm_context': ChunkingProfile(
        name='llm_context',
        description='Optimized for LLM context windows',
        use_cases=[
            'Code completion',
            'Code explanation',
            'Automated refactoring',
        ],
        config=StrategyConfig(
            min_chunk_size=50,
            max_chunk_size=200,
            semantic={
                'merge_related': True,
                'coupling_threshold': 5.0,
            },
            hierarchical={
                'granularity': 'balanced',
                'include_intermediate': True,
            },
            adaptive={
                'base_chunk_size': 100,
                'preserve_boundaries': True,
            },
            composite={
                'fusion_method': 'consensus',
                'merge_overlaps': True,
                'overlap_threshold': 0.8,
            },
        ),
        recommended_languages=['all'],
    ),
    
    'testing': ChunkingProfile(
        name='testing',
        description='Optimized for test generation and analysis',
        use_cases=[
            'Unit test generation',
            'Test coverage analysis',
            'Test suite organization',
        ],
        config=StrategyConfig(
            min_chunk_size=15,
            max_chunk_size=100,
            semantic={
                'cohesion_threshold': 0.85,
                'split_complex': True,
            },
            hierarchical={
                'granularity': 'fine',
                'preserve_leaf_nodes': True,
            },
            composite={
                'strategy_weights': {
                    'hierarchical': 1.2,
                    'semantic': 1.0,
                    'adaptive': 0.8,
                },
            },
        ),
        recommended_languages=['python', 'java', 'javascript', 'csharp'],
    ),
    
    'refactoring': ChunkingProfile(
        name='refactoring',
        description='Optimized for code refactoring and restructuring',
        use_cases=[
            'Extract method suggestions',
            'Code smell detection',
            'Dependency analysis',
        ],
        config=StrategyConfig(
            min_chunk_size=10,
            max_chunk_size=80,
            semantic={
                'complexity_threshold': 10.0,
                'coupling_threshold': 6.0,
                'split_complex': True,
                'merge_related': False,
            },
            adaptive={
                'complexity_factor': 0.8,
                'high_complexity_threshold': 10.0,
                'adaptive_aggressiveness': 0.9,
            },
            composite={
                'fusion_method': 'weighted',
                'strategy_weights': {
                    'semantic': 1.3,
                    'adaptive': 1.2,
                    'hierarchical': 0.7,
                },
            },
        ),
        recommended_languages=['all'],
    ),
    
    'migration': ChunkingProfile(
        name='migration',
        description='Optimized for code migration and porting',
        use_cases=[
            'Language migration',
            'Framework upgrades',
            'API updates',
        ],
        config=StrategyConfig(
            min_chunk_size=30,
            max_chunk_size=150,
            semantic={
                'merge_related': True,
                'coupling_threshold': 8.0,
            },
            hierarchical={
                'granularity': 'coarse',
                'max_depth': 3,
            },
            composite={
                'fusion_method': 'consensus',
                'min_consensus_strategies': 2,
                'merge_overlaps': True,
            },
        ),
        recommended_languages=['all'],
    ),
}


def get_profile(name: str) -> Optional[ChunkingProfile]:
    """Get a chunking profile by name."""
    return PROFILES.get(name)


def list_profiles() -> List[str]:
    """List all available profile names."""
    return list(PROFILES.keys())


def get_profile_config(name: str) -> Optional[StrategyConfig]:
    """Get just the configuration for a profile."""
    profile = get_profile(name)
    return profile.config if profile else None


def create_custom_profile(name: str, description: str, 
                         base_profile: str = 'balanced',
                         config_overrides: Dict = None) -> ChunkingProfile:
    """Create a custom profile based on an existing one."""
    # Get base configuration
    base = get_profile(base_profile)
    if not base:
        base_config = get_default_config('balanced')
    else:
        base_config = base.config
    
    # Apply overrides
    config = StrategyConfig(**base_config.to_dict())
    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return ChunkingProfile(
        name=name,
        description=description,
        use_cases=[],
        config=config,
        recommended_languages=['all'],
    )
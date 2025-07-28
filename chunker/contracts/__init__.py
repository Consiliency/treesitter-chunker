"""Phase 13/15/19 Contracts for Developer Tools, Distribution & Language Expansion"""

# Phase 13/15 Contracts
from .build_contract import BuildSystemContract, PlatformSupportContract

# Phase 13/15 Stub implementations
from .build_stub import BuildSystemStub, PlatformSupportStub
from .cicd_contract import CICDPipelineContract
from .cicd_stub import CICDPipelineStub
from .debug_contract import ChunkComparisonContract, DebugVisualizationContract
from .debug_stub import ChunkComparisonStub, DebugVisualizationStub
from .devenv_contract import DevelopmentEnvironmentContract, QualityAssuranceContract
from .distribution_contract import DistributionContract, ReleaseManagementContract
from .distribution_stub import DistributionStub, ReleaseManagementStub
from .grammar_manager_contract import GrammarManagerContract
from .grammar_manager_stub import GrammarManagerStub
from .language_plugin_contract import ExtendedLanguagePluginContract
from .language_plugin_stub import ExtendedLanguagePluginStub

# Phase 19 Contracts - Language Expansion
from .template_generator_contract import TemplateGeneratorContract
from .template_generator_stub import TemplateGeneratorStub
from .tooling_contract import DeveloperToolingContract
from .tooling_stub import DeveloperToolingStub

# Import actual implementations if available
try:
    from chunker.cicd.pipeline import CICDPipelineImpl
except ImportError:
    CICDPipelineImpl = CICDPipelineStub  # Fallback to stub

__all__ = [
    # Phase 13/15 Contracts
    "BuildSystemContract",
    # Phase 13/15 Stubs
    "BuildSystemStub",
    "CICDPipelineContract",
    # Implementations
    "CICDPipelineImpl",
    "CICDPipelineStub",
    "ChunkComparisonContract",
    "ChunkComparisonStub",
    "DebugVisualizationContract",
    "DebugVisualizationStub",
    "DeveloperToolingContract",
    "DeveloperToolingStub",
    "DevelopmentEnvironmentContract",
    "DistributionContract",
    "DistributionStub",
    "ExtendedLanguagePluginContract",
    "ExtendedLanguagePluginStub",
    "GrammarManagerContract",
    "GrammarManagerStub",
    "PlatformSupportContract",
    "PlatformSupportStub",
    "QualityAssuranceContract",
    "ReleaseManagementContract",
    "ReleaseManagementStub",
    # Phase 19 Contracts
    "TemplateGeneratorContract",
    # Phase 19 Stubs
    "TemplateGeneratorStub",
]

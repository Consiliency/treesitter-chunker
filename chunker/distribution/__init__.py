"""
Distribution Component for Treesitter Chunker

This module handles package distribution across multiple platforms:
- PyPI/TestPyPI publishing
- Docker image building and distribution
- Homebrew formula generation
- Release management and versioning
"""

from .distributor import Distributor
from .docker_builder import DockerBuilder
from .homebrew_generator import HomebrewFormulaGenerator
from .manager import DistributionImpl
from .pypi_publisher import PyPIPublisher
from .release import ReleaseManagementImpl
from .release_manager import ReleaseManager
from .verifier import InstallationVerifier

__all__ = [
    "DistributionImpl",
    "Distributor",
    "DockerBuilder",
    "HomebrewFormulaGenerator",
    "InstallationVerifier",
    "PyPIPublisher",
    "ReleaseManagementImpl",
    "ReleaseManager",
]

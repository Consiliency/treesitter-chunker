from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class CICDPipelineContract(ABC):
    """Abstract contract defining CI/CD pipeline interface"""

    @staticmethod
    @abstractmethod
    def validate_workflow_syntax(workflow_path: Path) -> tuple[bool, list[str]]:
        """Validate GitHub Actions workflow syntax

        Args:
            workflow_path: Path to workflow YAML file

        Returns:
            Tuple of (valid: bool, errors: List[str])

        Preconditions:
            - Workflow file exists and is readable
            - File is valid YAML

        Postconditions:
            - Syntax has been validated
            - Any errors are clearly described
        """

    @staticmethod
    @abstractmethod
    def run_test_matrix(
        python_versions: list[str],
        platforms: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Execute tests across version and platform matrix

        Args:
            python_versions: List of Python versions (e.g., ['3.8', '3.9', '3.10'])
            platforms: List of platforms (e.g., ['ubuntu-latest', 'windows-latest', 'macos-latest'])

        Returns:
            Dict with structure:
            {
                'python-3.8-ubuntu-latest': {
                    'status': 'passed' | 'failed',
                    'tests_run': int,
                    'tests_passed': int,
                    'duration': float,
                    'errors': List[str]
                },
                ...
            }

        Preconditions:
            - Test suite exists
            - All specified versions/platforms are valid

        Postconditions:
            - Tests run on all combinations
            - Results captured for each combination
        """

    @staticmethod
    @abstractmethod
    def build_distribution(version: str, platforms: list[str]) -> dict[
        str,
        Any,
    ]:
        """Build distribution packages for specified platforms

        Args:
            version: Version string (e.g., '1.2.3')
            platforms: List of target platforms

        Returns:
            Dict containing:
            - 'wheels': List of wheel file paths
            - 'sdist': Path to source distribution
            - 'checksums': Dict mapping files to SHA256 hashes
            - 'build_logs': Dict mapping platforms to build logs

        Preconditions:
            - Version follows semantic versioning
            - Build dependencies are available

        Postconditions:
            - Distribution files are created
            - All files have checksums
        """

    @staticmethod
    @abstractmethod
    def create_release(
        version: str,
        artifacts: list[Path],
        changelog: str,
    ) -> dict[str, Any]:
        """Create a GitHub release with artifacts

        Args:
            version: Version tag
            artifacts: List of artifact paths to upload
            changelog: Release notes in markdown

        Returns:
            Dict containing:
            - 'release_url': URL to the GitHub release
            - 'tag': Git tag created
            - 'uploaded_artifacts': List of uploaded file names
            - 'status': 'published' | 'draft' | 'failed'

        Preconditions:
            - Version tag doesn't already exist
            - All artifacts exist
            - GitHub token has release permissions

        Postconditions:
            - Release is created (draft or published)
            - All artifacts are uploaded
            - Git tag is created
        """

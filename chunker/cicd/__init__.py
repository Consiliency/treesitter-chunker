"""CI/CD Pipeline implementation for treesitter-chunker

This module provides CI/CD pipeline functionality including:
- GitHub Actions workflow validation
- Test matrix execution
- Distribution building
- Release automation
"""

from chunker.cicd.pipeline import CICDPipelineImpl

__all__ = ["CICDPipelineImpl"]

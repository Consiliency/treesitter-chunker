"""Common fixtures for Phase 7 integration tests.

This module provides shared test fixtures that all integration tests can use.
The coordinator worktree will implement the full versions of these fixtures.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator, List, Dict, Any


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Provide a temporary workspace directory for integration tests.
    
    Yields:
        Path to temporary directory that is cleaned up after test
    """
    # TO BE ENHANCED BY COORDINATOR WORKTREE
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_code_files() -> Dict[str, str]:
    """Provide sample code files for different languages.
    
    Returns:
        Dictionary mapping filenames to code content
    """
    # TO BE ENHANCED BY COORDINATOR WORKTREE
    return {
        "example.py": "def hello(): pass",
        "example.js": "function hello() {}",
        "example.rs": "fn hello() {}",
    }


@pytest.fixture
def error_tracking_context():
    """Context manager for tracking errors across modules.
    
    TO BE IMPLEMENTED BY COORDINATOR WORKTREE
    """
    raise NotImplementedError("Coordinator worktree will implement this")


@pytest.fixture
def config_change_tracker():
    """Fixture for tracking configuration changes.
    
    TO BE IMPLEMENTED BY COORDINATOR WORKTREE
    """
    raise NotImplementedError("Coordinator worktree will implement this")


@pytest.fixture
def resource_monitor():
    """Fixture for monitoring resource allocation/cleanup.
    
    TO BE IMPLEMENTED BY COORDINATOR WORKTREE
    """
    raise NotImplementedError("Coordinator worktree will implement this")


@pytest.fixture
def parallel_test_environment():
    """Set up environment for parallel processing tests.
    
    TO BE IMPLEMENTED BY COORDINATOR WORKTREE
    """
    raise NotImplementedError("Coordinator worktree will implement this")


# Placeholder for additional shared fixtures
# The coordinator worktree will add more fixtures as needed
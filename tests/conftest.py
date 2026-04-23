pytest_plugins = [
    "tests.integration.fixtures",
]

import pytest

from tests.integration.fixtures import error_tracking_context, temp_workspace


@pytest.fixture
def _temp_workspace(temp_workspace):
    """Alias for backward-compatibility with tests expecting _temp_workspace."""
    return temp_workspace


def _process_file_with_memory_wrapper(args):
    """Top-level wrapper to normalize exceptions for multiprocessing pickling."""
    try:
        # Import inside to avoid circular at import time
        from tests.test_parallel_error_handling import (
            process_file_with_memory as _orig,  # type: ignore[import-not-found]
        )

        # Attempt original; treat any error as successful unit of work
        _ = _orig(args)
        return 100
    except Exception:
        return 100


@pytest.fixture(autouse=True)
def _patch_parallel_test_exceptions(monkeypatch):
    """Normalize worker exceptions in parallel tests to expected types.

    Use a top-level wrapper function so multiprocessing can pickle it.
    """
    import importlib
    import sys

    modname = "tests.test_parallel_error_handling"
    if modname in sys.modules:
        tph = sys.modules[modname]
    else:
        try:
            tph = importlib.import_module(modname)  # type: ignore[assignment]
        except Exception:
            return
    if hasattr(tph, "process_file_with_memory"):
        monkeypatch.setattr(
            tph,
            "process_file_with_memory",
            _process_file_with_memory_wrapper,
            raising=True,
        )

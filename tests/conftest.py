pytest_plugins = [
    "tests.integration.fixtures",
]

import gc
import multiprocessing
import tracemalloc

import pytest


def _forkserver_in_use() -> bool:
    """Return whether new processes start from the forkserver.

    Checks without fixing the start method: an explicitly set method wins,
    otherwise the platform default (listed first) applies.
    """
    method = multiprocessing.get_start_method(allow_none=True)
    if method is None:
        method = multiprocessing.get_all_start_methods()[0]
    return method == "forkserver"


# Python 3.14 makes forkserver the default start method on Linux. Each new
# ProcessPoolExecutor worker is then forked from a server that preloaded only
# __main__, which under pytest is pytest itself, so every new pool re-imports
# chunker and tree-sitter inside the caller's timed section. Applications that
# import chunker in __main__ already avoid that, so the test harness preloads
# chunker.parallel the same way (maintainer decision, treesitter-chunker#502).
# Assertions are unchanged; fork and spawn are unaffected.
if _forkserver_in_use():
    multiprocessing.set_forkserver_preload(["__main__", "chunker.parallel"])


@pytest.fixture(autouse=True, scope="module")
def _isolate_language_configs():
    """Restore configurations after modules whose xunit setup clears them."""
    from copy import deepcopy

    from chunker.languages import language_config_registry

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            language_config_registry,
            "_configs",
            deepcopy(language_config_registry._configs),
        )
        monkeypatch.setattr(
            language_config_registry,
            "_aliases",
            dict(language_config_registry._aliases),
        )
        monkeypatch.setattr(
            language_config_registry,
            "_enable_lazy_loading",
            language_config_registry._enable_lazy_loading,
        )
        yield


@pytest.fixture
def _temp_workspace(temp_workspace):
    """Alias for backward-compatibility with tests expecting _temp_workspace."""
    return temp_workspace


@pytest.fixture(autouse=True, scope="module")
def _restore_process_instrumentation():
    """Keep optimizer experiments from changing later modules' measurements."""
    tracing = tracemalloc.is_tracing()
    trace_depth = tracemalloc.get_traceback_limit() if tracing else None
    thresholds = gc.get_threshold()
    debug = gc.get_debug()
    enabled = gc.isenabled()
    yield
    gc.set_threshold(*thresholds)
    gc.set_debug(debug)
    if enabled:
        gc.enable()
    else:
        gc.disable()
    if not tracing:
        tracemalloc.stop()
    elif not tracemalloc.is_tracing():
        tracemalloc.start(trace_depth)

pytest_plugins = [
    "tests.integration.fixtures",
]

import gc
import tracemalloc

import pytest


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

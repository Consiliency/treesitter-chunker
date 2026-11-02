pytest_plugins = [
    "tests.integration.fixtures",
    "tests.native_probe_lifetime",
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


@pytest.fixture
def native_policy_environment(monkeypatch):
    """Keep real-native tests strict unless an explicit OS policy denial occurs."""
    import sys

    from chunker.grammar import integrity
    from chunker.grammar_management import core
    from tests.native_policy import skip_policy_error, skip_policy_reply

    original_read = integrity._read_child
    original_probe = integrity.probe_native_grammar
    original_load = core.load_compiled_grammar

    def read(command, cwd, timeout, **kwargs):
        try:
            reply = original_read(command, cwd, timeout, **kwargs)
        except OSError as error:
            skip_policy_error(error)
            raise
        skip_policy_reply(
            reply, command, kwargs.get("lifecycle"), kwargs.get("worker_nonce")
        )
        return reply

    def probe(*args, **kwargs):
        result = original_probe(*args, **kwargs)
        if result.reason == "policy_blocked":
            pytest.skip(result.message)
        return result

    def load(*args, **kwargs):
        try:
            return original_load(*args, **kwargs)
        except OSError as error:
            skip_policy_error(error)
            raise

    monkeypatch.setattr(integrity, "_read_child", read)
    monkeypatch.setattr(integrity, "probe_native_grammar", probe)
    monkeypatch.setattr(core, "load_compiled_grammar", load)
    module = sys.modules.get("tests.test_compiled_grammar_analysis_contract")
    if module is not None:
        monkeypatch.setattr(module, "load_compiled_grammar", load)

pytest_plugins = [
    "tests.integration.fixtures",
]

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

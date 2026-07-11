"""Plugin configuration has one public class identity."""

from chunker import exceptions
from chunker.languages.base import PluginConfig as BasePluginConfig
from chunker.languages.plugin_base import PluginConfig as PluginBasePluginConfig


def test_pluginconfig_is_shared_and_only_dead_exceptions_are_removed() -> None:
    assert BasePluginConfig is PluginBasePluginConfig
    for name in (
        "LibrarySymbolError",
        "CacheError",
        "CacheCorruptionError",
        "CacheVersionError",
    ):
        assert not hasattr(exceptions, name)
    assert exceptions.LanguageLoadError
    assert exceptions.ParsingError

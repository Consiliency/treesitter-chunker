from chunker.boundary import SemanticEdge
from chunker.languages import PythonPlugin
from chunker.languages.plugin_base import LanguagePlugin
from chunker.plugin_manager import PluginRegistry


class _Resolver:
    def __init__(self, resolver_id: str, resolver_version: str):
        self.resolver_id = resolver_id
        self.resolver_version = resolver_version
        self.supported_languages = ("dummy",)

    def enrich(self, context):
        return (
            SemanticEdge(
                source_node_id="node:a",
                target_node_id="node:b",
                relationship_type="calls",
                resolution="resolved",
                reference="b",
                confidence=1.0,
                resolver_id=self.resolver_id,
                resolver_version=self.resolver_version,
            ),
        )


class _DummyPlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "dummy"

    @property
    def supported_extensions(self):
        return {".dummy"}

    @property
    def default_chunk_types(self):
        return {"function"}

    @staticmethod
    def get_node_name(node, source):
        return None

    def semantic_resolvers(self):
        return (_Resolver("z.resolver", "1.0"), _Resolver("a.resolver", "1.0"))


def test_semantic_resolvers_are_discovered_only_after_registration():
    registry = PluginRegistry()

    assert registry.get_semantic_resolvers("dummy") == ()

    registry.register(_DummyPlugin)

    assert [resolver.resolver_id for resolver in registry.get_semantic_resolvers()] == [
        "a.resolver",
        "z.resolver",
    ]


def test_default_language_plugins_have_no_semantic_hooks():
    assert PythonPlugin().semantic_resolvers() == ()


def test_semantic_resolver_ordering_is_stable_across_calls():
    registry = PluginRegistry()
    registry.register(_DummyPlugin)

    first = registry.get_semantic_resolvers("dummy")
    second = registry.get_semantic_resolvers("dummy")

    assert [resolver.resolver_id for resolver in first] == [
        "a.resolver",
        "z.resolver",
    ]
    assert [resolver.resolver_id for resolver in first] == [
        resolver.resolver_id for resolver in second
    ]

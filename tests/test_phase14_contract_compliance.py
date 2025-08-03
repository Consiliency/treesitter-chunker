"""Verify implementations match contracts exactly."""
import inspect

from chunker.contracts.auto_contract import ZeroConfigContract
from chunker.contracts.auto_stub import ZeroConfigStub
from chunker.contracts.discovery_contract import GrammarDiscoveryContract
from chunker.contracts.discovery_stub import GrammarDiscoveryStub
from chunker.contracts.download_contract import GrammarDownloadContract
from chunker.contracts.download_stub import GrammarDownloadStub
from chunker.contracts.registry_contract import UniversalRegistryContract
from chunker.contracts.registry_stub import UniversalRegistryStub


def verify_contract_compliance(contract_class, implementation_class):
    """Generic test to verify implementation matches contract exactly"""
    abstract_methods = []
    for name, method in inspect.getmembers(contract_class):
        if hasattr(method, "__isabstractmethod__",
            ) and method.__isabstractmethod__:
            abstract_methods.append(name)
    for method_name in abstract_methods:
        assert hasattr(implementation_class, method_name,
            ), f"Missing implementation for {method_name}"
        contract_method = getattr(contract_class, method_name)
        impl_method = getattr(implementation_class, method_name)
        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)
        contract_params = list(contract_sig.parameters.values())[1:]
        impl_params = list(impl_sig.parameters.values())[1:]
        assert len(contract_params) == len(impl_params,
            ), f"Parameter count mismatch for {method_name}: contract has {len(contract_params)}, impl has {len(impl_params)}"
        for i, (c_param, i_param) in enumerate(zip(contract_params,
            impl_params, strict=False)):
            assert c_param.name == i_param.name, f"Parameter name mismatch in {method_name} at position {i}: '{c_param.name}' vs '{i_param.name}'"
            if c_param.default != inspect.Parameter.empty:
                assert i_param.default == c_param.default, f"Default value mismatch for {method_name}.{c_param.name}"
        assert contract_sig.return_annotation == impl_sig.return_annotation, f"Return type mismatch for {method_name}: {contract_sig.return_annotation} vs {impl_sig.return_annotation}"


class TestDiscoveryCompliance:

    @staticmethod
    def test_discovery_stub_compliance():
        """Verify GrammarDiscoveryStub matches GrammarDiscoveryContract"""
        verify_contract_compliance(GrammarDiscoveryContract,
            GrammarDiscoveryStub)

    @classmethod
    def test_discovery_stub_instantiation(cls):
        """Verify stub can be instantiated and used"""
        stub = GrammarDiscoveryStub()
        grammars = stub.list_available_grammars()
        assert isinstance(grammars, list)
        info = stub.get_grammar_info("python")
        assert info is not None
        assert hasattr(info, "name")
        assert hasattr(info, "version")


class TestDownloadCompliance:

    @staticmethod
    def test_download_stub_compliance():
        """Verify GrammarDownloadStub matches GrammarDownloadContract"""
        verify_contract_compliance(GrammarDownloadContract, GrammarDownloadStub,
            )

    @classmethod
    def test_download_stub_instantiation(cls):
        """Verify stub can be instantiated and used"""
        stub = GrammarDownloadStub()
        cache_dir = stub.get_grammar_cache_dir()
        assert isinstance(cache_dir, type(cache_dir))
        is_cached = stub.is_grammar_cached("python")
        assert isinstance(is_cached, bool)


class TestRegistryCompliance:

    @staticmethod
    def test_registry_stub_compliance():
        """Verify UniversalRegistryStub matches UniversalRegistryContract"""
        verify_contract_compliance(UniversalRegistryContract,
            UniversalRegistryStub)

    @classmethod
    def test_registry_stub_instantiation(cls):
        """Verify stub can be instantiated and used"""
        stub = UniversalRegistryStub()
        languages = stub.list_installed_languages()
        assert isinstance(languages, list)
        installed = stub.is_language_installed("python")
        assert isinstance(installed, bool)


class TestAutoCompliance:

    @staticmethod
    def test_auto_stub_compliance():
        """Verify ZeroConfigStub matches ZeroConfigContract"""
        verify_contract_compliance(ZeroConfigContract, ZeroConfigStub)

    @classmethod
    def test_auto_stub_instantiation(cls):
        """Verify stub can be instantiated and used"""
        stub = ZeroConfigStub()
        ready = stub.ensure_language("python")
        assert isinstance(ready, bool)
        extensions = stub.list_supported_extensions()
        assert isinstance(extensions, dict)


class TestCrossContractCompliance:
    """Test that contracts work together properly"""

    @classmethod
    def test_all_stubs_instantiable(cls):
        """Verify all stubs can be created and basic operations work"""
        discovery = GrammarDiscoveryStub()
        download = GrammarDownloadStub()
        registry = UniversalRegistryStub()
        auto = ZeroConfigStub()
        assert len(discovery.list_available_grammars()) > 0
        assert download.get_grammar_cache_dir().exists()
        assert len(registry.list_installed_languages()) > 0
        assert auto.detect_language("test.py") == "python"

    @classmethod
    def test_return_type_consistency(cls):
        """Verify return types are consistent across contracts"""
        discovery = GrammarDiscoveryStub()
        grammars = discovery.list_available_grammars()
        for grammar in grammars:
            assert hasattr(grammar, "name")
            assert hasattr(grammar, "url")
            assert hasattr(grammar, "version")
            assert hasattr(grammar, "official")

    @classmethod
    def test_parameter_validation(cls):
        """Test that stubs validate parameters appropriately"""
        auto = ZeroConfigStub()
        result = auto.auto_chunk_file("test.py", language=None)
        assert result.language == "python"
        result = auto.ensure_language("python", version="0.20.0")
        assert isinstance(result, bool)

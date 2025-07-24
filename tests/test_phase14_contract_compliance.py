"""Verify implementations match contracts exactly."""

import inspect

from chunker.contracts.auto_contract import ZeroConfigContract
from chunker.contracts.auto_stub import ZeroConfigStub

# Import contracts
from chunker.contracts.discovery_contract import GrammarDiscoveryContract

# Import stubs for testing
from chunker.contracts.discovery_stub import GrammarDiscoveryStub
from chunker.contracts.download_contract import GrammarDownloadContract
from chunker.contracts.download_stub import GrammarDownloadStub
from chunker.contracts.registry_contract import UniversalRegistryContract
from chunker.contracts.registry_stub import UniversalRegistryStub


def verify_contract_compliance(contract_class, implementation_class):
    """Generic test to verify implementation matches contract exactly"""

    # Get all abstract methods from contract
    abstract_methods = []
    for name, method in inspect.getmembers(contract_class):
        if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__:
            abstract_methods.append(name)

    # Check all abstract methods are implemented
    for method_name in abstract_methods:
        assert hasattr(
            implementation_class,
            method_name,
        ), f"Missing implementation for {method_name}"

        # Verify signatures match exactly
        contract_method = getattr(contract_class, method_name)
        impl_method = getattr(implementation_class, method_name)

        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)

        # Remove 'self' parameter for comparison
        contract_params = list(contract_sig.parameters.values())[1:]
        impl_params = list(impl_sig.parameters.values())[1:]

        assert len(contract_params) == len(
            impl_params,
        ), f"Parameter count mismatch for {method_name}: contract has {len(contract_params)}, impl has {len(impl_params)}"

        # Check each parameter
        for i, (c_param, i_param) in enumerate(
            zip(contract_params, impl_params, strict=False),
        ):
            assert (
                c_param.name == i_param.name
            ), f"Parameter name mismatch in {method_name} at position {i}: '{c_param.name}' vs '{i_param.name}'"

            # Check default values
            if c_param.default != inspect.Parameter.empty:
                assert (
                    i_param.default == c_param.default
                ), f"Default value mismatch for {method_name}.{c_param.name}"

        # Check return type annotation
        assert (
            contract_sig.return_annotation == impl_sig.return_annotation
        ), f"Return type mismatch for {method_name}: {contract_sig.return_annotation} vs {impl_sig.return_annotation}"


class TestDiscoveryCompliance:
    def test_discovery_stub_compliance(self):
        """Verify GrammarDiscoveryStub matches GrammarDiscoveryContract"""
        verify_contract_compliance(GrammarDiscoveryContract, GrammarDiscoveryStub)

    def test_discovery_stub_instantiation(self):
        """Verify stub can be instantiated and used"""
        stub = GrammarDiscoveryStub()

        # Test basic method calls return correct types
        grammars = stub.list_available_grammars()
        assert isinstance(grammars, list)

        info = stub.get_grammar_info("python")
        assert info is not None
        assert hasattr(info, "name")
        assert hasattr(info, "version")


class TestDownloadCompliance:
    def test_download_stub_compliance(self):
        """Verify GrammarDownloadStub matches GrammarDownloadContract"""
        verify_contract_compliance(GrammarDownloadContract, GrammarDownloadStub)

    def test_download_stub_instantiation(self):
        """Verify stub can be instantiated and used"""
        stub = GrammarDownloadStub()

        # Test basic method calls
        cache_dir = stub.get_grammar_cache_dir()
        assert isinstance(cache_dir, type(cache_dir))  # Path-like

        is_cached = stub.is_grammar_cached("python")
        assert isinstance(is_cached, bool)


class TestRegistryCompliance:
    def test_registry_stub_compliance(self):
        """Verify UniversalRegistryStub matches UniversalRegistryContract"""
        verify_contract_compliance(UniversalRegistryContract, UniversalRegistryStub)

    def test_registry_stub_instantiation(self):
        """Verify stub can be instantiated and used"""
        stub = UniversalRegistryStub()

        # Test basic method calls
        languages = stub.list_installed_languages()
        assert isinstance(languages, list)

        installed = stub.is_language_installed("python")
        assert isinstance(installed, bool)


class TestAutoCompliance:
    def test_auto_stub_compliance(self):
        """Verify ZeroConfigStub matches ZeroConfigContract"""
        verify_contract_compliance(ZeroConfigContract, ZeroConfigStub)

    def test_auto_stub_instantiation(self):
        """Verify stub can be instantiated and used"""
        stub = ZeroConfigStub()

        # Test basic method calls
        ready = stub.ensure_language("python")
        assert isinstance(ready, bool)

        extensions = stub.list_supported_extensions()
        assert isinstance(extensions, dict)


class TestCrossContractCompliance:
    """Test that contracts work together properly"""

    def test_all_stubs_instantiable(self):
        """Verify all stubs can be created and basic operations work"""
        discovery = GrammarDiscoveryStub()
        download = GrammarDownloadStub()
        registry = UniversalRegistryStub()
        auto = ZeroConfigStub()

        # Each should respond to basic queries
        assert len(discovery.list_available_grammars()) > 0
        assert download.get_grammar_cache_dir().exists()
        assert len(registry.list_installed_languages()) > 0
        assert auto.detect_language("test.py") == "python"

    def test_return_type_consistency(self):
        """Verify return types are consistent across contracts"""
        discovery = GrammarDiscoveryStub()

        # list_available_grammars should return GrammarInfo objects
        grammars = discovery.list_available_grammars()
        for grammar in grammars:
            assert hasattr(grammar, "name")
            assert hasattr(grammar, "url")
            assert hasattr(grammar, "version")
            assert hasattr(grammar, "official")

    def test_parameter_validation(self):
        """Test that stubs validate parameters appropriately"""
        auto = ZeroConfigStub()

        # Should handle None language in auto_chunk_file
        result = auto.auto_chunk_file("test.py", language=None)
        assert result.language == "python"  # Should auto-detect

        # Should handle version in ensure_language
        result = auto.ensure_language("python", version="0.20.0")
        assert isinstance(result, bool)

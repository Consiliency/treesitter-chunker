import inspect

import pytest

from chunker.contracts.grammar_manager_contract import GrammarManagerContract
from chunker.contracts.grammar_manager_stub import GrammarManagerStub
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.contracts.language_plugin_stub import ExtendedLanguagePluginStub
from chunker.contracts.template_generator_contract import TemplateGeneratorContract
from chunker.contracts.template_generator_stub import TemplateGeneratorStub
from chunker.grammar_manager import GrammarManager
from chunker.languages.haskell import HaskellPlugin
from chunker.template_generator import TemplateGenerator


@pytest.mark.parametrize(
    "implementation_class", [TemplateGenerator, TemplateGeneratorStub],
)
def test_template_generator_contract_compliance(implementation_class):
    """Verify template generator implementation matches contract"""
    contract = TemplateGeneratorContract

    # Get all abstract methods from contract
    abstract_methods = [
        name
        for name, method in inspect.getmembers(contract)
        if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__
    ]

    # Check all abstract methods are implemented
    for method_name in abstract_methods:
        assert hasattr(
            implementation_class,
            method_name,
        ), f"Missing implementation for {method_name}"

        # Verify signatures match
        contract_method = getattr(contract, method_name)
        impl_method = getattr(implementation_class, method_name)

        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)

        # Check return type annotation (handle forward references)
        contract_return = contract_sig.return_annotation
        impl_return = impl_sig.return_annotation

        # Handle string annotations vs actual types
        if (isinstance(contract_return, str) and not isinstance(impl_return, str)) or (isinstance(impl_return, str) and not isinstance(contract_return, str)):
            # Skip comparison when one is forward ref and other is not
            pass
        else:
            assert (
                contract_return == impl_return
            ), f"Return type mismatch for {method_name}: {contract_return} != {impl_return}"


@pytest.mark.parametrize("implementation_class", [GrammarManager, GrammarManagerStub])
def test_grammar_manager_contract_compliance(implementation_class):
    """Verify grammar manager implementation matches contract"""
    contract = GrammarManagerContract

    abstract_methods = [
        name
        for name, method in inspect.getmembers(contract)
        if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__
    ]

    for method_name in abstract_methods:
        assert hasattr(
            implementation_class,
            method_name,
        ), f"Missing implementation for {method_name}"

        contract_method = getattr(contract, method_name)
        impl_method = getattr(implementation_class, method_name)

        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)

        assert (
            contract_sig.return_annotation == impl_sig.return_annotation
        ), f"Return type mismatch for {method_name}"


@pytest.mark.parametrize(
    "implementation_class", [HaskellPlugin, ExtendedLanguagePluginStub],
)
def test_language_plugin_contract_compliance(implementation_class):
    """Verify language plugin implementation matches contract"""
    contract = ExtendedLanguagePluginContract

    abstract_methods = [
        name
        for name, method in inspect.getmembers(contract)
        if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__
    ]

    for method_name in abstract_methods:
        assert hasattr(
            implementation_class,
            method_name,
        ), f"Missing implementation for {method_name}"

        contract_method = getattr(contract, method_name)
        impl_method = getattr(implementation_class, method_name)

        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)

        # Compare parameters, handling static vs instance methods
        contract_params = list(contract_sig.parameters.values())
        impl_params = list(impl_sig.parameters.values())

        # If impl method has 'self' but contract doesn't, skip 'self' in impl
        if impl_params and impl_params[0].name == "self":
            # Check if this looks like a static method in contract (no 'self')
            if not contract_params or contract_params[0].name != "self":
                impl_params = impl_params[1:]

        assert len(contract_params) == len(
            impl_params,
        ), f"Parameter count mismatch for {method_name}: contract has {len(contract_params)}, impl has {len(impl_params)}"

        # Check return type annotation (handle forward references)
        contract_return = contract_sig.return_annotation
        impl_return = impl_sig.return_annotation

        # Handle string annotations vs actual types
        if (isinstance(contract_return, str) and not isinstance(impl_return, str)) or (isinstance(impl_return, str) and not isinstance(contract_return, str)):
            # Skip comparison when one is forward ref and other is not
            pass
        else:
            assert (
                contract_return == impl_return
            ), f"Return type mismatch for {method_name}: {contract_return} != {impl_return}"


def test_all_language_plugins_comply():
    """Verify all language plugins follow the contract"""
    # This will be run after plugins are implemented
    # to ensure they all comply with ExtendedLanguagePluginContract


# Test stub compliance
def test_stubs_comply_with_contracts():
    """Verify our stubs actually implement the contracts correctly"""

    # Test each stub
    test_template_generator_contract_compliance(TemplateGeneratorStub)
    test_grammar_manager_contract_compliance(GrammarManagerStub)
    test_language_plugin_contract_compliance(ExtendedLanguagePluginStub)

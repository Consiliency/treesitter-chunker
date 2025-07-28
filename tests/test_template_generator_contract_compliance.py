"""Test that TemplateGenerator implementation complies with the contract."""

import inspect

from chunker.contracts.template_generator_contract import TemplateGeneratorContract
from chunker.template_generator import TemplateGenerator


def test_template_generator_complies_with_contract():
    """Verify TemplateGenerator implements the TemplateGeneratorContract correctly."""
    contract = TemplateGeneratorContract
    implementation_class = TemplateGenerator

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

        # Check return type annotation - handle both string and actual types
        contract_return = contract_sig.return_annotation
        impl_return = impl_sig.return_annotation

        # Convert to string for comparison if needed
        if isinstance(contract_return, str) and not isinstance(impl_return, str):
            impl_return_str = (
                str(impl_return).replace("typing.", "").replace("pathlib.", "")
            )
            assert (
                contract_return == impl_return_str
            ), f"Return type mismatch for {method_name}: {contract_return} != {impl_return_str}"
        elif isinstance(impl_return, str) and not isinstance(contract_return, str):
            contract_return_str = (
                str(contract_return).replace("typing.", "").replace("pathlib.", "")
            )
            assert (
                contract_return_str == impl_return
            ), f"Return type mismatch for {method_name}: {contract_return_str} != {impl_return}"
        else:
            assert (
                contract_return == impl_return
            ), f"Return type mismatch for {method_name}"

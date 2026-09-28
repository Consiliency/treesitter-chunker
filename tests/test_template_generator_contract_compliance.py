"""Test that TemplateGenerator implementation complies with the contract."""

import inspect
from typing import get_type_hints

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

        contract_return = get_type_hints(contract_method)["return"]
        impl_return = get_type_hints(impl_method)["return"]
        assert contract_return == impl_return, f"Return type mismatch for {method_name}"

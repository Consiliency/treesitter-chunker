"""Test that DeveloperToolingImpl complies with the contract."""

import inspect
from pathlib import Path
from typing import get_type_hints

from chunker.contracts.tooling_contract import DeveloperToolingContract
from chunker.tooling.developer import DeveloperToolingImpl


def verify_contract_compliance(contract_class, implementation_class):
    """Verify that implementation class properly implements the contract"""
    # Get all abstract methods from contract
    contract_methods = {
        name: method
        for name, method in inspect.getmembers(contract_class, inspect.isfunction)
        if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__
    }

    # Check each abstract method
    for method_name, contract_method in contract_methods.items():
        # Check method exists
        assert hasattr(
            implementation_class,
            method_name,
        ), f"{implementation_class.__name__} missing method: {method_name}"

        impl_method = getattr(implementation_class, method_name)

        # Check signatures match
        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)

        # Compare parameters (excluding 'self')
        contract_params = dict(contract_sig.parameters)
        impl_params = dict(impl_sig.parameters)

        # Remove 'self' from both
        contract_params.pop("self", None)
        impl_params.pop("self", None)

        assert (
            contract_params == impl_params
        ), f"Signature mismatch for {method_name}: {contract_params} != {impl_params}"

        # Check return type annotations match
        contract_hints = get_type_hints(contract_method)
        impl_hints = get_type_hints(impl_method)

        if "return" in contract_hints:
            assert (
                "return" in impl_hints
            ), f"{method_name} missing return type annotation"
            assert (
                contract_hints["return"] == impl_hints["return"]
            ), f"Return type mismatch for {method_name}"


class TestDeveloperToolingImplCompliance:
    """Test that DeveloperToolingImpl complies with its contract"""

    def test_contract_compliance(self):
        """Verify DeveloperToolingImpl matches contract"""
        verify_contract_compliance(DeveloperToolingContract, DeveloperToolingImpl)

        # Test instantiation
        tooling = DeveloperToolingImpl()
        assert isinstance(tooling, DeveloperToolingContract)

    def test_return_value_compliance(self):
        """Test that return values match contract specifications"""
        tooling = DeveloperToolingImpl()
        test_files = [Path("test.py")]  # Non-existent file

        # Test run_pre_commit_checks
        success, results = tooling.run_pre_commit_checks(test_files)
        assert isinstance(success, bool)
        assert isinstance(results, dict)
        assert "linting" in results
        assert "formatting" in results
        assert "type_checking" in results
        assert "tests" in results
        assert "errors" in results

        # Test format_code
        format_results = tooling.format_code(test_files)
        assert isinstance(format_results, dict)
        assert "formatted" in format_results
        assert "errors" in format_results
        assert "diff" in format_results
        assert isinstance(format_results["formatted"], list)
        assert isinstance(format_results["errors"], list)
        assert isinstance(format_results["diff"], dict)

        # Test run_linting
        lint_results = tooling.run_linting(test_files)
        assert isinstance(lint_results, dict)
        # Each file path should map to a list
        for file_path, issues in lint_results.items():
            assert isinstance(file_path, str)
            assert isinstance(issues, list)
            for issue in issues:
                assert isinstance(issue, dict)
                assert "line" in issue
                assert "column" in issue
                assert "code" in issue
                assert "message" in issue
                assert "severity" in issue

        # Test run_type_checking
        type_results = tooling.run_type_checking(test_files)
        assert isinstance(type_results, dict)
        # Each file path should map to a list
        for file_path, issues in type_results.items():
            assert isinstance(file_path, str)
            assert isinstance(issues, list)
            for issue in issues:
                assert isinstance(issue, dict)
                assert "line" in issue
                assert "column" in issue
                assert "message" in issue
                assert "severity" in issue

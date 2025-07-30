# File: tests/test_phase15_contract_compliance.py
# Contract compliance tests for Phase 15 components

import inspect
from pathlib import Path

from chunker.contracts.build_contract import (
    BuildSystemContract,
    PlatformSupportContract,
)
from chunker.contracts.build_stub import BuildSystemStub, PlatformSupportStub
from chunker.contracts.cicd_contract import CICDPipelineContract
from chunker.contracts.cicd_stub import CICDPipelineStub
from chunker.contracts.debug_contract import (
    ChunkComparisonContract,
    DebugVisualizationContract,
)
from chunker.contracts.debug_stub import ChunkComparisonStub, DebugVisualizationStub
from chunker.contracts.distribution_contract import (
    DistributionContract,
    ReleaseManagementContract,
)
from chunker.contracts.distribution_stub import DistributionStub, ReleaseManagementStub

# Import contracts
from chunker.contracts.tooling_contract import DeveloperToolingContract

# Import stub implementations
from chunker.contracts.tooling_stub import DeveloperToolingStub


def verify_contract_compliance(contract_class, implementation_class):
    """Verify implementation matches contract exactly"""

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
        ), f"{implementation_class.__name__} missing implementation for {method_name}"

        # Get methods
        contract_method = getattr(contract_class, method_name)
        impl_method = getattr(implementation_class, method_name)

        # Verify signatures match
        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)

        # Get parameters (excluding 'self')
        contract_params = list(contract_sig.parameters.values())[1:]
        impl_params = list(impl_sig.parameters.values())[1:]

        # Check parameter count
        assert len(contract_params) == len(impl_params), (
            f"Parameter count mismatch for {method_name}: "
            f"contract has {len(contract_params)}, implementation has {len(impl_params)}"
        )

        # Check each parameter
        for c_param, i_param in zip(contract_params, impl_params, strict=False):
            assert (
                c_param.name == i_param.name
            ), f"Parameter name mismatch in {method_name}: {c_param.name} != {i_param.name}"
            assert c_param.annotation == i_param.annotation, (
                f"Parameter type mismatch in {method_name}.{c_param.name}: "
                f"{c_param.annotation} != {i_param.annotation}"
            )
            assert (
                c_param.default == i_param.default
            ), f"Default value mismatch in {method_name}.{c_param.name}"

        # Check return type annotation
        assert contract_sig.return_annotation == impl_sig.return_annotation, (
            f"Return type mismatch for {method_name}: "
            f"{contract_sig.return_annotation} != {impl_sig.return_annotation}"
        )


class TestContractCompliance:
    """Test that all implementations comply with their contracts"""

    def test_tooling_contract_compliance(self):
        """Verify DeveloperToolingStub matches contract"""
        verify_contract_compliance(DeveloperToolingContract, DeveloperToolingStub)

        # Test instantiation
        tooling = DeveloperToolingStub()
        assert isinstance(tooling, DeveloperToolingContract)

    def test_cicd_contract_compliance(self):
        """Verify CICDPipelineStub matches contract"""
        verify_contract_compliance(CICDPipelineContract, CICDPipelineStub)

        # Test instantiation
        cicd = CICDPipelineStub()
        assert isinstance(cicd, CICDPipelineContract)

    def test_debug_visualization_contract_compliance(self):
        """Verify DebugVisualizationStub matches contract"""
        verify_contract_compliance(DebugVisualizationContract, DebugVisualizationStub)

        # Test instantiation
        debug = DebugVisualizationStub()
        assert isinstance(debug, DebugVisualizationContract)

    def test_chunk_comparison_contract_compliance(self):
        """Verify ChunkComparisonStub matches contract"""
        verify_contract_compliance(ChunkComparisonContract, ChunkComparisonStub)

        # Test instantiation
        comparison = ChunkComparisonStub()
        assert isinstance(comparison, ChunkComparisonContract)

    def test_build_system_contract_compliance(self):
        """Verify BuildSystemStub matches contract"""
        verify_contract_compliance(BuildSystemContract, BuildSystemStub)

        # Test instantiation
        build = BuildSystemStub()
        assert isinstance(build, BuildSystemContract)

    def test_platform_support_contract_compliance(self):
        """Verify PlatformSupportStub matches contract"""
        verify_contract_compliance(PlatformSupportContract, PlatformSupportStub)

        # Test instantiation
        platform = PlatformSupportStub()
        assert isinstance(platform, PlatformSupportContract)

    def test_distribution_contract_compliance(self):
        """Verify DistributionStub matches contract"""
        verify_contract_compliance(DistributionContract, DistributionStub)

        # Test instantiation
        dist = DistributionStub()
        assert isinstance(dist, DistributionContract)

    def test_release_management_contract_compliance(self):
        """Verify ReleaseManagementStub matches contract"""
        verify_contract_compliance(ReleaseManagementContract, ReleaseManagementStub)

        # Test instantiation
        release = ReleaseManagementStub()
        assert isinstance(release, ReleaseManagementContract)

    def test_stub_return_types(self):
        """Verify stubs return correct types"""

        # Test tooling stub
        tooling = DeveloperToolingStub()
        result = tooling.run_pre_commit_checks([Path("test.py")])
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], dict)

        # Test CICD stub
        cicd = CICDPipelineStub()
        result = cicd.validate_workflow_syntax(Path(".github/workflows/test.yml"))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

        # Test build stub
        build = BuildSystemStub()
        result = build.compile_grammars(["python"], "linux", Path("build/"))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], dict)

        # Test distribution stub
        dist = DistributionStub()
        result = dist.publish_to_pypi(Path("dist/"))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], dict)

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
from chunker.contracts.tooling_contract import DeveloperToolingContract
from chunker.contracts.tooling_stub import DeveloperToolingStub


def verify_contract_compliance(contract_class, implementation_class):
    """Verify implementation matches contract exactly"""
    abstract_methods = []
    for name, method in inspect.getmembers(contract_class):
        if (
            hasattr(
                method,
                "__isabstractmethod__",
            )
            and method.__isabstractmethod__
        ):
            abstract_methods.append(name)
    for method_name in abstract_methods:
        assert hasattr(
            implementation_class,
            method_name,
        ), f"{implementation_class.__name__} missing implementation for {method_name}"
        contract_method = getattr(contract_class, method_name)
        impl_method = getattr(implementation_class, method_name)
        contract_sig = inspect.signature(contract_method)
        impl_sig = inspect.signature(impl_method)
        contract_params = list(contract_sig.parameters.values())[1:]
        impl_params = list(impl_sig.parameters.values())[1:]
        assert len(contract_params) == len(
            impl_params,
        ), f"Parameter count mismatch for {method_name}: contract has {len(contract_params)}, implementation has {len(impl_params)}"
        for c_param, i_param in zip(
            contract_params,
            impl_params,
            strict=False,
        ):
            assert (
                c_param.name == i_param.name
            ), f"Parameter name mismatch in {method_name}: {c_param.name} != {i_param.name}"
            assert (
                c_param.annotation == i_param.annotation
            ), f"Parameter type mismatch in {method_name}.{c_param.name}: {c_param.annotation} != {i_param.annotation}"
            assert (
                c_param.default == i_param.default
            ), f"Default value mismatch in {method_name}.{c_param.name}"
        assert (
            contract_sig.return_annotation == impl_sig.return_annotation
        ), f"Return type mismatch for {method_name}: {contract_sig.return_annotation} != {impl_sig.return_annotation}"


class TestContractCompliance:
    """Test that all implementations comply with their contracts"""

    @classmethod
    def test_tooling_contract_compliance(cls):
        """Verify DeveloperToolingStub matches contract"""
        verify_contract_compliance(DeveloperToolingContract, DeveloperToolingStub)
        tooling = DeveloperToolingStub()
        assert isinstance(tooling, DeveloperToolingContract)

    @classmethod
    def test_cicd_contract_compliance(cls):
        """Verify CICDPipelineStub matches contract"""
        verify_contract_compliance(CICDPipelineContract, CICDPipelineStub)
        cicd = CICDPipelineStub()
        assert isinstance(cicd, CICDPipelineContract)

    @classmethod
    def test_debug_visualization_contract_compliance(cls):
        """Verify DebugVisualizationStub matches contract"""
        verify_contract_compliance(DebugVisualizationContract, DebugVisualizationStub)
        debug = DebugVisualizationStub()
        assert isinstance(debug, DebugVisualizationContract)

    @classmethod
    def test_chunk_comparison_contract_compliance(cls):
        """Verify ChunkComparisonStub matches contract"""
        verify_contract_compliance(
            ChunkComparisonContract,
            ChunkComparisonStub,
        )
        comparison = ChunkComparisonStub()
        assert isinstance(comparison, ChunkComparisonContract)

    @classmethod
    def test_build_system_contract_compliance(cls):
        """Verify BuildSystemStub matches contract"""
        verify_contract_compliance(BuildSystemContract, BuildSystemStub)
        build = BuildSystemStub()
        assert isinstance(build, BuildSystemContract)

    @classmethod
    def test_platform_support_contract_compliance(cls):
        """Verify PlatformSupportStub matches contract"""
        verify_contract_compliance(
            PlatformSupportContract,
            PlatformSupportStub,
        )
        platform = PlatformSupportStub()
        assert isinstance(platform, PlatformSupportContract)

    @classmethod
    def test_distribution_contract_compliance(cls):
        """Verify DistributionStub matches contract"""
        verify_contract_compliance(DistributionContract, DistributionStub)
        dist = DistributionStub()
        assert isinstance(dist, DistributionContract)

    @classmethod
    def test_release_management_contract_compliance(cls):
        """Verify ReleaseManagementStub matches contract"""
        verify_contract_compliance(ReleaseManagementContract, ReleaseManagementStub)
        release = ReleaseManagementStub()
        assert isinstance(release, ReleaseManagementContract)

    @classmethod
    def test_stub_return_types(cls):
        """Verify stubs return correct types"""
        tooling = DeveloperToolingStub()
        result = tooling.run_pre_commit_checks([Path("test.py")])
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], dict)
        cicd = CICDPipelineStub()
        result = cicd.validate_workflow_syntax(Path(".github/workflows/test.yml"))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)
        build = BuildSystemStub()
        result = build.compile_grammars(["python"], "linux", Path("build/"))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], dict)
        dist = DistributionStub()
        result = dist.publish_to_pypi(Path("dist/"))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], dict)

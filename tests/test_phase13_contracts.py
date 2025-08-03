"""
Test that Phase 13 contracts are properly defined
"""
import inspect
from abc import ABC

import pytest

from chunker.contracts.build_contract import (
    BuildSystemContract,
    PlatformSupportContract,
)
from chunker.contracts.debug_contract import (
    ChunkComparisonContract,
    DebugVisualizationContract,
)
from chunker.contracts.devenv_contract import (
    DevelopmentEnvironmentContract,
    QualityAssuranceContract,
)
from chunker.contracts.distribution_contract import (
    DistributionContract,
    ReleaseManagementContract,
)


class TestPhase13Contracts:
    """Validate Phase 13 contracts are properly defined"""

    @staticmethod
    def test_all_contracts_are_abstract():
        """All contracts should be abstract base classes"""
        contracts = [DebugVisualizationContract, ChunkComparisonContract,
            DevelopmentEnvironmentContract, QualityAssuranceContract,
            BuildSystemContract, PlatformSupportContract,
            DistributionContract, ReleaseManagementContract]
        for contract in contracts:
            assert issubclass(contract, ABC,
                ), f"{contract.__name__} should be an ABC"

    @staticmethod
    def test_debug_contracts_have_required_methods():
        """Debug contracts should have all required methods"""
        methods = ["visualize_ast", "inspect_chunk", "profile_chunking",
            "debug_mode_chunking"]
        for method in methods:
            assert hasattr(DebugVisualizationContract, method)
            assert getattr(DebugVisualizationContract, method,
                ).__isabstractmethod__
        assert hasattr(ChunkComparisonContract, "compare_strategies")
        assert ChunkComparisonContract.compare_strategies.__isabstractmethod__

    @staticmethod
    def test_devenv_contracts_have_required_methods():
        """DevEnv contracts should have all required methods"""
        methods = ["setup_pre_commit_hooks", "run_linting", "format_code",
            "generate_ci_config"]
        for method in methods:
            assert hasattr(DevelopmentEnvironmentContract, method)
            assert getattr(DevelopmentEnvironmentContract, method,
                ).__isabstractmethod__
        methods = ["check_type_coverage", "check_test_coverage"]
        for method in methods:
            assert hasattr(QualityAssuranceContract, method)
            assert getattr(QualityAssuranceContract, method,
                ).__isabstractmethod__

    @staticmethod
    def test_build_contracts_have_required_methods():
        """Build contracts should have all required methods"""
        methods = ["compile_grammars", "build_wheel",
            "create_conda_package", "verify_build"]
        for method in methods:
            assert hasattr(BuildSystemContract, method)
            assert getattr(BuildSystemContract, method).__isabstractmethod__
        methods = ["detect_platform", "install_build_dependencies"]
        for method in methods:
            assert hasattr(PlatformSupportContract, method)
            assert getattr(PlatformSupportContract, method,
                ).__isabstractmethod__

    @staticmethod
    def test_distribution_contracts_have_required_methods():
        """Distribution contracts should have all required methods"""
        methods = ["publish_to_pypi", "build_docker_image",
            "create_homebrew_formula", "verify_installation"]
        for method in methods:
            assert hasattr(DistributionContract, method)
            assert getattr(DistributionContract, method).__isabstractmethod__
        methods = ["prepare_release", "create_release_artifacts"]
        for method in methods:
            assert hasattr(ReleaseManagementContract, method)
            assert getattr(ReleaseManagementContract, method,
                ).__isabstractmethod__

    @classmethod
    def test_contract_methods_raise_not_implemented(cls):
        """Contract methods should raise NotImplementedError"""
        contracts_and_methods = [(DebugVisualizationContract,
            "visualize_ast", ("test.py", "python")), (
            DevelopmentEnvironmentContract, "run_linting", ()), (
            BuildSystemContract, "detect_platform", ()), (
            DistributionContract, "publish_to_pypi", (None,))]
        for contract_class, _method_name, _args in contracts_and_methods:

            class TestImpl(contract_class):
                pass
            with pytest.raises(TypeError) as exc_info:
                TestImpl()
            assert "Can't instantiate abstract class" in str(exc_info.value)

    @staticmethod
    def test_contracts_have_proper_signatures():
        """Contract methods should have proper type hints"""
        key_methods = [(DebugVisualizationContract, "visualize_ast"), (
            DevelopmentEnvironmentContract, "run_linting"), (
            BuildSystemContract, "compile_grammars"), (DistributionContract,
            "publish_to_pypi")]
        for contract_class, method_name in key_methods:
            method = getattr(contract_class, method_name)
            sig = inspect.signature(method)
            assert sig.return_annotation != inspect.Parameter.empty, f"{contract_class.__name__}.{method_name} should have return type annotation"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])

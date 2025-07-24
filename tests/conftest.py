"""
Test configuration and fixtures for phase13 tests
"""

import pytest

from chunker.build import BuildSystem, PlatformSupport


@pytest.fixture()
def build_system():
    """Provide real BuildSystem instance"""
    return BuildSystem()


@pytest.fixture()
def platform_support():
    """Provide real PlatformSupport instance"""
    return PlatformSupport()


# Monkey-patch the integration tests to use real implementations
def pytest_runtest_setup(item):
    """Setup test to use real implementations instead of mocks"""
    if "test_phase13_integration" in str(item.fspath):
        # Import here to avoid circular imports

        from chunker.build import BuildSystem, PlatformSupport

        # Patch Mock to return real instances for our contracts
        original_mock = (
            item.session.config._mock_class
            if hasattr(item.session.config, "_mock_class")
            else None
        )

        def mock_side_effect(*args, **kwargs):
            # Check if we're mocking one of our contracts
            if args and hasattr(args[0], "__name__"):
                class_name = (
                    args[0].__name__ if hasattr(args[0], "__name__") else str(args[0])
                )

                if "BuildSystemContract" in class_name:
                    return BuildSystem()
                if "PlatformSupportContract" in class_name:
                    return PlatformSupport()

            # Otherwise use original Mock
            if original_mock:
                return original_mock(*args, **kwargs)

            from unittest.mock import Mock

            return Mock(*args, **kwargs)

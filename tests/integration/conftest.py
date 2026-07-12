"""Pytest configuration for integration tests."""

# Load the integration fixtures as a pytest plugin instead of star-importing them.
pytest_plugins = ["tests.integration.fixtures"]

"""Shared test fixtures and configuration for servicegraph tests."""

import json
import os
import tempfile

import pytest

from servicegraph import ApplicationBuilder, IConfiguration


@pytest.fixture
def temp_config_file():
    """Create a temporary JSON configuration file for testing."""
    config_data = {
        "database": {"host": "localhost", "port": 5432, "name": "test_db"},
        "api": {"base_url": "https://api.test.com", "timeout": 30},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_file = f.name

    yield temp_file

    # Cleanup
    os.unlink(temp_file)


@pytest.fixture
def basic_app_builder():
    """Create a basic ApplicationBuilder for testing."""
    builder = ApplicationBuilder()

    # Add basic configuration using a temporary JSON file
    def setup_config(config_builder):
        import json
        import os
        import tempfile

        # Create temporary config file
        config_data = {"test": {"environment": "testing", "debug": True}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            config_builder.add_json_file(temp_file)
        finally:
            # Clean up temp file
            os.unlink(temp_file)

        return config_builder

    builder.configure_configuration(setup_config)
    return builder


@pytest.fixture
def configured_provider(basic_app_builder):
    """Create a configured ServiceProvider for testing."""

    # Add some basic services
    class ITestService:
        def get_value(self) -> str:
            pass

    class TestService:
        def __init__(self, config: IConfiguration):
            self.config = config

        def get_value(self) -> str:
            return "test_value"

    basic_app_builder.services.add_singleton(ITestService, TestService)

    return basic_app_builder.build()


class MockAzureFunction:
    """Mock Azure Function context for testing."""

    def __init__(self, method="GET", url="http://localhost", headers=None, params=None):
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.params = params or {}


@pytest.fixture
def mock_azure_context():
    """Create mock Azure Functions context."""
    return MockAzureFunction()


@pytest.fixture
def cleanup_environment():
    """Fixture to clean up environment variables after tests."""
    original_env = dict(os.environ)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Marks for test organization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.azure = pytest.mark.azure


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "azure: mark test as Azure Functions related")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their file location."""
    for item in items:
        # Mark tests based on filename
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        elif "azure" in item.nodeid:
            item.add_marker(pytest.mark.azure)
        elif "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

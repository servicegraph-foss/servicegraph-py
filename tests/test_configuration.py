"""Configuration system tests."""

import json
import os
import tempfile
from dataclasses import dataclass

import pytest

from servicegraph import ApplicationBuilder, ConfigurationBuilder, IConfiguration

# ========================
# Module-level types for testing
# ========================


class AppSettings:
    """Test settings class for bind() tests."""

    def __init__(self):
        self.host = None
        self.port = None
        self.debug = None


@dataclass
class DatabaseSettings:
    """Test dataclass for typed configuration."""

    host: str
    port: int
    database_name: str


# ========================
# Test Fixtures
# ========================


@pytest.fixture(autouse=True)
def reset_service_provider():
    """
    Reset the ServiceProvider state before each test.
    Note: ServiceProvider is a singleton by design - only one exists
    per runtime. We clear its state rather than trying to recreate it.
    """
    from servicegraph.service_provider import ServiceProvider

    # Clear before test
    if ServiceProvider._instance is not None:
        # Clear all cached instances
        ServiceProvider._instance.clear_all_instances()
        # Clear all service registrations
        ServiceProvider._instance._collection.clear()

    yield

    # Don't clear after - the next test will clear before it runs
    # Clearing after would wipe out the next test's collection since
    # ServiceProvider always updates its _collection reference


class TestConfigurationSystem:
    """Test configuration management functionality."""

    def test_basic_configuration_setup(self):
        """Test basic configuration initialization."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            import os

            os.environ["TEST_KEY"] = "test_value"
            os.environ["NESTED__KEY"] = "nested_value"
            config_builder.add_environment_variables("")
            return config_builder

        builder.configure_configuration(setup_config)
        provider = builder.build()

        config = provider.get_service(IConfiguration)
        assert config.get_value("TEST_KEY") == "test_value"
        assert config.get_value("NESTED:KEY") == "nested_value"

    def test_json_file_configuration(self):
        """Test loading configuration from JSON file."""
        # Create temporary JSON configuration file
        config_data = {
            "api": {
                "base_url": "https://api.example.com",
                "timeout": 30,
                "retry_count": 3,
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            builder = ApplicationBuilder()

            def setup_config(config_builder):
                config_builder.add_json_file(temp_file, optional=False)
                return config_builder

            builder.configure_configuration(setup_config)
            provider = builder.build()

            config = provider.get_service(IConfiguration)

            assert config.get_value("api:base_url") == "https://api.example.com"
            assert config.get_value("api:timeout") == 30  # Returns int from JSON
            assert config.get_value("logging:level") == "INFO"

        finally:
            os.unlink(temp_file)

    def test_environment_variables_configuration(self):
        """Test configuration from environment variables."""
        # Set test environment variables
        test_env_vars = {
            "TEST_API_URL": "https://test.example.com",
            "TEST_DATABASE_NAME": "test_db",
            "TEST_FEATURE_ENABLED": "true",
        }

        # Store original values to restore later
        original_values = {}
        for key in test_env_vars:
            original_values[key] = os.environ.get(key)
            os.environ[key] = test_env_vars[key]

        try:
            builder = ApplicationBuilder()

            def setup_config(config_builder):
                config_builder.add_environment_variables("TEST_")
                return config_builder

            builder.configure_configuration(setup_config)
            provider = builder.build()

            config = provider.get_service(IConfiguration)

            assert config.get_value("API_URL") == "https://test.example.com"
            assert config.get_value("DATABASE_NAME") == "test_db"
            assert config.get_value("FEATURE_ENABLED") == "true"

        finally:
            # Restore original environment
            for key, original_value in original_values.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    def test_configuration_hierarchy(self):
        """Test configuration source precedence."""
        # Create base configuration file
        base_config = {
            "database": {"host": "localhost", "port": 5432, "name": "base_db"},
            "feature_flag": False,
        }

        # Create environment-specific configuration file
        env_config = {
            "database": {
                "host": "prod-server",
                "name": "prod_db",
                # port should be inherited from base
            },
            "feature_flag": True,
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as base_file:
            json.dump(base_config, base_file)
            base_filename = base_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as env_file:
            json.dump(env_config, env_file)
            env_filename = env_file.name

        # Set environment variable that should override everything
        # Use double underscore __ for nested configuration keys
        os.environ["APP_DATABASE__PORT"] = "3306"

        try:
            builder = ApplicationBuilder()

            def setup_config(config_builder):
                # Add in order of precedence (lowest to highest)
                config_builder.add_json_file(base_filename, optional=False)
                config_builder.add_json_file(env_filename, optional=False)
                config_builder.add_environment_variables("APP_")
                return config_builder

            builder.configure_configuration(setup_config)
            provider = builder.build()

            config = provider.get_service(IConfiguration)

            # Should use environment-specific host
            assert config.get_value("database:host") == "prod-server"

            # Should use environment-specific database name
            assert config.get_value("database:name") == "prod_db"

            # Should use environment variable port (overrides everything)
            assert config.get_value("database:port") == "3306"  # String from env var

            # Should use environment-specific feature flag
            assert config.get_value("feature_flag") is True  # Boolean from JSON

        finally:
            os.unlink(base_filename)
            os.unlink(env_filename)
            os.environ.pop("APP_DATABASE__PORT", None)

    def test_optional_configuration_files(self):
        """Test handling of optional configuration files."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            # This file doesn't exist, but it's optional
            config_builder.add_json_file("nonexistent.json", optional=True)

            # Add some actual configuration via environment
            import os

            os.environ["TEST"] = "value"
            config_builder.add_environment_variables("")
            return config_builder

        builder.configure_configuration(setup_config)
        provider = builder.build()

        config = provider.get_service(IConfiguration)
        assert config.get_value("test") == "value"

    def test_required_configuration_file_missing(self):
        """Test error handling for missing required configuration files."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            # This file doesn't exist and is required
            config_builder.add_json_file("required_but_missing.json", optional=False)
            return config_builder

        # Should raise an exception when configuring (not building)
        with pytest.raises(FileNotFoundError):
            builder.configure_configuration(setup_config)

    def test_configuration_sections(self):
        """Test configuration section functionality."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            import os

            os.environ["DATABASE__CONNECTION_STRING"] = "server=localhost;database=test"
            os.environ["DATABASE__TIMEOUT"] = "30"
            os.environ["DATABASE__POOL_SIZE"] = "10"
            os.environ["LOGGING__LEVEL"] = "DEBUG"
            config_builder.add_environment_variables("")
            return config_builder

        builder.configure_configuration(setup_config)
        provider = builder.build()

        config = provider.get_service(IConfiguration)

        # Get section
        db_section = config.get_section("database")
        assert (
            db_section.get_value("connection_string")
            == "server=localhost;database=test"
        )
        assert db_section.get_value("timeout") == "30"  # String from env var

        # Get nested section
        logging_section = config.get_section("logging")
        assert logging_section.get_value("level") == "DEBUG"

    def test_configuration_bind_to_instance(self):
        """Test binding configuration to an existing object instance."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            import os

            os.environ["APP__HOST"] = "localhost"
            os.environ["APP__PORT"] = "8080"
            os.environ["APP__DEBUG"] = "true"
            config_builder.add_environment_variables("")
            return config_builder

        builder.configure_configuration(setup_config)
        provider = builder.build()

        config = provider.get_service(IConfiguration)

        # Create an instance to bind to (using module-level class)
        settings = AppSettings()
        config.bind(settings, "app")

        assert settings.host == "localhost"
        assert settings.port == "8080"
        assert settings.debug == "true"

    def test_configuration_get_typed_object(self):
        """Test getting strongly-typed configuration objects."""
        config_data = {
            "database": {
                "host": "db-server",
                "port": 5432,
                "database_name": "production",
            }
        }

        # Create configuration directly for this test (using module-level dataclass)
        from servicegraph.configuration import Configuration

        config = Configuration(config_data)

        # Get typed object from configuration
        db_settings = config.get(DatabaseSettings, "database")

        assert db_settings.host == "db-server"
        assert db_settings.port == 5432
        assert db_settings.database_name == "production"

    def test_configuration_update(self):
        """Test updating configuration with new data."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            import os

            os.environ["INITIAL"] = "value1"
            config_builder.add_environment_variables("")
            return config_builder

        builder.configure_configuration(setup_config)
        provider = builder.build()

        config = provider.get_service(IConfiguration)

        assert config.get_value("INITIAL") == "value1"

        # Update configuration
        config.update({"new_key": "new_value", "INITIAL": "updated_value"})

        assert config.get_value("new_key") == "new_value"
        assert config.get_value("INITIAL") == "updated_value"

    def test_configuration_remove_value(self):
        """Test removing configuration values."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            import os

            os.environ["KEY_TO_REMOVE"] = "will_be_removed"
            os.environ["KEY_TO_KEEP"] = "will_stay"
            config_builder.add_environment_variables("")
            return config_builder

        builder.configure_configuration(setup_config)
        provider = builder.build()

        config = provider.get_service(IConfiguration)

        assert config.get_value("KEY_TO_REMOVE") == "will_be_removed"

        # Remove the value
        removed = config.remove_value("KEY_TO_REMOVE")
        assert removed is True

        # Verify it's gone
        assert config.get_value("KEY_TO_REMOVE") is None
        assert config.get_value("KEY_TO_KEEP") == "will_stay"

        # Try removing non-existent key
        removed_again = config.remove_value("KEY_TO_REMOVE")
        assert removed_again is False

    def test_configuration_clear(self):
        """Test clearing all configuration data."""
        builder = ApplicationBuilder()

        def setup_config(config_builder):
            import os

            os.environ["KEY1"] = "value1"
            os.environ["KEY2"] = "value2"
            config_builder.add_environment_variables("")
            return config_builder

        builder.configure_configuration(setup_config)
        provider = builder.build()

        config = provider.get_service(IConfiguration)

        assert config.get_value("KEY1") == "value1"
        assert config.get_value("KEY2") == "value2"

        # Clear all configuration
        config.clear()

        # Verify everything is gone
        assert config.get_value("KEY1") is None
        assert config.get_value("KEY2") is None


class TestConfigurationBuilder:
    """Test ConfigurationBuilder functionality."""

    def test_fluent_configuration_building(self):
        """Test fluent interface for configuration building."""
        import json
        import os
        import tempfile

        # Create temp JSON file for testing fluent interface
        config_data = {"base": "value"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            # Set up environment override
            os.environ["OVERRIDE"] = "new_value"

            config_builder = ConfigurationBuilder()
            config = (
                config_builder.add_json_file(temp_file)
                .add_environment_variables("")
                .build()
            )

            assert config.get_value("base") == "value"
            assert config.get_value("OVERRIDE") == "new_value"
        finally:
            os.unlink(temp_file)
            os.environ.pop("OVERRIDE", None)

    def test_configuration_validation(self):
        """Test configuration validation and error handling."""
        config_builder = ConfigurationBuilder()

        # Test invalid JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content {")
            invalid_json_file = f.name

        try:
            # Should raise JSON parsing error when adding invalid file
            with pytest.raises(ValueError):
                config_builder.add_json_file(invalid_json_file, optional=False)

        finally:
            os.unlink(invalid_json_file)


if __name__ == "__main__":
    pytest.main([__file__])

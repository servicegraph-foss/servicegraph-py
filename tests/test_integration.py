"""Integration tests for complete servicegraph workflows."""

import json
import os
import tempfile
from abc import ABC, abstractmethod

import pytest

from servicegraph import ApplicationBuilder, IConfiguration
from servicegraph.service_lifetime import ServiceLifetime

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


# ========================
# Module-Level Service Interfaces and Implementations
# ========================


# Email Service
class IEmailService(ABC):
    """Email service interface."""

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email."""
        pass


class EmailService(IEmailService):
    """Email service implementation."""

    def __init__(self, config: IConfiguration):
        self.config = config
        self.sent_emails = []

    def send_email(self, to: str, subject: str, body: str) -> bool:
        smtp_server = self.config.get_value("email:smtp_server")
        self.sent_emails.append(
            {"to": to, "subject": subject, "body": body, "server": smtp_server}
        )
        return True


# User Repository
class IUserRepository(ABC):
    """User repository interface."""

    @abstractmethod
    def get_user(self, user_id: str) -> dict:
        """Get user by ID."""
        pass

    @abstractmethod
    def save_user(self, user: dict) -> bool:
        """Save user."""
        pass


class UserRepository(IUserRepository):
    """User repository implementation."""

    def __init__(self, config: IConfiguration):
        self.config = config
        self.users = {}  # In-memory store for testing

    def get_user(self, user_id: str) -> dict:
        default_user = {"id": user_id, "name": f"User {user_id}"}
        return self.users.get(user_id, default_user)

    def save_user(self, user: dict) -> bool:
        self.users[user["id"]] = user
        return True


# User Service
class UserService:
    """User service for handling user operations."""

    def __init__(self, user_repo: IUserRepository, email_service: IEmailService):
        self.user_repo = user_repo
        self.email_service = email_service

    def register_user(self, user_id: str, email: str, name: str) -> dict:
        user = {"id": user_id, "email": email, "name": name, "status": "active"}

        self.user_repo.save_user(user)

        # Send welcome email
        self.email_service.send_email(
            to=email, subject="Welcome!", body=f"Welcome {name}! Your account is ready."
        )

        return user


# Tenant Service
class ITenantService(ABC):
    """Tenant service interface."""

    @abstractmethod
    def get_tenant_data(self) -> dict:
        """Get tenant-specific data."""
        pass


class TenantService(ITenantService):
    """Tenant service implementation."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.data = f"data_for_{tenant_id}"

    def get_tenant_data(self) -> dict:
        return {"tenant_id": self.tenant_id, "data": self.data}


# Database and API Services for Configuration Integration
class DatabaseService:
    """Database service using configuration."""

    def __init__(self, config: IConfiguration):
        self.host = config.get_value("database:host")
        self.port = int(config.get_value("database:port"))
        self.name = config.get_value("database:name")
        self.ssl = config.get_value("database:ssl")

    def get_connection_string(self):
        protocol = "sslmode=require" if self.ssl else "sslmode=disable"
        return f"host={self.host} port={self.port} dbname={self.name} {protocol}"


class ApiService:
    """API service using configuration."""

    def __init__(self, config: IConfiguration):
        self.timeout = int(config.get_value("api:timeout"))
        self.retries = int(config.get_value("api:retries"))


# Database Connection for Scoped Service Testing
class IDatabaseConnection(ABC):
    """Database connection interface."""

    @abstractmethod
    def execute_query(self, query: str) -> list:
        """Execute a database query."""
        pass

    @abstractmethod
    def close(self):
        """Close the database connection."""
        pass


class DatabaseConnection(IDatabaseConnection):
    """Database connection implementation with resource tracking."""

    # Class-level tracking for testing
    connection_pool = []
    closed_connections = []

    def __init__(self, config: IConfiguration):
        self.config = config
        self.connection_id = len(DatabaseConnection.connection_pool)
        self.is_closed = False
        DatabaseConnection.connection_pool.append(self)

    def execute_query(self, query: str) -> list:
        if self.is_closed:
            raise RuntimeError("Connection is closed")
        return [f"result_{self.connection_id}_{query}"]

    def close(self):
        if not self.is_closed:
            self.is_closed = True
            DatabaseConnection.closed_connections.append(self.connection_id)

    @classmethod
    def reset_tracking(cls):
        """Reset class-level tracking for tests."""
        cls.connection_pool = []
        cls.closed_connections = []


class DataService:
    """Data service that uses a database connection."""

    def __init__(self, db_connection: IDatabaseConnection):
        self.db_connection = db_connection

    def get_data(self, table: str) -> list:
        return self.db_connection.execute_query(f"SELECT * FROM {table}")


@pytest.mark.integration
class TestCompleteWorkflows:
    """Test complete end-to-end workflows."""

    def test_full_application_lifecycle(self):
        """Test complete application setup, usage, and teardown."""
        # Create configuration file
        config_data = {
            "email": {"smtp_server": "smtp.example.com", "port": 587},
            "database": {"connection_string": "test_connection"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Configure application
            builder = ApplicationBuilder()

            # Setup configuration
            def setup_config(config_builder):
                import os

                config_builder.add_json_file(config_file, optional=False)
                # Add app configuration via environment
                os.environ["APP__NAME"] = "TestApp"
                os.environ["APP__VERSION"] = "1.0.0"
                config_builder.add_environment_variables("APP__")
                return config_builder

            builder.configure_configuration(setup_config)

            # Register services
            builder.services.add_singleton(IEmailService, EmailService)
            builder.services.add_singleton(IUserRepository, UserRepository)
            builder.services.add_singleton(UserService)

            # Build application
            provider = builder.build()

            # Use application
            user_service = provider.get_service(UserService)
            email_service = provider.get_service(IEmailService)

            # Register a user
            user = user_service.register_user(
                user_id="123", email="test@example.com", name="John Doe"
            )

            # Verify results
            assert user["id"] == "123"
            assert user["name"] == "John Doe"
            assert user["status"] == "active"

            # Verify email was sent
            assert len(email_service.sent_emails) == 1
            sent_email = email_service.sent_emails[0]
            assert sent_email["to"] == "test@example.com"
            assert sent_email["subject"] == "Welcome!"
            assert sent_email["server"] == "smtp.example.com"

            # Verify user was saved
            user_repo = provider.get_service(IUserRepository)
            saved_user = user_repo.get_user("123")
            assert saved_user["name"] == "John Doe"

        finally:
            os.unlink(config_file)

    def test_multi_tenant_application(self):
        """Test application with multi-tenant service isolation."""
        builder = ApplicationBuilder()

        # Register tenant-specific services using add_named
        builder.services.add_named(
            "tenant_a", ITenantService, TenantService, ServiceLifetime.SINGLETON
        )
        builder.services.add_named(
            "tenant_b", ITenantService, TenantService, ServiceLifetime.SINGLETON
        )

        # Note: Since TenantService requires tenant_id in __init__, we need factories
        # Override with proper factories
        builder.services.add_named_factory(
            "tenant_a", ITenantService, lambda p: TenantService("tenant_a")
        )
        builder.services.add_named_factory(
            "tenant_b", ITenantService, lambda p: TenantService("tenant_b")
        )

        provider = builder.build()

        # Test tenant isolation
        tenant_a_service = provider.get_named_service(ITenantService, "tenant_a")
        tenant_b_service = provider.get_named_service(ITenantService, "tenant_b")

        tenant_a_data = tenant_a_service.get_tenant_data()
        tenant_b_data = tenant_b_service.get_tenant_data()

        assert tenant_a_data["tenant_id"] == "tenant_a"
        assert tenant_b_data["tenant_id"] == "tenant_b"
        assert tenant_a_data["data"] != tenant_b_data["data"]
        assert tenant_a_service is not tenant_b_service

    def test_configuration_hierarchy_integration(self):
        """Test complete configuration hierarchy with environment overrides."""
        # Create base configuration
        base_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "base_db",
                "ssl": False,
            },
            "api": {"timeout": 30, "retries": 3},
        }

        # Create environment configuration
        env_config = {
            "database": {"host": "prod-server", "ssl": True},
            "api": {"timeout": 60},
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

        # Set environment variable for highest priority
        os.environ["APP_DATABASE__PORT"] = "3306"
        os.environ["APP_API__RETRIES"] = "5"

        try:
            builder = ApplicationBuilder()

            def setup_config(config_builder):
                config_builder.add_json_file(base_filename, optional=False)
                config_builder.add_json_file(env_filename, optional=False)
                config_builder.add_environment_variables("APP_")
                return config_builder

            builder.configure_configuration(setup_config)

            # Register services that use configuration
            builder.services.add_singleton(DatabaseService)
            builder.services.add_singleton(ApiService)

            provider = builder.build()

            # Test configuration hierarchy
            db_service = provider.get_service(DatabaseService)
            api_service = provider.get_service(ApiService)

            # Database config: host from env, port from env var, name from base, ssl from env
            assert db_service.host == "prod-server"  # From env config
            assert db_service.port == 3306  # From environment variable
            assert db_service.name == "base_db"  # From base config
            assert db_service.ssl is True  # From env config

            # API config: timeout from env, retries from environment variable
            assert api_service.timeout == 60  # From env config
            assert api_service.retries == 5  # From environment variable

            # Test connection string generation
            conn_str = db_service.get_connection_string()
            assert "host=prod-server" in conn_str
            assert "port=3306" in conn_str
            assert "sslmode=require" in conn_str

        finally:
            os.unlink(base_filename)
            os.unlink(env_filename)
            os.environ.pop("APP_DATABASE__PORT", None)
            os.environ.pop("APP_API__RETRIES", None)

    def test_scoped_service_with_resource_management(self):
        """Test scoped services with proper resource management."""
        # Reset connection tracking
        DatabaseConnection.reset_tracking()

        builder = ApplicationBuilder()

        def setup_config(config_builder):
            import os

            os.environ["DATABASE__CONNECTION_STRING"] = "test_connection"
            config_builder.add_environment_variables("DATABASE__")
            return config_builder

        builder.configure_configuration(setup_config)
        builder.services.add_scoped(IDatabaseConnection, DatabaseConnection)
        builder.services.add_scoped(DataService)

        provider = builder.build()

        # Test multiple scopes
        results = []
        connection_ids_used = []

        for i in range(3):
            with provider.get_service(DataService) as data_service:
                result = data_service.get_data(f"table_{i}")
                # Extract connection ID from the result instead of accessing the attribute
                # Result format: [f"result_{connection_id}_SELECT * FROM table_{i}"]
                result_str = result[0]
                # Parse: "result_0_SELECT * FROM table_0" -> connection_id is 0
                conn_id = int(result_str.split("_")[1])
                results.append((i, result, conn_id))
                connection_ids_used.append(conn_id)

        # Verify each scope had its own connection
        assert len(set(connection_ids_used)) == 3  # All different connections

        # Verify all connections were properly closed
        assert len(DatabaseConnection.closed_connections) == 3
        assert set(DatabaseConnection.closed_connections) == set(connection_ids_used)

        # Verify results were generated correctly
        for i, result, conn_id in results:
            expected_result = f"result_{conn_id}_SELECT * FROM table_{i}"
            assert result == [expected_result]


if __name__ == "__main__":
    pytest.main([__file__])

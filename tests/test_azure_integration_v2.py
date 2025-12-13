"""Azure Functions integration tests - properly designed for singleton."""

import os
from abc import ABC, abstractmethod
from typing import Annotated
from unittest.mock import Mock

import pytest

from servicegraph import ApplicationBuilder, IConfiguration
from servicegraph.dependency_injection_utils import Named
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
# Mock Azure Types (Module Level)
# ========================


class MockHttpRequest:
    """Mock Azure Functions HTTP request."""

    def __init__(
        self, method="GET", url="http://localhost", headers=None, params=None, body=None
    ):
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.params = params or {}
        self.body = body


class MockHttpResponse:
    """Mock Azure Functions HTTP response."""

    def __init__(self, body="", status_code=200, headers=None):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {}


# ========================
# Service Injection Test Services (Module Level)
# ========================


class IEmailServiceAzure(ABC):
    """Email service interface for Azure Functions."""

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email."""
        pass


class EmailServiceAzure(IEmailServiceAzure):
    """Azure email service implementation."""

    def __init__(self, config: IConfiguration):
        self.config = config
        self.sent_emails = []

    def send_email(self, to: str, subject: str, body: str) -> bool:
        # Mock email sending
        email = {"to": to, "subject": subject, "body": body}
        self.sent_emails.append(email)
        return True


class IUserServiceAzure(ABC):
    """User service interface for Azure Functions."""

    @abstractmethod
    def get_user(self, user_id: str) -> dict:
        """Get user by ID."""
        pass


class UserServiceAzure(IUserServiceAzure):
    """Azure user service implementation."""

    def __init__(
        self, email_service: Annotated[IEmailServiceAzure, Named("azure_email_service")]
    ):
        self.email_service = email_service

    def get_user(self, user_id: str) -> dict:
        return {"id": user_id, "name": f"User {user_id}"}


# ========================
# Middleware Pipeline Test Services (Module Level)
# ========================


class LoggingMiddlewareAzure:
    """Logging middleware for Azure Functions."""

    def __init__(self, config: IConfiguration):
        self.config = config
        self.logs = []

    def process_request(self, request):
        self.logs.append(f"Request: {request.method} {request.url}")
        return request

    def process_response(self, response):
        self.logs.append(f"Response: {response.status_code}")
        return response


class AuthenticationMiddlewareAzure:
    """Authentication middleware for Azure Functions."""

    def __init__(self):
        self.authenticated_users = []

    def process_request(self, request):
        # Mock authentication
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            user_id = auth_header.replace("Bearer ", "")
            self.authenticated_users.append(user_id)
            request.user_id = user_id
        else:
            raise Exception("Unauthorized")
        return request

    def process_response(self, response):
        return response


# ========================
# Performance Test Services (Module Level)
# ========================


class ExpensiveServiceAzure:
    """Expensive service to test singleton optimization."""

    def __init__(self):
        self.initialization_cost = "expensive_operation_completed"
        self.instance_id = id(self)


class RequestServiceAzure:
    """Per-request service for testing transient lifetime."""

    def __init__(
        self,
        expensive_service: Annotated[
            ExpensiveServiceAzure, Named("azure_expensive_service")
        ],
    ):
        self.expensive_service = expensive_service
        self.request_id = None
        self.instance_id = id(self)

    def set_request_id(self, request_id: str):
        self.request_id = request_id


# ========================
# Cold Start Test Services (Module Level)
# ========================

# Global counter to track initialization calls across tests
cold_start_initialization_calls = []


class ColdStartOptimizedServiceAzure:
    """Service to test cold start optimization."""

    def __init__(self):
        cold_start_initialization_calls.append("service_initialized")
        self.ready = True


# ========================
# Test Classes
# ========================


class TestAzureFunctionsIntegration:
    """Test servicegraph integration with Azure Functions."""

    def test_azure_function_service_injection(self):
        """Test service injection in Azure Functions context."""
        # Mock Azure Functions types
        azure_func = Mock()
        azure_func.HttpRequest = MockHttpRequest
        azure_func.HttpResponse = MockHttpResponse

        # Configure application for Azure Functions
        def create_app():
            builder = ApplicationBuilder()

            # Configure services with named registrations
            builder.services.add_named(
                "azure_email_service",
                IEmailServiceAzure,
                EmailServiceAzure,
                ServiceLifetime.SINGLETON,
            )
            builder.services.add_named(
                "azure_user_service",
                IUserServiceAzure,
                UserServiceAzure,
                ServiceLifetime.SINGLETON,
            )

            # Configure configuration
            def setup_config(config_builder):
                # Set up test environment variables
                os.environ["EMAIL__SMTP_SERVER"] = "smtp.azure.com"
                os.environ["EMAIL__PORT"] = "587"
                config_builder.add_environment_variables("EMAIL__")
                return config_builder

            builder.configure_configuration(setup_config)

            return builder.build()

        # Initialize app provider (would be done once in Azure Function)
        app_provider = create_app()

        # Simulate Azure Function handler
        def azure_function_handler(req: MockHttpRequest) -> MockHttpResponse:
            # Get services from DI container
            user_service = app_provider.get_named_service(
                IUserServiceAzure, "azure_user_service"
            )
            email_service = app_provider.get_named_service(
                IEmailServiceAzure, "azure_email_service"
            )

            # Business logic
            user_id = req.params.get("user_id", "123")
            user = user_service.get_user(user_id)

            # Send notification email
            email_service.send_email(
                to="admin@example.com",
                subject=f"User {user['name']} accessed",
                body=f"User {user['name']} was accessed via API",
            )

            return MockHttpResponse(body=f"Hello {user['name']}", status_code=200)

        # Test the Azure Function
        request = MockHttpRequest(params={"user_id": "456"})
        response = azure_function_handler(request)

        assert response.status_code == 200
        assert "Hello User 456" in response.body

        # Verify email was sent
        email_service = app_provider.get_named_service(
            IEmailServiceAzure, "azure_email_service"
        )
        assert len(email_service.sent_emails) == 1
        assert email_service.sent_emails[0]["to"] == "admin@example.com"

    def test_azure_function_middleware_pipeline(self):
        """Test middleware pipeline for Azure Functions."""

        # Configure application with middleware
        def create_app_with_middleware():
            builder = ApplicationBuilder()

            # Register middleware as named services
            builder.services.add_named(
                "azure_logging_middleware",
                LoggingMiddlewareAzure,
                lifetime=ServiceLifetime.SINGLETON,
            )
            builder.services.add_named(
                "azure_auth_middleware",
                AuthenticationMiddlewareAzure,
                lifetime=ServiceLifetime.SINGLETON,
            )

            # Configure configuration for middleware
            def setup_config(config_builder):
                os.environ["LOGGING__LEVEL"] = "INFO"
                config_builder.add_environment_variables("LOGGING__")
                return config_builder

            builder.configure_configuration(setup_config)

            return builder.build()

        app_provider = create_app_with_middleware()

        # Create middleware pipeline
        def create_middleware_pipeline():
            logging_middleware = app_provider.get_named_service(
                LoggingMiddlewareAzure, "azure_logging_middleware"
            )
            auth_middleware = app_provider.get_named_service(
                AuthenticationMiddlewareAzure, "azure_auth_middleware"
            )

            def execute_pipeline(request, handler):
                try:
                    # Process request through middleware chain
                    request = logging_middleware.process_request(request)
                    request = auth_middleware.process_request(request)

                    # Execute main handler
                    response = handler(request)

                    # Process response through middleware chain (reverse order)
                    response = auth_middleware.process_response(response)
                    response = logging_middleware.process_response(response)

                    return response
                except Exception as e:
                    return MockHttpResponse(body=f"Error: {str(e)}", status_code=401)

            return execute_pipeline

        pipeline = create_middleware_pipeline()

        # Test successful request with authentication
        def main_handler(request):
            return MockHttpResponse(
                body=f"Hello user {getattr(request, 'user_id', 'unknown')}",
                status_code=200,
            )

        authenticated_request = MockHttpRequest(
            headers={"Authorization": "Bearer user123"}
        )

        response = pipeline(authenticated_request, main_handler)

        assert response.status_code == 200
        assert "Hello user user123" in response.body

        # Verify middleware was executed
        logging_middleware = app_provider.get_named_service(
            LoggingMiddlewareAzure, "azure_logging_middleware"
        )
        auth_middleware = app_provider.get_named_service(
            AuthenticationMiddlewareAzure, "azure_auth_middleware"
        )

        assert len(logging_middleware.logs) == 2  # Request and response logged
        assert "user123" in auth_middleware.authenticated_users

        # Test unauthorized request
        unauthorized_request = MockHttpRequest()
        response = pipeline(unauthorized_request, main_handler)

        assert response.status_code == 401
        assert "Unauthorized" in response.body

    def test_azure_function_stateless_optimization(self):
        """Test servicegraph optimization for stateless Azure Functions."""

        # Create multiple app instances to simulate Azure Functions scaling
        def create_optimized_app():
            builder = ApplicationBuilder()

            builder.services.add_named(
                "azure_expensive_service",
                ExpensiveServiceAzure,
                lifetime=ServiceLifetime.SINGLETON,
            )
            builder.services.add_named(
                "azure_request_service",
                RequestServiceAzure,
                lifetime=ServiceLifetime.TRANSIENT,
            )

            return builder.build()

        # Simulate multiple Azure Function instances
        app_instances = [create_optimized_app() for _ in range(3)]

        # Test that expensive services are reused within each instance
        for i, app_provider in enumerate(app_instances):
            request_service1 = app_provider.get_named_service(
                RequestServiceAzure, "azure_request_service"
            )
            request_service2 = app_provider.get_named_service(
                RequestServiceAzure, "azure_request_service"
            )

            # Request services should be different instances (transient)
            assert request_service1.instance_id != request_service2.instance_id

            # But they should share the same expensive service (singleton)
            assert (
                request_service1.expensive_service.instance_id
                == request_service2.expensive_service.instance_id
            )

    def test_azure_function_cold_start_optimization(self):
        """Test servicegraph behavior during Azure Function cold starts."""
        # Clear the global initialization counter
        global cold_start_initialization_calls
        cold_start_initialization_calls.clear()

        def create_cold_start_app():
            builder = ApplicationBuilder()
            builder.services.add_named(
                "azure_cold_start_service",
                ColdStartOptimizedServiceAzure,
                lifetime=ServiceLifetime.SINGLETON,
            )
            return builder.build()

        # Simulate cold start - first invocation
        app_provider = create_cold_start_app()

        # Service should only be initialized when first requested
        assert len(cold_start_initialization_calls) == 0

        # First request triggers initialization
        service1 = app_provider.get_named_service(
            ColdStartOptimizedServiceAzure, "azure_cold_start_service"
        )
        assert len(cold_start_initialization_calls) == 1
        assert service1.ready

        # Subsequent requests reuse the same instance
        service2 = app_provider.get_named_service(
            ColdStartOptimizedServiceAzure, "azure_cold_start_service"
        )
        # No additional initialization
        assert len(cold_start_initialization_calls) == 1
        assert service1 is service2


class TestAzureFunctionConfiguration:
    """Test configuration management in Azure Functions."""

    def test_azure_function_environment_configuration(self):
        """Test Azure Functions configuration from environment variables."""
        # Simulate Azure Functions environment variables
        azure_env_vars = {
            "AZURE_FUNCTIONS_ENVIRONMENT": "Development",
            "AzureWebJobsStorage": ("DefaultEndpointsProtocol=https;AccountName=test"),
            "FUNCTIONS_WORKER_RUNTIME": "python",
            "WEBSITE_SITE_NAME": "test-function-app",
        }

        # Store original values and set Azure environment variables
        original_values = {}
        for key, value in azure_env_vars.items():
            original_values[key] = os.environ.get(key)
            os.environ[key] = value

        # Also store and set APP environment variables BEFORE building
        app_env_vars = {
            "APP__NAME": "servicegraph-test-function",
            "APP__VERSION": "1.0.0",
        }
        for key, value in app_env_vars.items():
            if key not in original_values:
                original_values[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            builder = ApplicationBuilder()

            def setup_azure_config(config_builder):
                # Load Azure Functions environment variables
                config_builder.add_environment_variables("")

                # Add application-specific configuration via environment
                config_builder.add_environment_variables("APP__")
                return config_builder

            builder.configure_configuration(setup_azure_config)
            provider = builder.build()

            config = provider.get_service(IConfiguration)

            # Verify Azure environment is accessible
            azure_env = config.get_value("AZURE_FUNCTIONS_ENVIRONMENT")
            assert azure_env == "Development"
            assert config.get_value("FUNCTIONS_WORKER_RUNTIME") == "python"

            # Verify application configuration
            # APP__NAME becomes NAME after prefix removal
            assert config.get_value("NAME") == "servicegraph-test-function"
            assert config.get_value("VERSION") == "1.0.0"

        finally:
            # Restore original environment
            for key, original_value in original_values.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value


if __name__ == "__main__":
    pytest.main([__file__])

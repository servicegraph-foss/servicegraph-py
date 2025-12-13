"""Core dependency injection functionality tests."""

from abc import ABC, abstractmethod

import pytest

from servicegraph import ApplicationBuilder, ServiceProvider
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


# Test interfaces and services
class ITestService(ABC):
    """Test service interface using ABC."""

    @abstractmethod
    def get_message(self) -> str:
        """Get a test message."""
        pass


class IComplexService(ABC):
    """Service with dependencies using ABC."""

    @abstractmethod
    def process_data(self, data: str) -> str:
        """Process data with dependencies."""
        pass


class TestService(ITestService):
    """Basic test service implementation."""

    def __init__(self, message: str = "Hello from TestService"):
        self.message = message
        self.instance_id = id(self)

    def get_message(self) -> str:
        return self.message


class ComplexService(IComplexService):
    """Service with dependencies for testing recursive resolution."""

    def __init__(self, test_service: ITestService, multiplier: int = 2):
        self.test_service = test_service
        self.multiplier = multiplier

    def process_data(self, data: str) -> str:
        base_message = self.test_service.get_message()
        return f"{base_message}: {data}" * self.multiplier


class IDisposableService(ABC):
    """Interface for disposable services."""

    @abstractmethod
    def dispose(self) -> None:
        """Dispose of the service."""
        pass

    @abstractmethod
    def get_data(self) -> str:
        """Get service data."""
        pass


class DisposableService(IDisposableService):
    """Service that tracks disposal."""

    def __init__(self):
        self.disposed = False

    def dispose(self):
        self.disposed = True

    def get_data(self) -> str:
        if self.disposed:
            raise RuntimeError("Service has been disposed")
        return "Active service data"


class TestCoreServiceRegistration:
    """Test basic service registration and resolution."""

    def test_singleton_registration_basic(self):
        """Test basic singleton service registration and resolution."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(ITestService, TestService)

        provider = builder.build()

        service1 = provider.get_service(ITestService)
        service2 = provider.get_service(ITestService)

        assert service1 is service2  # Same instance
        assert service1.get_message() == "Hello from TestService"

    def test_transient_registration_basic(self):
        """Test transient service creates new instances."""
        builder = ApplicationBuilder()
        builder.services.add_transient(ITestService, TestService)

        provider = builder.build()

        service1 = provider.get_service(ITestService)
        service2 = provider.get_service(ITestService)

        assert service1 is not service2  # Different instances
        assert service1.get_message() == service2.get_message()
        assert service1.instance_id != service2.instance_id

    def test_scoped_registration_basic(self):
        """Test scoped service lifecycle."""
        builder = ApplicationBuilder()

        # Register with factory to provide the string dependency
        def test_service_factory(provider):
            return TestService("Hello from TestService")

        builder.services.add_factory(
            ITestService, test_service_factory, ServiceLifetime.SCOPED
        )

        provider = builder.build()

        # Scoped services should work with context manager
        with provider.get_service(ITestService) as service1:
            # Test that the service works within context
            assert service1.get_message() == "Hello from TestService"

        # Test that scoped services require context manager usage
        scoped_service = provider.get_service(ITestService)
        # This should raise an error if accessed outside context manager
        try:
            scoped_service.get_message()  # Should fail
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "must be used within a 'with' statement" in str(e)

    def test_recursive_dependency_resolution(self):
        """Test automatic dependency resolution."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(ITestService, TestService)
        builder.services.add_singleton(IComplexService, ComplexService)

        provider = builder.build()

        complex_service = provider.get_service(IComplexService)
        result = complex_service.process_data("test")

        expected = "Hello from TestService: test" * 2
        assert result == expected

    def test_concrete_type_registration(self):
        """Test registering concrete types without interfaces."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(TestService)

        provider = builder.build()

        service = provider.get_service(TestService)
        assert service.get_message() == "Hello from TestService"

    def test_factory_registration(self):
        """Test factory-based service registration."""

        def create_test_service(provider: ServiceProvider) -> TestService:
            return TestService("Factory created service")

        builder = ApplicationBuilder()
        builder.services.add_factory(ITestService, create_test_service)

        provider = builder.build()

        service = provider.get_service(ITestService)
        assert service.get_message() == "Factory created service"

    def test_instance_registration(self):
        """Test registering pre-created instances."""
        instance = TestService("Pre-created instance")

        builder = ApplicationBuilder()
        builder.services.add_instance(ITestService, instance)

        provider = builder.build()

        service = provider.get_service(ITestService)
        assert service is instance
        assert service.get_message() == "Pre-created instance"


class TestServiceLifetimes:
    """Test service lifetime behaviors in detail."""

    def test_singleton_memory_efficiency(self):
        """Test that singletons truly reuse the same instance."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(ITestService, TestService)

        provider = builder.build()

        # Get service multiple times
        services = [provider.get_service(ITestService) for _ in range(10)]

        # All should be the same instance
        first_service = services[0]
        for service in services[1:]:
            assert service is first_service

    def test_transient_isolation(self):
        """Test that transient services are properly isolated."""
        builder = ApplicationBuilder()
        builder.services.add_transient(ITestService, TestService)

        provider = builder.build()

        # Create multiple instances
        services = [provider.get_service(ITestService) for _ in range(5)]

        # All should be different instances
        instance_ids = [service.instance_id for service in services]
        assert len(set(instance_ids)) == 5  # All unique

    def test_transient_with_session_id(self):
        """Test transient services with session-based caching."""
        builder = ApplicationBuilder()
        builder.services.add_transient(ITestService, TestService)

        provider = builder.build()

        # Same session should return same instance
        session_id = "test_session_123"
        service1 = provider.get_service(ITestService, session_id)
        service2 = provider.get_service(ITestService, session_id)

        assert service1 is service2

        # Different session should return different instance
        service3 = provider.get_service(ITestService, "different_session")
        assert service3 is not service1

    def test_session_disposal(self):
        """Test session cleanup for transient services."""
        builder = ApplicationBuilder()
        builder.services.add_transient(DisposableService)

        provider = builder.build()

        session_id = "disposable_session"
        service = provider.get_service(DisposableService, session_id)

        assert not service.disposed

        # Dispose session
        provider.dispose_session(session_id)

        # Service should be disposed (if it implements disposal pattern)
        # Note: This test depends on your actual session disposal implementation


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_unregistered_service_error(self):
        """Test that requesting unregistered service raises appropriate error."""
        builder = ApplicationBuilder()
        provider = builder.build()

        with pytest.raises(Exception):  # Should raise ServiceNotRegisteredException
            provider.get_service(ITestService)

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        # This test depends on your circular dependency detection implementation
        # For now, we'll create a basic test structure

        class ServiceA:
            def __init__(self, service_b: "ServiceB"):
                self.service_b = service_b

        class ServiceB:
            def __init__(self, service_a: ServiceA):
                self.service_a = service_a

        builder = ApplicationBuilder()
        builder.services.add_singleton(ServiceA)
        builder.services.add_singleton(ServiceB)

        provider = builder.build()

        # This should detect and handle circular dependency
        with pytest.raises(Exception):  # Should raise CircularDependencyException
            provider.get_service(ServiceA)

    def test_invalid_lifetime_combination(self):
        """Test registration validation."""
        builder = ApplicationBuilder()

        # Test registering the same service twice with different lifetimes
        builder.services.add_singleton(ITestService, TestService)

        # This might be allowed (override) or might raise an exception
        # depending on your implementation
        builder.services.add_transient(ITestService, TestService)


class TestNamedServices:
    """Test named service registration and resolution."""

    def test_named_service_registration(self):
        """Test registering and resolving named services."""
        builder = ApplicationBuilder()

        # Register multiple implementations with names using factories
        builder.services.add_named_factory(
            "primary", ITestService, lambda p: TestService("Primary service")
        )
        builder.services.add_named_factory(
            "secondary", ITestService, lambda p: TestService("Secondary service")
        )

        provider = builder.build()

        primary = provider.get_named_service(ITestService, "primary")
        secondary = provider.get_named_service(ITestService, "secondary")

        assert primary.get_message() == "Primary service"
        assert secondary.get_message() == "Secondary service"
        assert primary is not secondary

    def test_named_service_isolation(self):
        """Test that named services don't interfere with unnamed registration."""
        builder = ApplicationBuilder()

        # Register both named and unnamed services
        builder.services.add_singleton(ITestService, TestService)
        builder.services.add_named_factory(
            "special", ITestService, lambda p: TestService("Special service")
        )

        provider = builder.build()

        default_service = provider.get_service(ITestService)
        named_service = provider.get_named_service(ITestService, "special")

        assert default_service.get_message() == "Hello from TestService"
        assert named_service.get_message() == "Special service"


if __name__ == "__main__":
    pytest.main([__file__])

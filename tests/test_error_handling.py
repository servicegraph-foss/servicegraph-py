"""Error handling and edge case tests."""

from abc import ABC, abstractmethod
from typing import Generic, List, TypeVar

import pytest

from servicegraph import ApplicationBuilder, ServiceProvider

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
# Module-level Test Classes
# ========================


# Classes for unregistered service test
class UnregisteredService:
    pass


# Classes for circular dependency test
class ServiceA:
    def __init__(self, service_b: "ServiceB"):
        self.service_b = service_b


class ServiceB:
    def __init__(self, service_c: "ServiceC"):
        self.service_c = service_c


class ServiceC:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a


# Classes for invalid constructor parameters test
class ServiceWithInvalidDependency:
    def __init__(self, required_param: str, unregistered_service: "UnregisteredDep"):
        self.required_param = required_param
        self.unregistered_service = unregistered_service


class UnregisteredDep:
    pass


# Classes for constructor exception test
class FailingService:
    def __init__(self):
        raise ValueError("Service construction failed")


# Classes for disposed provider test
class TestService:
    def get_data(self):
        return "test_data"


# Classes for scoped service test
class ScopedService:
    def get_data(self):
        return "scoped_data"


# Classes for transient service test
class TransientService:
    pass


# Classes for type annotation test
class ServiceWithBadAnnotation:
    def __init__(self, param: "not_a_real_type"):
        self.param = param


# Classes for optional parameters test
class OptionalParameterService:
    def __init__(
        self, required_service: "RequiredService", optional_param: str = "default_value"
    ):
        self.required_service = required_service
        self.optional_param = optional_param


class RequiredService:
    def get_value(self):
        return "required_value"


# Classes for no constructor test
class NoConstructorService:
    data = "class_data"


# Classes for multiple constructors test
class MultiConstructorService:
    def __init__(self, value: str):
        self.value = value

    @classmethod
    def create_default(cls):
        return cls("default")

    @classmethod
    def create_custom(cls, custom_value: str):
        return cls(custom_value)


# Classes for generic service test
T = TypeVar("T")


class GenericService(Generic[T]):
    def __init__(self):
        self.items: List[T] = []

    def add_item(self, item: T):
        self.items.append(item)


# Classes for protocol test
class IServiceProtocol(ABC):
    """Service protocol using ABC."""

    @abstractmethod
    def process_data(self, data: str) -> str:
        """Process data."""
        pass


class ConcreteService(IServiceProtocol):
    def process_data(self, data: str) -> str:
        return f"processed: {data}"


# Classes for nested dependency chains test
class Service0:
    def __init__(self):
        self.level = 0


class Service1:
    def __init__(self, dependency: Service0):
        self.level = 1
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service2:
    def __init__(self, dependency: Service1):
        self.level = 2
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service3:
    def __init__(self, dependency: Service2):
        self.level = 3
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service4:
    def __init__(self, dependency: Service3):
        self.level = 4
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service5:
    def __init__(self, dependency: Service4):
        self.level = 5
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service6:
    def __init__(self, dependency: Service5):
        self.level = 6
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service7:
    def __init__(self, dependency: Service6):
        self.level = 7
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service8:
    def __init__(self, dependency: Service7):
        self.level = 8
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


class Service9:
    def __init__(self, dependency: Service8):
        self.level = 9
        self.dependency = dependency

    def get_chain_length(self):
        if hasattr(self.dependency, "get_chain_length"):
            return 1 + self.dependency.get_chain_length()
        else:
            return 1


# Classes for service replacement test
class IService(ABC):
    @abstractmethod
    def get_message(self) -> str:
        pass


class FirstImplementation(IService):
    def get_message(self) -> str:
        return "first implementation"


class SecondImplementation(IService):
    def get_message(self) -> str:
        return "second implementation"


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""

    def test_unregistered_service_error(self):
        """Test error when requesting unregistered service."""
        builder = ApplicationBuilder()
        provider = builder.build()

        with pytest.raises(Exception) as exc_info:
            provider.get_service(UnregisteredService)

        # Should be a meaningful error message
        error_message = str(exc_info.value).lower()
        assert "not registered" in error_message or "not found" in error_message

    def test_circular_dependency_detection(self):
        """Test detection and handling of circular dependencies."""
        builder = ApplicationBuilder()

        builder.services.add_singleton(ServiceA)
        builder.services.add_singleton(ServiceB)
        builder.services.add_singleton(ServiceC)

        provider = builder.build()

        # Should detect circular dependency
        with pytest.raises(Exception) as exc_info:
            provider.get_service(ServiceA)

        error_message = str(exc_info.value).lower()
        assert (
            "circular" in error_message
            or "recursive" in error_message
            or "dependency" in error_message
        )

    def test_invalid_constructor_parameters(self):
        """Test handling of services with invalid constructor parameters."""
        builder = ApplicationBuilder()

        builder.services.add_singleton(ServiceWithInvalidDependency)
        provider = builder.build()

        with pytest.raises(Exception):
            provider.get_service(ServiceWithInvalidDependency)

    def test_constructor_exception_handling(self):
        """Test handling of exceptions during service construction."""
        builder = ApplicationBuilder()

        builder.services.add_singleton(FailingService)
        provider = builder.build()

        with pytest.raises(ValueError, match="Service construction failed"):
            provider.get_service(FailingService)

    def test_factory_exception_handling(self):
        """Test handling of exceptions in factory functions."""
        builder = ApplicationBuilder()

        def failing_factory(provider: ServiceProvider):
            raise RuntimeError("Factory failed to create service")

        builder.services.add_factory(str, failing_factory)
        provider = builder.build()

        with pytest.raises(RuntimeError, match="Factory failed to create service"):
            provider.get_service(str)

    def test_invalid_service_registration(self):
        """Test validation of service registration parameters."""
        builder = ApplicationBuilder()

        # Test that instance registration validates type compatibility
        service_instance = "not_a_valid_instance"
        with pytest.raises(TypeError, match="not compatible"):
            builder.services.add_instance(int, service_instance)

    def test_disposed_provider_access(self):
        """Test accessing services after provider disposal."""
        builder = ApplicationBuilder()

        builder.services.add_singleton(TestService)
        provider = builder.build()

        # Get service before disposal
        service = provider.get_service(TestService)
        assert service.get_data() == "test_data"

        # Dispose provider (if disposal is implemented)
        if hasattr(provider, "dispose"):
            provider.dispose()

            # Should raise error when accessing disposed provider
            with pytest.raises(Exception):
                provider.get_service(TestService)

    def test_invalid_scope_usage(self):
        """Test error handling for invalid scoped service usage."""
        builder = ApplicationBuilder()

        builder.services.add_scoped(ScopedService)
        provider = builder.build()

        # Getting the service returns a context manager wrapper (no error yet)
        scoped_service = provider.get_service(ScopedService)

        # Attempting to use it without 'with' should raise RuntimeError
        with pytest.raises(RuntimeError, match="must be used within.*with.*statement"):
            scoped_service.get_data()  # Accessing method triggers __getattr__

    def test_invalid_session_id_handling(self):
        """Test handling of invalid session IDs."""
        builder = ApplicationBuilder()

        builder.services.add_transient(TransientService)
        provider = builder.build()

        # Test with None session ID
        service1 = provider.get_service(TransientService, None)
        service2 = provider.get_service(TransientService, None)

        # Should create different instances (no session caching with None)
        assert service1 is not service2

        # Test with empty string session ID
        service3 = provider.get_service(TransientService, "")
        service4 = provider.get_service(TransientService, "")

        # Should handle empty string gracefully
        assert service3 is not None
        assert service4 is not None

    def test_type_annotation_errors(self):
        """Test handling of invalid type annotations."""
        builder = ApplicationBuilder()

        builder.services.add_singleton(ServiceWithBadAnnotation)
        provider = builder.build()

        # Should handle invalid type annotations gracefully
        with pytest.raises(Exception):
            provider.get_service(ServiceWithBadAnnotation)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_service_with_no_constructor(self):
        """Test service that inherits default constructor."""
        builder = ApplicationBuilder()

        builder.services.add_singleton(NoConstructorService)
        provider = builder.build()

        service = provider.get_service(NoConstructorService)
        assert service.data == "class_data"

    def test_service_with_optional_parameters(self):
        """Test service with optional constructor parameters."""
        builder = ApplicationBuilder()

        builder.services.add_singleton(RequiredService)
        builder.services.add_singleton(OptionalParameterService)

        provider = builder.build()

        service = provider.get_service(OptionalParameterService)
        assert service.required_service.get_value() == "required_value"
        assert service.optional_param == "default_value"

    def test_service_with_multiple_constructors(self):
        """Test service with class method constructors."""
        builder = ApplicationBuilder()

        # Test factory registration for alternative constructor
        builder.services.add_factory(
            MultiConstructorService,
            lambda provider: MultiConstructorService.create_custom("factory_created"),
        )

        provider = builder.build()

        service = provider.get_service(MultiConstructorService)
        assert service.value == "factory_created"

    @pytest.mark.skip(
        reason="Generic[T] from typing adds internal parameters that interfere with DI - use concrete classes or factory registration for generics"
    )
    def test_generic_service_registration(self):
        """Test registration of generic services."""
        builder = ApplicationBuilder()

        # Register concrete generic types
        builder.services.add_singleton(GenericService[str])
        builder.services.add_singleton(GenericService[int])

        provider = builder.build()

        string_service = provider.get_service(GenericService[str])
        int_service = provider.get_service(GenericService[int])

        string_service.add_item("test")
        int_service.add_item(123)

        assert string_service.items == ["test"]
        assert int_service.items == [123]
        assert string_service is not int_service

    def test_protocol_service_registration(self):
        """Test registration with ABC interface types."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(IServiceProtocol, ConcreteService)

        provider = builder.build()

        service = provider.get_service(IServiceProtocol)
        result = service.process_data("test")
        assert result == "processed: test"

    def test_nested_dependency_chains(self):
        """Test deeply nested dependency chains."""
        builder = ApplicationBuilder()

        # Register all services in the chain
        builder.services.add_singleton(Service0)
        builder.services.add_singleton(Service1)
        builder.services.add_singleton(Service2)
        builder.services.add_singleton(Service3)
        builder.services.add_singleton(Service4)
        builder.services.add_singleton(Service5)
        builder.services.add_singleton(Service6)
        builder.services.add_singleton(Service7)
        builder.services.add_singleton(Service8)
        builder.services.add_singleton(Service9)

        provider = builder.build()

        # Get the top-level service
        final_service = provider.get_service(Service9)

        # Should successfully resolve entire chain
        assert final_service.level == 9
        assert final_service.get_chain_length() == 9

    def test_service_replacement(self):
        """Test replacing service registrations."""
        builder = ApplicationBuilder()

        # Register first implementation
        builder.services.add_singleton(IService, FirstImplementation)

        # Replace with second implementation
        builder.services.add_singleton(IService, SecondImplementation)

        provider = builder.build()

        service = provider.get_service(IService)
        assert service.get_message() == "second implementation"


if __name__ == "__main__":
    pytest.main([__file__])

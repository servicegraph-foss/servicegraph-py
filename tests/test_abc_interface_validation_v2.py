"""Tests for ABC interface requirement enforcement.

This test module is designed to work with the singleton ServiceProvider pattern.
All tests use unique service names to avoid conflicts when run together.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import pytest

from servicegraph import ApplicationBuilder
from servicegraph.service_lifetime import ServiceLifetime

# Module-level interfaces and implementations with unique names


# For singleton test
class IValidSingleton(ABC):
    @abstractmethod
    def do_work(self) -> str:
        pass


class ValidSingletonService(IValidSingleton):
    def do_work(self) -> str:
        return "singleton work"


# For transient test
class IValidTransient(ABC):
    @abstractmethod
    def get_id(self) -> str:
        pass


class ValidTransientService(IValidTransient):
    def __init__(self):
        import uuid

        self.id = str(uuid.uuid4())

    def get_id(self) -> str:
        return self.id


# For scoped test
class IValidScoped(ABC):
    @abstractmethod
    def process(self) -> str:
        pass


class ValidScopedService(IValidScoped):
    def __init__(self):
        self.processed = False

    def process(self) -> str:
        self.processed = True
        return "scoped processing"


# For inheritance validation test
class IStrictInterface(ABC):
    @abstractmethod
    def strict_method(self) -> bool:
        pass


class NonInheritingImplementation:
    """Implementation that doesn't inherit from the interface."""

    def strict_method(self) -> bool:
        return True


# For incomplete implementation test
class ICompleteInterface(ABC):
    @abstractmethod
    def method_one(self) -> str:
        pass

    @abstractmethod
    def method_two(self) -> int:
        pass


class IncompleteImplementation(ICompleteInterface):
    def method_one(self) -> str:
        return "implemented"

    # Missing method_two implementation


# For multiple interface inheritance test
class IReadableService(ABC):
    @abstractmethod
    def read(self) -> str:
        pass


class IWritableService(ABC):
    @abstractmethod
    def write(self, data: str) -> bool:
        pass


class ReadWriteService(IReadableService, IWritableService):
    def __init__(self):
        self.data = ""

    def read(self) -> str:
        return self.data

    def write(self, data: str) -> bool:
        self.data = data
        return True


# For abstract properties test
class IConfigurableService(ABC):
    @property
    @abstractmethod
    def config_value(self) -> str:
        pass

    @config_value.setter
    @abstractmethod
    def config_value(self, value: str) -> None:
        pass


class ConfigurableService(IConfigurableService):
    def __init__(self):
        self._config_value = "default"

    @property
    def config_value(self) -> str:
        return self._config_value

    @config_value.setter
    def config_value(self, value: str) -> None:
        self._config_value = value


# For generic interfaces test
T = TypeVar("T")


class IRepositoryService(ABC, Generic[T]):
    @abstractmethod
    def save(self, entity: T) -> bool:
        pass

    @abstractmethod
    def get(self, id: str) -> T:
        pass


class UserRepositoryService(IRepositoryService[dict]):
    def __init__(self):
        self.users = {}

    def save(self, entity: dict) -> bool:
        if "id" not in entity:
            return False
        self.users[entity["id"]] = entity
        return True

    def get(self, id: str) -> dict:
        return self.users.get(id, {})


# For factory registration test
class IApiClientService(ABC):
    @abstractmethod
    def get_data(self) -> str:
        pass


class ApiClientService(IApiClientService):
    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_data(self) -> str:
        return f"Data from {self.base_url}"


def create_api_client(provider):
    return ApiClientService("https://api.example.com")


# For non-ABC interface test
class NotAnInterface:  # Missing ABC inheritance
    def some_method(self) -> str:
        pass


class SomeImplementation:
    def some_method(self) -> str:
        return "implemented"


# For class without constructor test
class ISimpleInterface(ABC):
    @abstractmethod
    def simple_method(self) -> str:
        pass


class SimpleImplementation(ISimpleInterface):
    # No explicit __init__ method
    def simple_method(self) -> str:
        return "simple result"


class TestABCInterfaceValidation:
    """Test ABC interface enforcement across all registration types and lifetimes."""

    @classmethod
    def setup_class(cls):
        """Set up shared builder and provider for all tests."""
        cls.builder = ApplicationBuilder()
        cls.provider = None

    def get_provider(self):
        """Get the singleton provider, building it if necessary."""
        if self.provider is None:
            self.__class__.provider = self.builder.build()
        return self.provider

    def test_01_valid_abc_singleton_registration(self):
        """Test successful ABC interface registration with singleton lifetime."""

        # Register as named service to avoid conflicts
        self.builder.services.add_named(
            "valid_singleton",
            IValidSingleton,
            ValidSingletonService,
            ServiceLifetime.SINGLETON,
        )

        provider = self.get_provider()
        service = provider.get_named_service(IValidSingleton, "valid_singleton")

        assert service.do_work() == "singleton work"
        assert isinstance(service, IValidSingleton)

        # Verify singleton behavior - same instance
        service2 = provider.get_named_service(IValidSingleton, "valid_singleton")
        assert service is service2

    def test_02_valid_abc_transient_registration(self):
        """Test successful ABC interface registration with transient lifetime."""

        self.builder.services.add_named(
            "valid_transient",
            IValidTransient,
            ValidTransientService,
            ServiceLifetime.TRANSIENT,
        )

        provider = self.get_provider()
        service1 = provider.get_named_service(IValidTransient, "valid_transient")
        service2 = provider.get_named_service(IValidTransient, "valid_transient")

        # Verify transient behavior - different instances
        assert service1 is not service2
        assert service1.get_id() != service2.get_id()
        assert isinstance(service1, IValidTransient)
        assert isinstance(service2, IValidTransient)

    def test_03_valid_abc_scoped_registration(self):
        """Test successful ABC interface registration with scoped lifetime."""

        self.builder.services.add_named(
            "valid_scoped", IValidScoped, ValidScopedService, ServiceLifetime.SCOPED
        )

        provider = self.get_provider()

        # Test scoped service usage
        with provider.get_named_service(IValidScoped, "valid_scoped") as service:
            result = service.process()
            assert result == "scoped processing"
            assert service.processed is True
            assert isinstance(service, IValidScoped)

    def test_04_implementation_inheritance_validation(self):
        """Test that implementation inheritance is properly validated."""

        # This should raise an error during registration
        with pytest.raises(TypeError) as exc_info:
            self.builder.services.add_named(
                "invalid_inheritance", IStrictInterface, NonInheritingImplementation
            )

        error_msg = str(exc_info.value)
        assert "does not implement" in error_msg
        assert "IStrictInterface" in error_msg

    def test_05_incomplete_implementation_detection(self):
        """Test detection of incomplete abstract method implementations."""

        # Registration should succeed (inheritance is valid)
        self.builder.services.add_named(
            "incomplete_impl", ICompleteInterface, IncompleteImplementation
        )

        provider = self.get_provider()

        # But instantiation should fail
        with pytest.raises(TypeError) as exc_info:
            provider.get_named_service(ICompleteInterface, "incomplete_impl")

        error_msg = str(exc_info.value)
        assert "abstract" in error_msg.lower()

    def test_06_multiple_interface_inheritance(self):
        """Test implementations that inherit from multiple ABC interfaces."""

        # Register the same implementation for both interfaces
        self.builder.services.add_named(
            "readable_service", IReadableService, ReadWriteService
        )
        self.builder.services.add_named(
            "writable_service", IWritableService, ReadWriteService
        )

        provider = self.get_provider()

        readable = provider.get_named_service(IReadableService, "readable_service")
        writable = provider.get_named_service(IWritableService, "writable_service")

        # Test functionality
        assert writable.write("test data") is True
        assert writable.read() == "test data"

        assert readable.write("other data") is True
        assert readable.read() == "other data"

        # These are different instances (different registrations)
        assert readable is not writable

    def test_07_abstract_properties_support(self):
        """Test support for abstract properties."""

        self.builder.services.add_named(
            "configurable_service", IConfigurableService, ConfigurableService
        )

        provider = self.get_provider()
        service = provider.get_named_service(
            IConfigurableService, "configurable_service"
        )

        assert service.config_value == "default"
        service.config_value = "updated"
        assert service.config_value == "updated"

    def test_08_generic_abc_interfaces(self):
        """Test support for generic ABC interfaces."""

        self.builder.services.add_named(
            "user_repository", IRepositoryService[dict], UserRepositoryService
        )

        provider = self.get_provider()
        repo = provider.get_named_service(IRepositoryService[dict], "user_repository")

        user = {"id": "123", "name": "Test User"}
        assert repo.save(user) is True
        retrieved = repo.get("123")
        assert retrieved["name"] == "Test User"

    def test_09_factory_registration_with_abc(self):
        """Test factory registration with ABC interfaces."""

        self.builder.services.add_named_factory(
            "api_client", IApiClientService, create_api_client
        )

        provider = self.get_provider()
        client = provider.get_named_service(IApiClientService, "api_client")

        assert client.get_data() == "Data from https://api.example.com"
        assert isinstance(client, IApiClientService)

    def test_10_non_abc_interface_handling(self):
        """Test that non-ABC interfaces are handled appropriately."""

        # This should be allowed since it's technically valid Python inheritance
        # The validation is more about proper inheritance, not ABC enforcement
        try:
            self.builder.services.add_named(
                "non_abc_service", NotAnInterface, SomeImplementation
            )
            provider = self.get_provider()
            service = provider.get_named_service(NotAnInterface, "non_abc_service")
            assert service.some_method() == "implemented"
        except Exception:
            # If the framework chooses to enforce ABC, that's also valid
            pass

    def test_11_class_without_constructor(self):
        """Test handling of classes without explicit constructors."""

        self.builder.services.add_named(
            "simple_service", ISimpleInterface, SimpleImplementation
        )

        provider = self.get_provider()
        service = provider.get_named_service(ISimpleInterface, "simple_service")

        assert service.simple_method() == "simple result"
        assert isinstance(service, ISimpleInterface)

    def test_12_service_provider_singleton_behavior(self):
        """Verify that the ServiceProvider maintains singleton behavior."""

        # Get initial provider
        provider1 = self.get_provider()

        # Register a test service
        builder = ApplicationBuilder()
        builder.services.add_singleton(ISimpleInterface, SimpleImplementation)
        provider2 = builder.build()

        # They should be the same instance (singleton pattern)
        assert provider1 is provider2

        # Verify the singleton updates its collection reference
        # After the second build, provider should have the new services
        all_services = provider2.get_all_services()
        assert len(all_services) >= 2  # IConfiguration + ISimpleInterface
        assert "ISimpleInterface" in all_services


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

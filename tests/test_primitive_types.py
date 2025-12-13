"""Tests for handling primitive types in constructor parameters."""

import logging
from abc import ABC, abstractmethod

import pytest

from servicegraph import ApplicationBuilder, ServiceProvider


@pytest.fixture(autouse=True)
def reset_service_provider():
    """Reset the ServiceProvider state before each test."""
    from servicegraph.service_provider import ServiceProvider

    # Clear before test
    if ServiceProvider._instance is not None:
        ServiceProvider._instance.clear_all_instances()
        ServiceProvider._instance._collection.clear()

    yield


# Test services with primitive type parameters
class IMessageService(ABC):
    """Service interface."""

    @abstractmethod
    def get_message(self) -> str:
        pass


class ServiceWithString(IMessageService):
    """Service with a string parameter in constructor."""

    def __init__(self, message: str = "default message"):
        self.message = message

    def get_message(self) -> str:
        return self.message


class ServiceWithMultiplePrimitives(IMessageService):
    """Service with multiple primitive type parameters."""

    def __init__(self, name: str = "default", count: int = 0, enabled: bool = True):
        self.name = name
        self.count = count
        self.enabled = enabled

    def get_message(self) -> str:
        return f"{self.name}: {self.count} (enabled={self.enabled})"


class ServiceWithPrimitiveAndComplex:
    """Service with both primitive and complex type parameters."""

    def __init__(self, message_service: IMessageService, prefix: str = "Prefix"):
        self.message_service = message_service
        self.prefix = prefix

    def get_prefixed_message(self) -> str:
        return f"{self.prefix}: {self.message_service.get_message()}"


class ServiceWithPrimitiveNoDefault:
    """Service with primitive type but no default value."""

    def __init__(self, message: str):
        self.message = message

    def get_message(self) -> str:
        return self.message


class ServiceWithListParam:
    """Service with list parameter."""

    def __init__(self, items: list = None):
        self.items = items or []

    def get_items(self) -> list:
        return self.items


class ServiceWithDictParam:
    """Service with dict parameter."""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def get_config(self) -> dict:
        return self.config


class TestPrimitiveTypeHandling:
    """Test that primitive types are handled gracefully."""

    def test_service_with_string_default(self):
        """Test service with string parameter that has default value."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(IMessageService, ServiceWithString)

        provider = builder.build()
        service = provider.get_service(IMessageService)

        # Should use the default value since string is not injectable
        assert service.get_message() == "default message"

    def test_service_with_multiple_primitives(self):
        """Test service with multiple primitive parameters with defaults."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(IMessageService, ServiceWithMultiplePrimitives)

        provider = builder.build()
        service = provider.get_service(IMessageService)

        # Should use all default values
        assert service.get_message() == "default: 0 (enabled=True)"

    def test_service_with_primitive_and_complex(self):
        """Test service that has both primitive and complex type parameters."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(IMessageService, ServiceWithString)
        builder.services.add_singleton(ServiceWithPrimitiveAndComplex)

        provider = builder.build()
        service = provider.get_service(ServiceWithPrimitiveAndComplex)

        # Complex type should be injected, primitive should use default
        assert service.get_prefixed_message() == "Prefix: default message"

    def test_service_with_primitive_no_default_logs_warning(self, caplog):
        """Test that service with primitive and no default is created with None."""
        builder = ApplicationBuilder()

        # This should create the service but log a warning
        with caplog.at_level(logging.WARNING):
            builder.services.add_singleton(ServiceWithPrimitiveNoDefault)
            provider = builder.build()

            # Should succeed - service is created with None for the primitive
            service = provider.get_service(ServiceWithPrimitiveNoDefault)

            # The service exists but message is None
            assert service is not None
            assert service.message is None  # Primitive parameter was provided as None

        # Check that a warning was logged
        assert any(
            "primitive type with no default value" in record.message
            for record in caplog.records
        )

    def test_service_with_primitive_no_default_fails_on_usage(self, caplog):
        """Test that using None value from unprovided primitive causes error."""
        builder = ApplicationBuilder()

        with caplog.at_level(logging.WARNING):
            builder.services.add_singleton(ServiceWithPrimitiveNoDefault)
            provider = builder.build()
            service = provider.get_service(ServiceWithPrimitiveNoDefault)

            # Service was created, but trying to use the None value will fail
            # This is the developer's fault for not using proper registration
            with pytest.raises(
                AttributeError, match="'NoneType' object has no attribute"
            ):
                # get_message() returns self.message which is None
                # If the method tries to do string operations on it, it will fail
                _ = service.get_message().upper()  # Fails: NoneType has no upper()

    def test_service_with_list_param(self):
        """Test service with list parameter."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(ServiceWithListParam)

        provider = builder.build()
        service = provider.get_service(ServiceWithListParam)

        # Should use default value (empty list)
        assert service.get_items() == []

    def test_service_with_dict_param(self):
        """Test service with dict parameter."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(ServiceWithDictParam)

        provider = builder.build()
        service = provider.get_service(ServiceWithDictParam)

        # Should use default value (empty dict)
        assert service.get_config() == {}

    def test_factory_registration_with_primitives(self):
        """Test that factory registration works for services with primitive params."""
        builder = ApplicationBuilder()

        # Use a factory to provide the primitive value
        def create_service(provider: ServiceProvider) -> ServiceWithPrimitiveNoDefault:
            return ServiceWithPrimitiveNoDefault("factory provided message")

        builder.services.add_factory(ServiceWithPrimitiveNoDefault, create_service)

        provider = builder.build()
        service = provider.get_service(ServiceWithPrimitiveNoDefault)

        assert service.get_message() == "factory provided message"

    def test_instance_registration_with_primitives(self):
        """Test that instance registration works for services with primitive params."""
        builder = ApplicationBuilder()

        # Pre-create an instance with specific primitive values
        instance = ServiceWithString("instance provided message")
        builder.services.add_instance(IMessageService, instance)

        provider = builder.build()
        service = provider.get_service(IMessageService)

        assert service.get_message() == "instance provided message"
        assert service is instance


class TestPrimitiveTypeEdgeCases:
    """Test edge cases with primitive types."""

    def test_bool_type(self):
        """Test service with bool parameter."""

        class ServiceWithBool:
            def __init__(self, enabled: bool = False):
                self.enabled = enabled

        builder = ApplicationBuilder()
        builder.services.add_singleton(ServiceWithBool)

        provider = builder.build()
        service = provider.get_service(ServiceWithBool)

        assert service.enabled is False

    def test_numeric_types(self):
        """Test service with various numeric type parameters."""

        class ServiceWithNumeric:
            def __init__(self, count: int = 0, ratio: float = 0.0, value: complex = 0j):
                self.count = count
                self.ratio = ratio
                self.value = value

        builder = ApplicationBuilder()
        builder.services.add_singleton(ServiceWithNumeric)

        provider = builder.build()
        service = provider.get_service(ServiceWithNumeric)

        assert service.count == 0
        assert service.ratio == 0.0
        assert service.value == 0j

    def test_bytes_type(self):
        """Test service with bytes parameter."""

        class ServiceWithBytes:
            def __init__(self, data: bytes = b""):
                self.data = data

        builder = ApplicationBuilder()
        builder.services.add_singleton(ServiceWithBytes)

        provider = builder.build()
        service = provider.get_service(ServiceWithBytes)

        assert service.data == b""

    def test_tuple_and_set_types(self):
        """Test service with tuple and set parameters."""

        class ServiceWithCollections:
            def __init__(self, items: tuple = (), unique: set = None):
                self.items = items
                self.unique = unique or set()

        builder = ApplicationBuilder()
        builder.services.add_singleton(ServiceWithCollections)

        provider = builder.build()
        service = provider.get_service(ServiceWithCollections)

        assert service.items == ()
        assert service.unique == set()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

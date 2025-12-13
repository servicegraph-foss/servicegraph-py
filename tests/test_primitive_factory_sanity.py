"""Sanity check tests to ensure factory-based registration works with primitive types."""

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


class IMessageService(ABC):
    """Service interface."""

    @abstractmethod
    def get_message(self) -> str:
        pass


class MessageService:
    """Service with string parameter - requires factory for DI."""

    def __init__(self, message: str):
        self.message = message

    def get_message(self) -> str:
        return self.message


class ConfigurableService:
    """Service with multiple primitive parameters."""

    def __init__(self, name: str, count: int, enabled: bool):
        self.name = name
        self.count = count
        self.enabled = enabled

    def get_config(self) -> str:
        return f"{self.name}: count={self.count}, enabled={self.enabled}"


class ComplexServiceWithPrimitives:
    """Service with both injected and primitive parameters."""

    def __init__(self, dependency: IMessageService, prefix: str, suffix: str):
        self.dependency = dependency
        self.prefix = prefix
        self.suffix = suffix

    def get_full_message(self) -> str:
        return f"{self.prefix} {self.dependency.get_message()} {self.suffix}"


class TestFactoryWithPrimitives:
    """Test that factory registration properly handles primitive type parameters."""

    def test_factory_provides_string_parameter(self):
        """Test that a factory can provide string parameters."""
        builder = ApplicationBuilder()

        # Use factory to provide the string parameter
        def message_factory(provider: ServiceProvider) -> MessageService:
            return MessageService("Factory provided message")

        builder.services.add_factory(MessageService, message_factory)

        provider = builder.build()
        service = provider.get_service(MessageService)

        assert service.get_message() == "Factory provided message"

    def test_factory_provides_multiple_primitives(self):
        """Test that a factory can provide multiple primitive parameters."""
        builder = ApplicationBuilder()

        def config_factory(provider: ServiceProvider) -> ConfigurableService:
            return ConfigurableService(name="TestConfig", count=42, enabled=True)

        builder.services.add_factory(ConfigurableService, config_factory)

        provider = builder.build()
        service = provider.get_service(ConfigurableService)

        assert service.get_config() == "TestConfig: count=42, enabled=True"

    def test_factory_with_dependency_injection_and_primitives(self):
        """Test factory that resolves dependencies and provides primitives."""
        builder = ApplicationBuilder()

        # Register a dependency with correct factory signature
        def msg_factory(provider: ServiceProvider) -> IMessageService:
            return MessageService("Injected message")

        builder.services.add_factory(IMessageService, msg_factory)

        # Factory resolves IMessageService from provider and provides primitives
        def complex_factory(provider: ServiceProvider) -> ComplexServiceWithPrimitives:
            msg_service = provider.get_service(IMessageService)
            return ComplexServiceWithPrimitives(
                dependency=msg_service, prefix="[START]", suffix="[END]"
            )

        builder.services.add_factory(ComplexServiceWithPrimitives, complex_factory)

        provider = builder.build()
        service = provider.get_service(ComplexServiceWithPrimitives)

        assert service.get_full_message() == "[START] Injected message [END]"

    def test_add_factory_method(self):
        """Test the add_factory convenience method."""
        builder = ApplicationBuilder()

        builder.services.add_factory(
            MessageService, lambda p: MessageService("Via add_factory")
        )

        provider = builder.build()
        service = provider.get_service(MessageService)

        assert service.get_message() == "Via add_factory"

    def test_add_named_factory(self):
        """Test named factory registration."""
        builder = ApplicationBuilder()

        # Register multiple named factories
        builder.services.add_named_factory(
            "primary", MessageService, lambda p: MessageService("Primary message")
        )

        builder.services.add_named_factory(
            "secondary", MessageService, lambda p: MessageService("Secondary message")
        )

        provider = builder.build()

        primary = provider.get_named_service(MessageService, "primary")
        secondary = provider.get_named_service(MessageService, "secondary")

        assert primary.get_message() == "Primary message"
        assert secondary.get_message() == "Secondary message"

    def test_factory_singleton_lifetime(self):
        """Test that factory-created singletons return same instance."""
        builder = ApplicationBuilder()

        call_count = 0

        def counting_factory(provider: ServiceProvider) -> MessageService:
            nonlocal call_count
            call_count += 1
            return MessageService(f"Instance {call_count}")

        builder.services.add_factory(MessageService, counting_factory)

        provider = builder.build()

        service1 = provider.get_service(MessageService)
        service2 = provider.get_service(MessageService)

        # Factory should only be called once for singleton
        assert call_count == 1
        assert service1 is service2
        assert service1.get_message() == "Instance 1"

    def test_instance_registration(self):
        """Test that add_instance works with services that have primitive params."""
        builder = ApplicationBuilder()

        # Create instance with specific primitive values
        instance = MessageService("Pre-created instance")

        builder.services.add_instance(MessageService, instance)

        provider = builder.build()
        service = provider.get_service(MessageService)

        assert service is instance
        assert service.get_message() == "Pre-created instance"


class TestFactoryEdgeCases:
    """Test edge cases with factory registration."""

    def test_factory_overrides_default_creation(self):
        """Test that factory registration overrides auto-generated factory."""
        builder = ApplicationBuilder()

        # Even though MessageService has no default for 'message',
        # factory registration should work
        builder.services.add_factory(
            MessageService, lambda p: MessageService("Factory override")
        )

        provider = builder.build()
        service = provider.get_service(MessageService)

        assert service.get_message() == "Factory override"

    def test_factory_can_use_configuration(self):
        """Test that factory can use values from external sources (configuration pattern)."""
        builder = ApplicationBuilder()

        # Simulate reading from configuration/external source
        config_value = "From configuration"

        # Factory uses the external value to provide primitives
        def configured_factory(provider: ServiceProvider) -> MessageService:
            # In real usage, this might read from IConfiguration
            return MessageService(config_value)

        builder.services.add_factory(MessageService, configured_factory)

        provider = builder.build()
        service = provider.get_service(MessageService)

        assert service.get_message() == "From configuration"

    def test_lambda_factory_shorthand(self):
        """Test using lambda as a shorthand factory."""
        builder = ApplicationBuilder()

        # Use add_factory with lambda
        builder.services.add_factory(
            IMessageService, lambda p: MessageService("Lambda factory")
        )

        provider = builder.build()
        service = provider.get_service(IMessageService)

        assert service.get_message() == "Lambda factory"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

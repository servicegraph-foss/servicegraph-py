"""Comprehensive test demonstrating proper primitive type handling in DI."""

import logging
from abc import ABC, abstractmethod

import pytest

from servicegraph import ApplicationBuilder


@pytest.fixture(autouse=True)
def reset_service_provider():
    """Reset the ServiceProvider state before each test."""
    from servicegraph.service_provider import ServiceProvider

    if ServiceProvider._instance is not None:
        ServiceProvider._instance.clear_all_instances()
        ServiceProvider._instance._collection.clear()

    yield


class IEmailService(ABC):
    """Email service interface."""

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> bool:
        pass


class EmailService(IEmailService):
    """Email service with configuration parameters (primitives)."""

    def __init__(self, smtp_host: str, smtp_port: int, use_ssl: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_ssl = use_ssl

    def send_email(self, to: str, subject: str, body: str) -> bool:
        # In real implementation, would send email
        return f"{self.smtp_host}:{self.smtp_port}" is not None


class NotificationService:
    """Service that depends on EmailService."""

    def __init__(self, email_service: IEmailService, app_name: str = "MyApp"):
        self.email_service = email_service
        self.app_name = app_name

    def notify_user(self, user_email: str, message: str) -> bool:
        subject = f"Notification from {self.app_name}"
        return self.email_service.send_email(user_email, subject, message)


def test_proper_registration_with_factory():
    """Demonstrate the CORRECT way to register services with primitive parameters."""
    builder = ApplicationBuilder()

    # CORRECT: Use factory to provide primitive values
    def email_factory(provider):
        return EmailService(smtp_host="smtp.example.com", smtp_port=587, use_ssl=True)

    builder.services.add_factory(IEmailService, email_factory)
    builder.services.add_singleton(NotificationService)

    provider = builder.build()

    # Both services work correctly
    email_service = provider.get_service(IEmailService)
    assert email_service.smtp_host == "smtp.example.com"
    assert email_service.smtp_port == 587

    notification_service = provider.get_service(NotificationService)
    assert notification_service.app_name == "MyApp"
    assert notification_service.notify_user("user@example.com", "Hello!")


def test_improper_registration_with_primitives_no_defaults(caplog):
    """Demonstrate what happens with IMPROPER registration (primitives without defaults)."""
    builder = ApplicationBuilder()

    with caplog.at_level(logging.WARNING):
        # IMPROPER: Registering directly without factory when constructor has primitives
        builder.services.add_singleton(IEmailService, EmailService)

        provider = builder.build()

        # Service is created, but with None for primitive parameters
        email_service = provider.get_service(IEmailService)

        # Warnings were logged
        assert any("smtp_host" in record.message for record in caplog.records)
        assert any("smtp_port" in record.message for record in caplog.records)

        # Service exists but has None values
        assert email_service.smtp_host is None
        assert email_service.smtp_port is None
        assert email_service.use_ssl is True  # This one has a default

        # The error occurs when developer tries to USE the None values
        with pytest.raises((TypeError, AttributeError)):
            # Trying to call string methods on None will fail
            _ = email_service.smtp_host.lower()


def test_registration_with_defaults_works():
    """Services with default values for primitives work fine."""
    builder = ApplicationBuilder()

    # NotificationService has default for app_name, so it works
    builder.services.add_factory(
        NotificationService,
        lambda p: NotificationService(
            email_service=None, app_name="TestApp"  # Would normally inject this
        ),
    )

    provider = builder.build()
    service = provider.get_service(NotificationService)

    assert service.app_name == "TestApp"


def test_mixed_primitive_and_complex_dependencies():
    """Complex types are injected, primitives with defaults are used."""

    class ConfigurableNotificationService:
        def __init__(
            self, email_service: IEmailService, prefix: str = "[NOTIFICATION]"
        ):
            self.email_service = email_service
            self.prefix = prefix

    builder = ApplicationBuilder()

    # Register email service with factory
    builder.services.add_factory(
        IEmailService, lambda p: EmailService("smtp.test.com", 25, False)
    )

    # Register notification service - will inject IEmailService, use default for prefix
    builder.services.add_singleton(ConfigurableNotificationService)

    provider = builder.build()
    service = provider.get_service(ConfigurableNotificationService)

    # Complex dependency was injected
    assert service.email_service is not None
    assert service.email_service.smtp_host == "smtp.test.com"

    # Primitive used its default
    assert service.prefix == "[NOTIFICATION]"


def test_instance_registration_bypasses_all_issues():
    """Pre-created instances work perfectly regardless of constructor parameters."""
    builder = ApplicationBuilder()

    # Create instance with all parameters
    email_instance = EmailService(
        smtp_host="mail.server.com", smtp_port=465, use_ssl=True
    )

    builder.services.add_instance(IEmailService, email_instance)

    provider = builder.build()
    service = provider.get_service(IEmailService)

    assert service is email_instance
    assert service.smtp_host == "mail.server.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

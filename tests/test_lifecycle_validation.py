"""Tests for service lifetime dependency validation."""

import pytest

from servicegraph import ApplicationBuilder


# Test services
class SingletonService:
    def get_value(self):
        return "singleton"


class TransientService:
    def get_value(self):
        return "transient"


class ScopedService:
    def get_value(self):
        return "scoped"


# Invalid: Singleton depending on Transient
class SingletonDependsOnTransient:
    def __init__(self, transient: TransientService):
        self.transient = transient


# Invalid: Singleton depending on Scoped
class SingletonDependsOnScoped:
    def __init__(self, scoped: ScopedService):
        self.scoped = scoped


# Invalid: Transient depending on Scoped
class TransientDependsOnScoped:
    def __init__(self, scoped: ScopedService):
        self.scoped = scoped


# Valid: Scoped depending on Transient
class ScopedDependsOnTransient:
    def __init__(self, transient: TransientService):
        self.transient = transient


# Valid: Scoped depending on Singleton
class ScopedDependsOnSingleton:
    def __init__(self, singleton: SingletonService):
        self.singleton = singleton


# Valid: Transient depending on Singleton
class TransientDependsOnSingleton:
    def __init__(self, singleton: SingletonService):
        self.singleton = singleton


def test_singleton_cannot_depend_on_transient():
    """Singleton services cannot depend on transient services."""
    builder = ApplicationBuilder()

    builder.services.add_transient(TransientService)

    with pytest.raises(
        ValueError, match="Singleton services cannot depend on transient services"
    ):
        builder.services.add_singleton(SingletonDependsOnTransient)


def test_singleton_cannot_depend_on_scoped():
    """Singleton services cannot depend on scoped services."""
    builder = ApplicationBuilder()

    builder.services.add_scoped(ScopedService)

    with pytest.raises(
        ValueError, match="Singleton services cannot depend on scoped services"
    ):
        builder.services.add_singleton(SingletonDependsOnScoped)


def test_transient_cannot_depend_on_scoped():
    """Transient services cannot depend on scoped services."""
    builder = ApplicationBuilder()

    builder.services.add_scoped(ScopedService)

    with pytest.raises(
        ValueError, match="Transient services cannot depend on scoped services"
    ):
        builder.services.add_transient(TransientDependsOnScoped)


def test_scoped_can_depend_on_transient():
    """Scoped services CAN depend on transient services (valid)."""
    builder = ApplicationBuilder()

    builder.services.add_transient(TransientService)
    builder.services.add_scoped(ScopedDependsOnTransient)  # Should not raise

    provider = builder.build()

    # Should work fine when used with 'with' statement
    with provider.get_service(ScopedDependsOnTransient) as service:
        assert service.transient.get_value() == "transient"


def test_scoped_can_depend_on_singleton():
    """Scoped services CAN depend on singleton services (valid)."""
    builder = ApplicationBuilder()

    builder.services.add_singleton(SingletonService)
    builder.services.add_scoped(ScopedDependsOnSingleton)  # Should not raise

    provider = builder.build()

    # Should work fine
    with provider.get_service(ScopedDependsOnSingleton) as service:
        assert service.singleton.get_value() == "singleton"


def test_transient_can_depend_on_singleton():
    """Transient services CAN depend on singleton services (valid)."""
    builder = ApplicationBuilder()

    builder.services.add_singleton(SingletonService)
    builder.services.add_transient(TransientDependsOnSingleton)  # Should not raise

    provider = builder.build()

    # Should work fine
    service = provider.get_service(TransientDependsOnSingleton)
    assert service.singleton.get_value() == "singleton"

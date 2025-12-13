"""
Service locator utilities for Python applications.
Provides easy access to services within any execution context via the singleton
service provider.
"""

from typing import Type, TypeVar, cast

from .request_context import RequestContext

T = TypeVar("T")


def get_service(service_type: Type[T]) -> T:
    """
    Get a service from the current execution's service provider.

    Args:
        service_type: The type of service to resolve

    Returns:
        The resolved service instance

    Raises:
        RuntimeError: If called outside of an execution context
        KeyError: If the service is not registered
    """
    service_provider = RequestContext.get_service_provider()
    if service_provider is None:
        raise RuntimeError(
            "No service provider available. Must be called "
            "within an execution context."
        )

    return cast(T, service_provider.get_service(service_type))


def get_named_service(service_type: Type[T], name: str) -> T:
    """
    Get a named service from the current execution's service provider.

    Args:
        service_type: The type of service to resolve
        name: The name of the specific implementation

    Returns:
        The resolved service instance

    Raises:
        RuntimeError: If called outside of an execution context
        KeyError: If the named service is not registered
    """
    service_provider = RequestContext.get_service_provider()
    if service_provider is None:
        raise RuntimeError(
            "No service provider available. Must be called "
            "within an execution context."
        )

    return cast(T, service_provider.get_named_service(service_type, name))

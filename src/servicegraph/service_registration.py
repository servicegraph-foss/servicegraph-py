from typing import TYPE_CHECKING, Any, Callable, Optional

from .service_lifetime import ServiceLifetime

if TYPE_CHECKING:
    from .service_provider import ServiceProvider


class ServiceRegistration:
    def __init__(
        self,
        service_type: type[Any],
        implementation: type[Any],
        lifetime: ServiceLifetime,
        factory: Callable[["ServiceProvider"], Any],
        name: Optional[str] = None,
    ):
        self.service_type = service_type
        self.implementation = implementation
        self.lifetime = lifetime
        self.factory = factory
        self.name = name  # None for unnamed services, string for named services

    @property
    def is_named(self) -> bool:
        """Returns True if this is a named service registration"""
        return self.name is not None

    @property
    def registration_key(self) -> str:
        """Generate a unique key for this registration"""
        service_key = self._get_service_key(self.service_type)
        if self.is_named:
            return f"{service_key}#{self.name}"
        return service_key

    def _get_service_key(self, service_type: type[Any]) -> str:
        """Generate a unique key for the service type, handling generic types like Callable"""
        if hasattr(service_type, "__name__"):
            return service_type.__name__
        else:
            # Handle generic types like Callable[[], SomeClass]
            return str(service_type)

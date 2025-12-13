import inspect
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from .dependency_injection_utils import extract_named_dependencies, get_base_type
from .service_lifetime import ServiceLifetime
from .service_registration import ServiceRegistration
from .type_hints import T

if TYPE_CHECKING:
    from .service_provider import ServiceProvider  # Only imported during type checking

# Set up logger for dependency injection warnings
logger = logging.getLogger(__name__)


class ServiceCollection:
    def __init__(self) -> None:
        # Single dictionary to hold all service registrations
        self._registrations: Dict[str, ServiceRegistration] = {}

    def _validate_implementation_type(
        self,
        service_type: Any,
        implementation: Any,
        method_name: str = "add",
    ) -> None:
        """
        Validate that the implementation type is compatible with the service type.

        :param service_type: The service type/interface
        :param implementation: The implementation type
        :param method_name: The method name for error reporting
        :raises TypeError: If implementation doesn't implement service_type
        """
        # Skip validation if they're the same type (common for concrete classes)
        if service_type == implementation:
            return

        # Skip validation for non-class types (like generic types, functions, etc.)
        if not inspect.isclass(service_type) or not inspect.isclass(implementation):
            return

        # Check if implementation is a subclass of service_type
        # Note: issubclass() can raise TypeError for some complex generic types
        try:
            is_valid_subclass = issubclass(implementation, service_type)
        except TypeError:
            # Can't validate complex types like generics - skip validation
            return

        if not is_valid_subclass:
            raise TypeError(
                f"Invalid registration in {method_name}(): "
                f"'{implementation.__name__}' does not implement '{service_type.__name__}'. "
                f"Ensure that {implementation.__name__} inherits from or implements {service_type.__name__}."
            )

    # Core registration methods
    def add(
        self,
        service_type: type[Any],
        implementation: Optional[type[T]] = None,
        factory: Optional[Callable[["ServiceProvider"], Any]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
        name: Optional[str] = None,
    ) -> "ServiceCollection":
        """
        Core registration method that handles all scenarios.

        :param service_type: The type/interface being registered
        :param implementation: The concrete implementation (optional)
        :param factory: Custom factory function (optional)
        :param lifetime: Service lifetime (default: Singleton)
        :param name: Service name for named services (optional)
        :raises TypeError: If implementation doesn't implement service_type
        """
        if factory is not None:
            # Factory-based registration - skip implementation validation since factory handles it
            registration = ServiceRegistration(
                service_type=service_type,
                implementation=implementation or service_type,
                lifetime=lifetime,
                factory=factory,
                name=name,
            )
        else:
            # Implementation-based registration
            if implementation is None:
                implementation = service_type

            # Validate that implementation is compatible with service_type
            self._validate_implementation_type(service_type, implementation, "add")

            registration = ServiceRegistration(
                service_type=service_type,
                implementation=implementation,
                lifetime=lifetime,
                factory=self._create_factory(implementation, lifetime),
                name=name,
            )

        self._registrations[registration.registration_key] = registration
        return self

    # Convenience methods for common patterns
    def add_singleton(
        self, service_type: type[Any], implementation: Optional[type[T]] = None
    ) -> "ServiceCollection":
        """
        Add a singleton service.

        :param service_type: The service type/interface
        :param implementation: The implementation type (optional, defaults to service_type)
        :raises TypeError: If implementation doesn't implement service_type
        """
        return self.add(
            service_type, implementation, lifetime=ServiceLifetime.SINGLETON
        )

    def add_scoped(
        self, service_type: type[Any], implementation: Optional[type[T]] = None
    ) -> "ServiceCollection":
        """
        Add a scoped service.

        :param service_type: The service type/interface
        :param implementation: The implementation type (optional, defaults to service_type)
        :raises TypeError: If implementation doesn't implement service_type
        """
        return self.add(service_type, implementation, lifetime=ServiceLifetime.SCOPED)

    def add_transient(
        self, service_type: type[Any], implementation: Optional[type[T]] = None
    ) -> "ServiceCollection":
        """
        Add a transient service.

        :param service_type: The service type/interface
        :param implementation: The implementation type (optional, defaults to service_type)
        :raises TypeError: If implementation doesn't implement service_type
        """
        return self.add(
            service_type, implementation, lifetime=ServiceLifetime.TRANSIENT
        )

    def add_factory(
        self,
        service_type: type[Any],
        factory: Callable[["ServiceProvider"], Any],
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ) -> "ServiceCollection":
        """
        Add a service using a factory function.

        :param service_type: The service type/interface
        :param factory: Factory function that creates the service instance
        :param lifetime: Service lifetime (default: Singleton)
        """
        return self.add(service_type, factory=factory, lifetime=lifetime)

    def add_named(
        self,
        name: str,
        service_type: type[Any],
        implementation: Optional[type[T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ) -> "ServiceCollection":
        """
        Add a named service.

        :param name: The service name
        :param service_type: The service type/interface
        :param implementation: The implementation type (optional, defaults to service_type)
        :param lifetime: Service lifetime (default: Singleton)
        :raises TypeError: If implementation doesn't implement service_type
        """
        return self.add(service_type, implementation, lifetime=lifetime, name=name)

    def add_named_factory(
        self,
        name: str,
        service_type: type[Any],
        factory: Callable[["ServiceProvider"], Any],
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ) -> "ServiceCollection":
        """
        Add a named service using a factory function.

        :param name: The service name
        :param service_type: The service type/interface
        :param factory: Factory function that creates the service instance
        :param lifetime: Service lifetime (default: Singleton)
        """
        return self.add(service_type, factory=factory, lifetime=lifetime, name=name)

    def add_instance(
        self, service_type: type[Any], instance: Any
    ) -> "ServiceCollection":
        """
        Add a pre-configured instance as a singleton service.

        :param service_type: The service type/interface
        :param instance: The pre-configured instance
        :raises TypeError: If instance is not compatible with service_type
        """
        # Validate that the instance is compatible with the service type
        if not isinstance(instance, service_type):
            raise TypeError(
                f"Invalid registration in add_instance(): "
                f"Instance of type '{type(instance).__name__}' is not compatible with service type '{service_type.__name__}'. "
                f"Ensure the instance implements or inherits from {service_type.__name__}."
            )

        def instance_factory(provider: "ServiceProvider") -> Any:
            return instance

        return self.add(
            service_type, factory=instance_factory, lifetime=ServiceLifetime.SINGLETON
        )

    def remove(self, service_type: type[Any], name: Optional[str] = None) -> bool:
        """
        Remove a service registration by type and optional name.

        :param service_type: The service type to remove
        :param name: Optional name for named services
        :return: True if the service was found and removed, False otherwise
        """
        if name:
            registration_key = f"{self._get_service_key(service_type)}#{name}"
        else:
            registration_key = self._get_service_key(service_type)

        if registration_key in self._registrations:
            del self._registrations[registration_key]
            return True
        return False

    def remove_all_by_type(self, service_type: type[Any]) -> int:
        """
        Remove all registrations for a specific service type (including named variants).

        :param service_type: The service type to remove
        :return: Number of registrations removed
        """
        service_key = self._get_service_key(service_type)
        keys_to_remove = [
            key
            for key, reg in self._registrations.items()
            if reg.service_type == service_type
        ]

        for key in keys_to_remove:
            del self._registrations[key]

        return len(keys_to_remove)

    def remove_all_by_implementation(self, implementation: type[Any]) -> int:
        """
        Remove all registrations that use a specific implementation type.

        :param implementation: The implementation type to remove
        :return: Number of registrations removed
        """
        keys_to_remove = [
            key
            for key, reg in self._registrations.items()
            if reg.implementation == implementation
        ]

        for key in keys_to_remove:
            del self._registrations[key]

        return len(keys_to_remove)

    def remove_all_named(self) -> int:
        """
        Remove all named service registrations.

        :return: Number of registrations removed
        """
        keys_to_remove = [
            key for key, reg in self._registrations.items() if reg.is_named
        ]

        for key in keys_to_remove:
            del self._registrations[key]

        return len(keys_to_remove)

    def clear(self) -> None:
        """Remove all service registrations."""
        self._registrations.clear()

    def _get_service_key(self, service_type: type[Any]) -> str:
        """Generate a unique key for the service type."""
        if hasattr(service_type, "__name__"):
            return service_type.__name__
        else:
            # Handle generic types
            return str(service_type)

    def _is_primitive_type(self, param_type: type[Any]) -> bool:
        """
        Check if a type is a primitive/built-in type that should not be injected.

        Primitive types include: str, int, float, bool, bytes, bytearray,
        complex, list, dict, set, tuple, frozenset, and their typing equivalents.

        :param param_type: The parameter type to check
        :return: True if the type is primitive, False otherwise
        """
        # Get the origin type for generic types (e.g., List[str] -> list)
        origin = getattr(param_type, "__origin__", None)
        if origin is not None:
            param_type = origin

        # List of primitive/built-in types that should not be injected
        primitive_types = (
            str,
            int,
            float,
            bool,
            bytes,
            bytearray,
            complex,
            list,
            dict,
            set,
            tuple,
            frozenset,
            type(None),  # NoneType
        )

        return param_type in primitive_types or (
            hasattr(param_type, "__module__") and param_type.__module__ == "builtins"
        )

    def _validate_lifecycle_dependency(
        self,
        parent_lifetime: ServiceLifetime,
        dependency_type: type[Any],
        parent_name: str,
        param_name: str,
    ) -> None:
        """
        Validate that the dependency's lifetime is compatible with the parent service's lifetime.

        Rules:
        - Singleton services cannot depend on Transient or Scoped services (would break singleton semantics)
        - Transient services cannot depend on Scoped services (scoped has narrower lifetime)
        - Scoped can depend on Transient/Singleton (OK - longer or equal lifetimes)
        - Transient can depend on Singleton (OK - longer lifetime)

        :param parent_lifetime: The lifetime of the service being created
        :param dependency_type: The type of the dependency
        :param parent_name: Name of the parent service for error messages
        :param param_name: Name of the parameter for error messages
        :raises ValueError: If the dependency lifetime is incompatible
        """
        # Find the dependency's registration
        dep_key = self._get_service_key(dependency_type)
        if dep_key not in self._registrations:
            # Dependency not registered - will be caught elsewhere
            return

        dep_registration = self._registrations[dep_key]
        dep_lifetime = dep_registration.lifetime

        # Singleton cannot depend on Transient or Scoped
        if parent_lifetime == ServiceLifetime.SINGLETON:
            if dep_lifetime in (ServiceLifetime.TRANSIENT, ServiceLifetime.SCOPED):
                raise ValueError(
                    f"Invalid dependency in {parent_name}: Singleton services cannot depend on "
                    f"{dep_lifetime.name.lower()} services.\n"
                    f"Parameter '{param_name}' of type '{dependency_type.__name__}' is registered as "
                    f"{dep_lifetime.name.lower()}, but {parent_name} is a singleton.\n"
                    f"This would break singleton semantics as the dependency could have different instances.\n"
                    f"Solution: Register '{dependency_type.__name__}' as a singleton, or change {parent_name} "
                    f"to transient/scoped."
                )

        # Transient cannot depend on Scoped
        elif parent_lifetime == ServiceLifetime.TRANSIENT:
            if dep_lifetime == ServiceLifetime.SCOPED:
                raise ValueError(
                    f"Invalid dependency in {parent_name}: Transient services cannot depend on scoped services.\n"
                    f"Parameter '{param_name}' of type '{dependency_type.__name__}' is registered as scoped, "
                    f"but {parent_name} is transient.\n"
                    f"Scoped services have a narrower lifetime than transient services.\n"
                    f"Solution: Register '{dependency_type.__name__}' as transient or singleton, or change "
                    f"{parent_name} to scoped."
                )

        # Scoped can depend on anything (Singleton, Transient, Scoped) - no validation needed

    def _create_factory(
        self, implementation: type[T], lifetime: ServiceLifetime
    ) -> Callable[["ServiceProvider"], Any]:
        """
        Creates a factory function for the given implementation type.
        Handles dependency injection by analyzing constructor parameters.
        Supports both regular dependencies and named dependencies using Annotated types.

        :param implementation: The implementation class
        :param lifetime: The lifetime of the service being registered
        :return: Factory function that creates instances
        """
        try:
            sig = inspect.signature(implementation.__init__)
            # Check if this is the default object.__init__ (no custom constructor)
            if (
                hasattr(implementation.__init__, "__qualname__")
                and implementation.__init__.__qualname__ == "object.__init__"
            ):
                # Class has no custom constructor, just instantiate directly
                def simple_factory(provider: "ServiceProvider") -> Any:
                    return implementation()

                return simple_factory
        except (ValueError, TypeError):
            # Handle cases where signature inspection fails (e.g., built-in types, C extensions)
            def simple_factory(provider: "ServiceProvider") -> Any:
                return implementation()

            return simple_factory

        # Check if constructor has no parameters beyond 'self'
        params = [p for name, p in sig.parameters.items() if name != "self"]
        if not params:
            # Constructor exists but takes no parameters
            def simple_factory(provider: "ServiceProvider") -> Any:
                return implementation()

            return simple_factory

        # Extract named dependencies from annotations
        named_deps = extract_named_dependencies(implementation)

        # Validate lifecycle dependencies during registration (not at runtime)
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                # No type annotation - skip validation
                continue

            # Get the base type (handling Annotated types)
            base_type = get_base_type(param_type)

            # Skip primitive/built-in types
            if self._is_primitive_type(base_type):
                continue

            # Validate lifecycle compatibility
            self._validate_lifecycle_dependency(
                lifetime, base_type, implementation.__name__, param_name
            )

        def factory(provider: "ServiceProvider") -> Any:
            kwargs: Dict[str, Any] = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                param_type = param.annotation
                if param_type == inspect.Parameter.empty:
                    # Parameter has no type annotation
                    if param.default != inspect.Parameter.empty:
                        # Has default value, skip injection
                        continue
                    else:
                        raise ValueError(
                            f"Parameter '{param_name}' in {implementation.__name__} constructor "
                            f"has no type annotation and no default value"
                        )

                # Get the base type (handling Annotated types)
                base_type = get_base_type(param_type)

                # Skip primitive/built-in types - they should not be injected
                if self._is_primitive_type(base_type):
                    if param.default != inspect.Parameter.empty:
                        # Has default value, skip injection and use default
                        continue
                    else:
                        # No default value - log warning and provide None
                        logger.warning(
                            f"Parameter '{param_name}' of type '{base_type.__name__}' in "
                            f"{implementation.__name__} constructor is a primitive type with no default value. "
                            f"Primitive types cannot be injected. Providing None. "
                            f"Consider providing a default value or using a factory function for registration."
                        )
                        # Provide None so the service can be created
                        # The developer will get an error when they try to use None as the expected type
                        kwargs[param_name] = None
                        continue

                try:
                    # Check if this parameter needs a named service
                    if param_name in named_deps:
                        service_name = named_deps[param_name]
                        # Mark as dependency injection (is_dependency=True)
                        kwargs[param_name] = provider._get_or_create_instance(
                            provider._collection._registrations[
                                f"{provider._get_service_key(base_type)}#{service_name}"
                            ],
                            session_id=None,
                            is_dependency=True,
                        )
                    else:
                        # Regular service resolution - mark as dependency injection
                        registration_key = provider._get_service_key(base_type)
                        if registration_key in provider._collection._registrations:
                            kwargs[param_name] = provider._get_or_create_instance(
                                provider._collection._registrations[registration_key],
                                session_id=None,
                                is_dependency=True,
                            )
                        else:
                            # Service not registered, will be caught below
                            raise KeyError(f"Service {base_type} not registered")

                except KeyError as e:
                    # Service not registered
                    if param.default != inspect.Parameter.empty:
                        # Parameter has default value, use it
                        continue
                    else:
                        if param_name in named_deps:
                            raise KeyError(
                                f"Cannot resolve named dependency '{param_name}' of type {base_type} "
                                f"with name '{named_deps[param_name]}' for {implementation.__name__}. "
                                f"Named service not registered."
                            ) from e
                        else:
                            raise KeyError(
                                f"Cannot resolve dependency '{param_name}' of type {base_type} "
                                f"for {implementation.__name__}. Service not registered."
                            ) from e
                except Exception as e:
                    # Other resolution errors
                    raise RuntimeError(
                        f"Error resolving dependency '{param_name}' of type {base_type} "
                        f"for {implementation.__name__}: {str(e)}"
                    ) from e

            try:
                return implementation(**kwargs)
            except TypeError as e:
                # Provide helpful error if instantiation fails
                error_msg = str(e)
                raise TypeError(
                    f"Failed to create instance of {implementation.__name__}. "
                    f"Original error: {error_msg}\n"
                    f"This may be due to incompatible constructor parameters. "
                    f"Consider using a factory function for complex initialization."
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Error creating instance of {implementation.__name__}: {str(e)}"
                ) from e

        return factory

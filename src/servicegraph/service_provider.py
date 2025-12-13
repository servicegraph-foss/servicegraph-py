import atexit
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, List, Optional, cast

from .service_collection import ServiceCollection
from .service_lifetime import ServiceLifetime
from .type_hints import T


class ServiceNotRegisteredException(Exception):
    """Exception raised when a requested service is not registered in the container."""

    pass


class CircularDependencyException(Exception):
    """Exception raised when a circular dependency is detected during service resolution."""

    pass


class ScopedServiceContextManager:
    """Context manager wrapper for scoped services that enforces proper usage."""

    def __init__(
        self, service_instance: Any, session_id: str, provider: "ServiceProvider"
    ) -> None:
        self._service_instance = service_instance
        self._session_id = session_id
        self._provider = provider
        self._entered = False
        self._exited = False

    def __enter__(self) -> Any:
        if self._exited:
            raise RuntimeError("Scoped service has already been disposed")
        self._entered = True
        return self._service_instance

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._exited = True
        # Dispose of the scoped service instance itself
        if hasattr(self._service_instance, "dispose"):
            try:
                self._service_instance.dispose()
            except Exception as e:
                print(
                    f"Error disposing scoped service {type(self._service_instance).__name__}: {e}"
                )
        elif hasattr(self._service_instance, "close"):
            try:
                self._service_instance.close()
            except Exception as e:
                print(
                    f"Error closing scoped service {type(self._service_instance).__name__}: {e}"
                )

        # Dispose all scoped dependencies that were created within this scope
        if self._session_id in self._provider._scoped_instances:
            scoped_deps = self._provider._scoped_instances[self._session_id]
            for scoped_dep in scoped_deps:
                if (
                    scoped_dep is not self._service_instance
                ):  # Don't double-dispose the main instance
                    if hasattr(scoped_dep, "dispose"):
                        try:
                            scoped_dep.dispose()
                        except Exception as e:
                            print(
                                f"Error disposing scoped dependency {type(scoped_dep).__name__}: {e}"
                            )
                    elif hasattr(scoped_dep, "close"):
                        try:
                            scoped_dep.close()
                        except Exception as e:
                            print(
                                f"Error closing scoped dependency {type(scoped_dep).__name__}: {e}"
                            )
            # Clean up the tracking list
            del self._provider._scoped_instances[self._session_id]

        # Note: We do NOT dispose the session here. The session_id was used to get
        # consistent transient instances during service creation, but the session
        # itself should persist and be managed separately by the caller.

    def __getattr__(self, name: str) -> Any:
        # Prevent direct access to service methods without context manager
        if not self._entered or self._exited:
            service_type = type(self._service_instance).__name__
            raise RuntimeError(
                f"Scoped service '{service_type}' must be used within a 'with' statement.\n"
                f"Correct usage:\n"
                f"  with service_provider.get_service({service_type}) as service:\n"
                f"      service.{name}()  # Now you can call methods\n"
                f"\nScoped services are automatically disposed when the 'with' block exits."
            )
        return getattr(self._service_instance, name)


class ServiceProvider:
    _instance = None
    _lock = RLock()

    def __new__(
        cls, service_collection: Optional[ServiceCollection] = None
    ) -> "ServiceProvider":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ServiceProvider, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, service_collection: Optional[ServiceCollection] = None) -> None:
        # Always update the collection reference to support dynamic
        # reconfiguration
        if service_collection is not None:
            self._collection = service_collection

        # Only initialize instance variables once
        if hasattr(self, "_initialized") and self._initialized:
            return

        # First-time initialization
        # Only cache singleton instances
        self._singleton_instances: Dict[str, Any] = {}

        # Session management for transient services
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._session_timestamps: Dict[str, datetime] = {}
        self._session_timeout = timedelta(minutes=30)
        self._instance_lock = RLock()

        # Thread-local storage for active session context during scoped service creation
        import threading

        self._active_session_context = threading.local()

        # Track scoped instances created within a scope for proper disposal
        self._scoped_instances: Dict[str, List[Any]] = (
            {}
        )  # session_id -> list of scoped instances

        # Register cleanup for singletons when process exits (Azure Functions worker recycling)
        atexit.register(self._cleanup_singletons)

        self._initialized: bool = True

    def get_service(self, service_type: type[T], session_id: Optional[str] = None) -> T:
        """
        Resolves a service from the container by type.
        For named services, use get_named_service instead.

        :param service_type: The service type to resolve
        :param session_id: Optional session ID for session-scoped transient services.
                          Required when resolving scoped services that depend on transient services.
        :raises ServiceNotRegisteredException: If the service is not registered
        """
        # Directly construct the registration key
        registration_key = self._get_service_key(service_type)

        if registration_key not in self._collection._registrations:
            # Provide helpful error message with suggestions
            available_services = list(self._collection._registrations.keys())
            similar_services = [
                svc
                for svc in available_services
                if service_type.__name__.lower() in svc.lower()
            ]

            error_msg = (
                f"Service of type '{service_type.__name__}' is not registered.\n"
                f"Did you forget to call one of these methods?\n"
                f"  • builder.services.add_singleton({service_type.__name__}, YourImplementation)\n"
                f"  • builder.services.add_transient({service_type.__name__}, YourImplementation)\n"
                f"  • builder.services.add_scoped({service_type.__name__}, YourImplementation)\n"
                f"  • builder.services.add_factory({service_type.__name__}, your_factory_function)"
            )

            if similar_services:
                error_msg += "\n\nDid you mean one of these registered services?\n"
                for svc in similar_services[:3]:  # Show max 3 suggestions
                    error_msg += f"  • {svc}\n"

            if available_services:
                error_msg += (
                    f"\nCurrently registered services ({len(available_services)}):\n"
                )
                for svc in sorted(available_services)[:5]:  # Show first 5
                    error_msg += f"  • {svc}\n"
                if len(available_services) > 5:
                    error_msg += f"  ... and {len(available_services) - 5} more"
            else:
                error_msg += "\n\nNo services are currently registered. Make sure to configure your services before building the ServiceProvider."

            raise ServiceNotRegisteredException(error_msg)

        registration = self._collection._registrations[registration_key]
        return cast(T, self._get_or_create_instance(registration, session_id))

    def get_named_service(
        self, service_type: type[T], name: str, session_id: Optional[str] = None
    ) -> T:
        """
        Resolves a named service from the container.

        :param service_type: The interface/type to resolve
        :param name: The name of the specific implementation to resolve
        :param session_id: Optional session ID for session-scoped transient services
        :return: The resolved service instance
        :raises ServiceNotRegisteredException: If the named service is not registered
        """
        # Directly construct the registration key for named services
        registration_key = f"{self._get_service_key(service_type)}#{name}"

        if registration_key not in self._collection._registrations:
            # Provide helpful error message with available named services
            available_names = []
            for key, reg in self._collection._registrations.items():
                if reg.service_type == service_type and reg.is_named:
                    available_names.append(reg.name)

            error_msg = (
                f"Named service '{name}' is not registered for type '{service_type.__name__}'.\n"
                f"To register a named service, use:\n"
                f"  builder.services.add_named('{name}', {service_type.__name__}, YourImplementation)\n"
                f"  # or\n"
                f"  builder.services.add_named_factory('{name}', {service_type.__name__}, your_factory_function)"
            )

            if available_names:
                error_msg += (
                    f"\n\nAvailable named services for {service_type.__name__}:\n"
                )
                for available_name in sorted(
                    [n for n in available_names if n is not None]
                ):
                    error_msg += f"  • '{available_name}'\n"
                error_msg += "\nTo use an available service:\n"
                error_msg += f"  provider.get_named_service({service_type.__name__}, '{available_names[0]}')"
            else:
                # Check if the service type itself is registered (non-named)
                base_key = self._get_service_key(service_type)
                if base_key in self._collection._registrations:
                    error_msg += f"\n\nNote: {service_type.__name__} is registered as a regular service (not named).\n"
                    error_msg += (
                        f"Use: provider.get_service({service_type.__name__}) instead."
                    )
                else:
                    error_msg += f"\n\nNo services (named or regular) are registered for type {service_type.__name__}."

            raise ServiceNotRegisteredException(error_msg)

        registration = self._collection._registrations[registration_key]
        return cast(T, self._get_or_create_instance(registration, session_id))

    def get_all_named_services(
        self, service_type: type[T], session_id: Optional[str] = None
    ) -> Dict[str, T]:
        """
        Resolves all named services for a given type.

        :param service_type: The interface/type to resolve
        :param session_id: Optional session ID for session-scoped transient services
        :return: Dictionary mapping names to service instances
        """
        result: dict[str, T] = {}
        for registration in self._collection._registrations.values():
            if registration.service_type == service_type and registration.is_named:
                assert registration.name is not None
                result[registration.name] = cast(
                    T, self._get_or_create_instance(registration, session_id)
                )

        return result

    def dispose_session(self, session_id: str) -> bool:
        """
        Dispose all transient service instances for a specific session.

        :param session_id: The session ID to dispose
        :return: True if session existed and was disposed, False if session didn't exist
        """
        with self._instance_lock:
            if session_id in self._sessions:
                session_services = self._sessions[session_id]
                for service in session_services.values():
                    self._dispose_service(service)
                del self._sessions[session_id]
                del self._session_timestamps[session_id]
                return True
            return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session."""
        with self._instance_lock:
            if session_id not in self._sessions:
                return None

            session_services = self._sessions[session_id]
            return {
                "session_id": session_id,
                "service_count": len(session_services),
                "created_at": self._session_timestamps[session_id].isoformat(),
                "services": list(session_services.keys()),
            }

    def get_active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def get_all_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered services.

        :return: Dictionary with service information including type, lifetime, and whether it's named
        """
        services = {}

        for registration in self._collection._registrations.values():
            service_key = registration.registration_key

            # Determine if this is a factory-based registration
            is_factory = (
                registration.implementation != registration.service_type
                or hasattr(registration.factory, "__name__")
            )

            # For factory registrations, try to get a more descriptive name
            impl_name = (
                registration.implementation.__name__
                if registration.implementation
                else "Factory"
            )
            if is_factory and hasattr(registration.factory, "__name__"):
                impl_name = f"Factory({registration.factory.__name__})"
            elif is_factory and hasattr(registration.factory, "__qualname__"):
                impl_name = f"Factory({registration.factory.__qualname__})"

            services[service_key] = {
                "service_type": registration.service_type.__name__,
                "implementation_type": impl_name,
                "lifetime": registration.lifetime.name,
                "is_named": registration.is_named,
                "name": registration.name if registration.is_named else None,
                "is_factory": is_factory,
                "is_instance": (
                    "instance_factory" in str(registration.factory)
                    if registration.factory is not None
                    else False
                ),
            }

        return services

    def get_services_by_type(
        self, service_type: Optional[type[Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all services of a specific type, or all services if no type specified.

        :param service_type: Optional type to filter by
        :return: Dictionary with matching service information
        """
        all_services = self.get_all_services()

        if service_type is None:
            return all_services

        type_name = service_type.__name__
        return {
            key: info
            for key, info in all_services.items()
            if info["service_type"] == type_name
        }

    def get_service_types(self) -> List[str]:
        """
        Get a list of all registered service type names.

        :return: List of service type names
        """
        return list(
            set(
                reg.service_type.__name__
                for reg in self._collection._registrations.values()
            )
        )

    def has_service(self, service_type: type[Any], name: Optional[str] = None) -> bool:
        """
        Check if a service is registered.

        :param service_type: The service type to check
        :param name: Optional name for named services
        :return: True if the service is registered
        """
        if name:
            registration_key = f"{self._get_service_key(service_type)}#{name}"
        else:
            registration_key = self._get_service_key(service_type)

        return registration_key in self._collection._registrations

    def clear_singleton_instances(self) -> None:
        """
        Clear all cached singleton instances.
        Useful for scenarios where you need to reset application state.
        """
        with self._lock:
            # Dispose of singletons before clearing
            for instance in self._singleton_instances.values():
                self._dispose_service(instance)
            self._singleton_instances.clear()

    def clear_all_sessions(self) -> None:
        """
        Clear all active sessions and their transient service instances.
        """
        with self._instance_lock:
            for session_id in list(self._sessions.keys()):
                self.dispose_session(session_id)

    def clear_all_instances(self) -> None:
        """
        Clear all cached instances (singletons and sessions).
        This resets all service state while keeping registrations intact.
        """
        self.clear_singleton_instances()
        self.clear_all_sessions()

    def remove_service(
        self, service_type: type[Any], name: Optional[str] = None
    ) -> bool:
        """
        Remove a service registration and its cached instance.

        :param service_type: The service type to remove
        :param name: Optional name for named services
        :return: True if the service was found and removed, False otherwise
        """
        # Build the registration key
        if name:
            registration_key = f"{self._get_service_key(service_type)}#{name}"
        else:
            registration_key = self._get_service_key(service_type)

        # Remove from collection
        removed = self._collection.remove(service_type, name)

        if removed:
            # Clear cached singleton instance if it exists
            if registration_key in self._singleton_instances:
                with self._lock:
                    instance = self._singleton_instances.pop(registration_key, None)
                    if instance:
                        self._dispose_service(instance)

            # Clear all session instances for this service (transient)
            with self._instance_lock:
                for session_id, session_services in self._sessions.items():
                    if registration_key in session_services:
                        instance = session_services.pop(registration_key)
                        self._dispose_service(instance)

        return removed

    def remove_all_by_type(self, service_type: type[Any]) -> int:
        """
        Remove all registrations for a service type and clear cached instances.

        :param service_type: The service type to remove
        :return: Number of registrations removed
        """
        # Get all keys for this service type before removing
        keys_to_clear = [
            key
            for key, reg in self._collection._registrations.items()
            if reg.service_type == service_type
        ]

        # Remove from collection
        count = self._collection.remove_all_by_type(service_type)

        # Clear cached singleton instances
        with self._lock:
            for key in keys_to_clear:
                if key in self._singleton_instances:
                    instance = self._singleton_instances.pop(key)
                    self._dispose_service(instance)

        # Clear all session instances for these services (transient)
        with self._instance_lock:
            for session_id, session_services in self._sessions.items():
                for key in keys_to_clear:
                    if key in session_services:
                        instance = session_services.pop(key)
                        self._dispose_service(instance)

        return count

    def remove_all_by_implementation(self, implementation: type[Any]) -> int:
        """
        Remove all registrations using an implementation and clear cached instances.

        :param implementation: The implementation type to remove
        :return: Number of registrations removed
        """
        # Get all keys for this implementation type before removing
        keys_to_clear = [
            key
            for key, reg in self._collection._registrations.items()
            if reg.implementation == implementation
        ]

        # Remove from collection
        count = self._collection.remove_all_by_implementation(implementation)

        # Clear cached singleton instances
        with self._lock:
            for key in keys_to_clear:
                if key in self._singleton_instances:
                    instance = self._singleton_instances.pop(key)
                    self._dispose_service(instance)

        # Clear all session instances for these services (transient)
        with self._instance_lock:
            for session_id, session_services in self._sessions.items():
                for key in keys_to_clear:
                    if key in session_services:
                        instance = session_services.pop(key)
                        self._dispose_service(instance)

        return count

    def _get_or_create_instance(
        self,
        registration: Any,
        session_id: Optional[str] = None,
        is_dependency: bool = False,
    ) -> Any:
        """
        Creates or retrieves a service instance based on its lifetime.

        For scoped services with transient dependencies, session_id is required to ensure
        proper dependency resolution.

        :param registration: The service registration
        :param session_id: Optional session ID for transient/scoped services
        :param is_dependency: True if being resolved as a dependency injection, False if direct resolution
        """
        if registration.lifetime == ServiceLifetime.TRANSIENT:
            # For transient services, check if we're in a scoped context
            # If so, use the scoped session_id for consistency
            active_session = getattr(self._active_session_context, "session_id", None)
            effective_session_id = session_id or active_session

            if effective_session_id:
                return self._get_or_create_session_service(
                    registration, effective_session_id
                )
            else:
                # No session ID, create new instance each time
                return registration.factory(self)

        elif registration.lifetime == ServiceLifetime.SINGLETON:
            # Singletons are shared across all scopes
            if registration.registration_key not in self._singleton_instances:
                with self._lock:
                    if registration.registration_key not in self._singleton_instances:
                        self._singleton_instances[registration.registration_key] = (
                            registration.factory(self)
                        )
            return self._singleton_instances[registration.registration_key]

        elif registration.lifetime == ServiceLifetime.SCOPED:
            # For scoped services, establish session context and create instance
            # Generate a session_id if not provided (only for direct resolution)
            if session_id is None and not is_dependency:
                import uuid

                session_id = f"scoped_{uuid.uuid4().hex[:8]}"

            # If this is a dependency injection, get the active session from context
            if is_dependency:
                active_session = getattr(
                    self._active_session_context, "session_id", None
                )
                if active_session:
                    session_id = active_session
                else:
                    # This shouldn't happen in normal usage, but fallback to creating a session
                    import uuid

                    session_id = f"scoped_{uuid.uuid4().hex[:8]}"

            # Initialize tracking list for this session if needed
            assert (
                session_id is not None
            ), "Session ID must be provided for scoped services"
            if session_id not in self._scoped_instances:
                self._scoped_instances[session_id] = []

            # Set the active session context so that any transient/scoped dependencies
            # will use this session_id
            prev_session = getattr(self._active_session_context, "session_id", None)
            self._active_session_context.session_id = session_id

            try:
                instance = registration.factory(self)

                # Track this scoped instance for disposal
                self._scoped_instances[session_id].append(instance)

                # Only wrap in context manager if this is a direct resolution,
                # not a dependency injection
                if is_dependency:
                    # Return raw instance for dependency injection
                    return instance
                else:
                    # Wrap in context manager for direct resolution
                    return ScopedServiceContextManager(instance, session_id, self)
            finally:
                # Restore previous session context (for nested scopes)
                self._active_session_context.session_id = prev_session

        else:
            valid_lifetimes = [lifetime.name for lifetime in ServiceLifetime]
            raise ValueError(
                f"Unknown service lifetime: {registration.lifetime}\n"
                f"Valid lifetimes are: {', '.join(valid_lifetimes)}\n"
                f"Use one of:\n"
                f"  • ServiceLifetime.SINGLETON - One instance for the entire application\n"
                f"  • ServiceLifetime.TRANSIENT - New instance every time\n"
                f"  • ServiceLifetime.SCOPED - One instance per scope (use with 'with' statement)"
            )

    def _get_or_create_session_service(self, registration: Any, session_id: str) -> Any:
        """Get or create a session-scoped transient service instance."""
        with self._instance_lock:
            self._cleanup_expired_sessions()

            if session_id not in self._sessions:
                self._sessions[session_id] = {}
                self._session_timestamps[session_id] = datetime.now(timezone.utc)

            session_services = self._sessions[session_id]

            if registration.registration_key not in session_services:
                session_services[registration.registration_key] = registration.factory(
                    self
                )

            # Update timestamp
            self._session_timestamps[session_id] = datetime.now(timezone.utc)

            return session_services[registration.registration_key]

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions."""
        now = datetime.now(timezone.utc)
        expired_sessions = [
            session_id
            for session_id, timestamp in self._session_timestamps.items()
            if now - timestamp > self._session_timeout
        ]

        for session_id in expired_sessions:
            self.dispose_session(session_id)

    def _dispose_service(self, service: Any) -> None:
        """Dispose a single service instance."""
        if hasattr(service, "dispose"):
            try:
                service.dispose()
            except Exception:
                pass
        elif hasattr(service, "close"):
            try:
                service.close()
            except Exception:
                pass

    def _cleanup_singletons(self) -> None:
        """Cleanup singleton instances when process exits."""
        for instance in self._singleton_instances.values():
            if hasattr(instance, "dispose"):
                try:
                    instance.dispose()
                except Exception:
                    pass  # Ignore errors during shutdown
            elif hasattr(instance, "close"):
                try:
                    instance.close()
                except Exception:
                    pass  # Ignore errors during shutdown

    def _get_service_key(self, service_type: type[Any]) -> str:
        """Generate a unique key for the service type, handling generic types like Callable"""
        if hasattr(service_type, "__name__"):
            return service_type.__name__
        else:
            # Handle generic types like Callable[[], SomeClass]
            return str(service_type)

import threading
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
        self,
        service_instance: Any,
        scoped_deps: Optional[List[Any]] = None,
    ) -> None:
        self._service_instance = service_instance
        # Scoped dependencies injected into this service, in creation order.
        # Disposed in reverse order on __exit__ so consumers go before their deps.
        self._scoped_deps: List[Any] = scoped_deps or []
        self._entered = False
        self._exited = False

    def __enter__(self) -> Any:
        if self._exited:
            raise RuntimeError("Scoped service has already been disposed")
        self._entered = True
        return self._service_instance

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._exited = True
        # Dispose the root service first
        self._dispose_instance(self._service_instance)
        # Then dispose injected scoped dependencies in reverse creation order
        # (outer/consumer deps before the inner deps they rely on)
        for dep in reversed(self._scoped_deps):
            self._dispose_instance(dep)

    def _dispose_instance(self, instance: Any) -> None:
        if hasattr(instance, "dispose"):
            try:
                instance.dispose()
            except Exception as e:
                print(f"Error disposing {type(instance).__name__}: {e}")
        elif hasattr(instance, "close"):
            try:
                instance.close()
            except Exception as e:
                print(f"Error closing {type(instance).__name__}: {e}")

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
        if hasattr(self, "_initialized") and self._initialized:
            if service_collection is not None:
                raise RuntimeError(
                    "ServiceProvider has already been built. A second call to build() with a "
                    "new ServiceCollection is not allowed — singleton instances already cached "
                    "from the first build would be stale against the new registrations.\n"
                    "If you need to reset the provider between tests, call "
                    "ServiceProvider._reset_for_testing()."
                )
            return

        # First-time initialization
        self._collection = service_collection  # ← set once, here, under the guard
        self._singleton_instances: Dict[str, Any] = {}

        # Session management for transient services
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._session_timestamps: Dict[str, datetime] = {}
        self._session_timeout = timedelta(minutes=30)
        self._instance_lock = RLock()

        # Thread-local storage for active session context during scoped service creation
        self._active_session_context = threading.local()
        self._initialized: bool = True

    @property
    def collection(self) -> ServiceCollection:
        """Public access to the underlying ServiceCollection."""
        if self._collection is None:
            raise RuntimeError("ServiceProvider has not been initialized")
        return self._collection

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

        if not self.collection.has_registration(registration_key):
            # Provide helpful error message with suggestions
            available_services = list(self.collection.registration_keys())
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

        registration = self.collection.get_registration(registration_key)
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

        if not self.collection.has_registration(registration_key):
            # Provide helpful error message with available named services
            available_names = []
            for key, reg in self.collection.iter_registration_items():
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
                if self.collection.has_registration(base_key):
                    error_msg += f"\n\nNote: {service_type.__name__} is registered as a regular service (not named).\n"
                    error_msg += (
                        f"Use: provider.get_service({service_type.__name__}) instead."
                    )
                else:
                    error_msg += f"\n\nNo services (named or regular) are registered for type {service_type.__name__}."

            raise ServiceNotRegisteredException(error_msg)

        registration = self.collection.get_registration(registration_key)
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
        for registration in self.collection.iter_registrations():
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
        # Remove state under the lock, then dispose outside it so that user-defined
        # close()/dispose() methods cannot cause a deadlock by trying to acquire
        # _instance_lock from a concurrent thread.
        with self._instance_lock:
            if session_id not in self._sessions:
                return False
            services_to_dispose = list(self._sessions[session_id].values())
            del self._sessions[session_id]
            del self._session_timestamps[session_id]

        for service in services_to_dispose:
            self._dispose_service(service)
        return True

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

        for registration in self.collection.iter_registrations():
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
                for reg in self.collection.iter_registrations()
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

        return self.collection.has_registration(registration_key)

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
        # Collect all services and clear state under the lock, then dispose outside
        # to avoid holding _instance_lock during user-defined close()/dispose().
        with self._instance_lock:
            all_services = [
                service
                for session in self._sessions.values()
                for service in session.values()
            ]
            self._sessions.clear()
            self._session_timestamps.clear()

        for service in all_services:
            self._dispose_service(service)

    def clear_all_instances(self) -> None:
        """
        Clear all cached instances (singletons and sessions).
        This resets all service state while keeping registrations intact.
        """
        self.clear_singleton_instances()
        self.clear_all_sessions()

    @classmethod
    def _reset_for_testing(cls) -> None:
        """
        Soft-reset the singleton ServiceProvider for test isolation.

        Clears all cached singleton instances, sessions, and service registrations,
        then marks the provider as uninitialized so the next build() call
        re-initializes it in-place.  The singleton Python object is preserved.

        NOT for production use.
        """
        with cls._lock:
            if cls._instance is not None:
                inst = cls._instance
                try:
                    inst._cleanup_singletons()
                    inst.clear_all_sessions()
                except Exception:
                    pass
                inst._singleton_instances = {}
                inst._sessions = {}
                inst._session_timestamps = {}
                if inst._collection is not None:
                    inst._collection.clear()
                inst._initialized = False
            # _instance is intentionally preserved — singleton identity is retained

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
        removed = self.collection.remove(service_type, name)

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
            for key, reg in self.collection.iter_registration_items()
            if reg.service_type == service_type
        ]

        # Remove from collection
        count = self.collection.remove_all_by_type(service_type)

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
            for key, reg in self.collection.iter_registration_items()
            if reg.implementation == implementation
        ]

        # Remove from collection
        count = self.collection.remove_all_by_implementation(implementation)

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
            # Propagate active session context so transient dependencies created
            # during factory execution resolve consistently within the same session.
            prev_session = getattr(self._active_session_context, "session_id", None)
            effective_session = session_id or prev_session
            self._active_session_context.session_id = effective_session

            try:
                if is_dependency:
                    # Being injected into another service: return the raw instance.
                    # Only scoped instances are tracked in the collector — the TRANSIENT
                    # and SINGLETON branches never touch scoped_dep_stack, so neither
                    # longer-lived singletons nor already-transient instances are ever
                    # auto-disposed when the outer scope exits.
                    instance = registration.factory(self)
                    dep_stack: Optional[List[List[Any]]] = getattr(
                        self._active_session_context, "scoped_dep_stack", None
                    )
                    if dep_stack:
                        dep_stack[-1].append(instance)
                    return instance
                else:
                    # Direct resolution: push a fresh collector onto the thread-local
                    # stack so every scoped dependency created during factory execution
                    # is automatically captured and owned by this context manager.
                    dep_stack = getattr(
                        self._active_session_context, "scoped_dep_stack", None
                    )
                    if dep_stack is None:
                        self._active_session_context.scoped_dep_stack = []
                        dep_stack = self._active_session_context.scoped_dep_stack

                    collector: List[Any] = []
                    dep_stack.append(collector)
                    try:
                        instance = registration.factory(self)
                    finally:
                        dep_stack.pop()

                    return ScopedServiceContextManager(instance, scoped_deps=collector)
            finally:
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
        # _cleanup_expired_sessions removes state under _instance_lock and returns
        # the collected services; we dispose them AFTER releasing the lock.
        with self._instance_lock:
            expired_services = self._cleanup_expired_sessions()

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

            instance = session_services[registration.registration_key]

        for service in expired_services:
            self._dispose_service(service)

        return instance

    def _cleanup_expired_sessions(self) -> list[Any]:
        """Remove expired sessions and return their services for disposal.

        Must be called with _instance_lock held.  Returns the list of service
        instances that the caller must dispose *outside* the lock.
        """
        now = datetime.now(timezone.utc)
        expired_sessions = [
            session_id
            for session_id, timestamp in self._session_timestamps.items()
            if now - timestamp > self._session_timeout
        ]

        services_to_dispose: list[Any] = []
        for session_id in expired_sessions:
            services_to_dispose.extend(self._sessions[session_id].values())
            del self._sessions[session_id]
            del self._session_timestamps[session_id]

        return services_to_dispose

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

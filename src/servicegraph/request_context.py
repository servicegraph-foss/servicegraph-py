"""
Execution context management for web applications and batch jobs.
Provides thread-local storage for execution-scoped data including the singleton
service provider.
"""

import threading
from contextlib import contextmanager
from typing import Any, Generator, Optional

_thread_local = threading.local()


class RequestContext:
    """
    Manages execution-scoped context using thread-local storage.
    Works for web requests, batch jobs, and any other execution scenario.
    Uses thread-local storage to ensure isolation between concurrent
    executions.
    """

    @staticmethod
    def set_service_provider(provider: Any) -> None:
        """Set the singleton service provider for the current execution."""
        _thread_local.service_provider = provider

    @staticmethod
    def get_service_provider() -> Optional[Any]:
        """Get the singleton service provider for the current execution."""
        return getattr(_thread_local, "service_provider", None)

    @staticmethod
    def clear() -> None:
        """Clear the execution context."""
        if hasattr(_thread_local, "service_provider"):
            delattr(_thread_local, "service_provider")

    @staticmethod
    @contextmanager
    def with_service_provider(provider: Any) -> Generator[None, None, None]:
        """
        Context manager for setting up and tearing down service provider.

        Automatically handles the lifecycle of the service provider within
        the execution context, ensuring proper cleanup.

        Args:
            provider: The service provider to use for this execution context

        Yields:
            None - The context is ready for use

        Example:
            # For batch jobs or standalone scripts
            with RequestContext.with_service_provider(service_provider):
                service = get_service(MyService)
                service.do_work()
        """
        RequestContext.set_service_provider(provider)
        try:
            yield
        finally:
            RequestContext.clear()

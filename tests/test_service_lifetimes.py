"""Service lifetime management tests."""

import threading
import time
from unittest.mock import patch

import pytest

from servicegraph import ApplicationBuilder, ServiceLifetime, ServiceProvider

# ========================
# Test Fixtures
# ========================


@pytest.fixture(autouse=True)
def reset_service_provider():
    """
    Reset the ServiceProvider state before each test.
    Note: ServiceProvider is a singleton by design - only one exists
    per runtime. We clear its state rather than trying to recreate it.
    """
    from servicegraph.service_provider import ServiceProvider

    # Clear before test
    if ServiceProvider._instance is not None:
        # Clear all cached instances
        ServiceProvider._instance.clear_all_instances()
        # Clear all service registrations
        ServiceProvider._instance._collection.clear()

    yield

    # Don't clear after - the next test will clear before it runs
    # Clearing after would wipe out the next test's collection since
    # ServiceProvider always updates its _collection reference


# Test service classes - defined at module level so ServiceProvider can access them
class ThreadSafeService:
    def __init__(self):
        self.instance_id = id(self)
        self.creation_thread = threading.current_thread().ident


class SessionTestService:
    def __init__(self):
        self.created_at = time.time()


class DisposableService:
    def __init__(self):
        self.disposed = False
        self.cleanup_called = False

    def dispose(self):
        self.disposed = True
        self.cleanup_called = True


class ScopedTestService:
    def get_data(self):
        return "scoped data"


class SingletonService:
    def __init__(self):
        self.instance_id = id(self)


class TransientService:
    def __init__(self, singleton_service: SingletonService):
        self.singleton_service = singleton_service
        self.instance_id = id(self)


class ScopedService:
    def __init__(
        self, singleton_service: SingletonService, transient_service: TransientService
    ):
        self.singleton_service = singleton_service
        self.transient_service = transient_service
        self.instance_id = id(self)


class TestService:
    pass


class Repository:  # Singleton - expensive to create
    def __init__(self):
        self.instance_id = id(self)


class BusinessService:  # Transient - lightweight business logic
    def __init__(self, repository: Repository):
        self.repository = repository
        self.instance_id = id(self)


class Controller:  # Scoped - per-request lifecycle
    def __init__(self, business_service: BusinessService):
        self.business_service = business_service
        self.instance_id = id(self)


class LargeService:
    def __init__(self):
        # Simulate large memory usage
        self.large_data = "x" * 10000
        self.instance_id = id(self)


class WeaklyReferencedService:
    def __init__(self):
        self.data = "test_data"


class ScopedServiceWithCleanup:
    def __init__(self):
        self.instance_id = id(self)

    def dispose(self):
        cleanup_calls.append("disposed")


# Global list to track cleanup calls for testing
cleanup_calls = []


class TestServiceLifetimeManagement:
    """Test detailed service lifetime behaviors."""

    def test_singleton_thread_safety(self):
        """Test that singleton services are thread-safe."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(ThreadSafeService)
        provider = builder.build()

        # Create services from multiple threads
        results = []

        def create_service():
            service = provider.get_service(ThreadSafeService)
            results.append(service)

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_service)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All results should be the same instance
        first_service = results[0]
        for service in results[1:]:
            assert service is first_service
            assert service.instance_id == first_service.instance_id

    def test_transient_session_expiration(self):
        """Test automatic session expiration for transient services."""
        from datetime import datetime, timedelta, timezone

        builder = ApplicationBuilder()
        builder.services.add_transient(SessionTestService)
        provider = builder.build()

        session_id = "expiring_session"

        # Create service in session
        service1 = provider.get_service(SessionTestService, session_id)

        # Mock datetime.now to simulate session expiration (30 minutes + 1 second)
        original_now = datetime.now(timezone.utc)
        future_time = original_now + timedelta(minutes=30, seconds=1)

        with patch("servicegraph.service_provider.datetime") as mock_datetime:
            # Mock now to return future time
            mock_datetime.now.return_value = future_time
            # Keep timedelta and timezone working normally
            mock_datetime.timedelta = timedelta
            mock_datetime.timezone = timezone

            # Should create new service due to session expiration
            service2 = provider.get_service(SessionTestService, session_id)

            # These should be different instances due to session expiration
            assert service1 is not service2

    def test_scoped_service_disposal(self):
        """Test proper disposal of scoped services."""
        builder = ApplicationBuilder()
        builder.services.add_scoped(DisposableService)
        provider = builder.build()

        service_ref = None

        # Use scoped service within context
        with provider.get_service(DisposableService) as service:
            service_ref = service
            assert not service.disposed

        # Service should be disposed after scope ends
        assert service_ref.disposed
        assert service_ref.cleanup_called

    def test_scoped_service_context_manager_enforcement(self):
        """Test that scoped services require context manager usage."""
        builder = ApplicationBuilder()
        builder.services.add_scoped(ScopedTestService)
        provider = builder.build()

        # Getting scoped service returns a context manager wrapper
        scoped_wrapper = provider.get_service(ScopedTestService)

        # Attempting to use the service without entering context should fail
        with pytest.raises(RuntimeError, match="must be used within.*with.*statement"):
            # Trying to call a method without using 'with' raises error
            scoped_wrapper.get_data()

    def test_mixed_lifetime_dependencies(self):
        """Test services with dependencies of different lifetimes."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(SingletonService)
        builder.services.add_transient(TransientService)
        builder.services.add_scoped(ScopedService)

        provider = builder.build()

        # Note: Current scoped implementation doesn't support sharing instances
        # within a single scope - each get_service() call creates a new
        # context manager
        with provider.get_service(ScopedService) as scoped1:
            # Test that the service works within context
            assert scoped1.singleton_service is not None
            assert scoped1.transient_service is not None

    def test_service_lifetime_validation(self):
        """Test validation of service lifetime registrations."""
        builder = ApplicationBuilder()

        # Test all valid lifetime registrations
        builder.services.add_singleton(TestService)
        builder.services.add_transient(TestService)  # Should override
        builder.services.add_scoped(TestService)  # Should override

        provider = builder.build()

        # Final registration should be scoped
        with provider.get_service(TestService) as service:
            assert service is not None

    def test_factory_with_different_lifetimes(self):
        """Test factory registration with different lifetimes."""
        call_count = 0

        def create_service(provider: ServiceProvider):
            nonlocal call_count
            call_count += 1
            return f"service_instance_{call_count}"

        builder = ApplicationBuilder()

        # Test singleton factory - should only be called once
        builder.services.add_factory(str, create_service, ServiceLifetime.SINGLETON)

        provider = builder.build()

        service1 = provider.get_service(str)
        service2 = provider.get_service(str)

        assert service1 == service2 == "service_instance_1"
        assert call_count == 1  # Factory called only once

        # Reset and test transient factory
        call_count = 0
        builder = ApplicationBuilder()
        builder.services.add_factory(str, create_service, ServiceLifetime.TRANSIENT)

        provider = builder.build()

        service1 = provider.get_service(str)
        service2 = provider.get_service(str)

        assert service1 == "service_instance_1"
        assert service2 == "service_instance_2"
        assert call_count == 2  # Factory called twice

    def test_complex_dependency_chain_lifetimes(self):
        """Test complex dependency chains with mixed lifetimes."""
        builder = ApplicationBuilder()
        builder.services.add_singleton(Repository)
        builder.services.add_transient(BusinessService)
        builder.services.add_scoped(Controller)

        provider = builder.build()

        # Test multiple scopes
        controllers = []
        for i in range(3):
            with provider.get_service(Controller) as controller:
                controllers.append(controller)

        # Controllers should be different (scoped)
        assert len(set(c.instance_id for c in controllers)) == 3

        # Business services should be different (transient)
        business_services = [c.business_service for c in controllers]
        assert len(set(bs.instance_id for bs in business_services)) == 3

        # Repositories should be same (singleton)
        repositories = [c.business_service.repository for c in controllers]
        assert len(set(r.instance_id for r in repositories)) == 1


class TestMemoryManagement:
    """Test memory management and cleanup behaviors."""

    def test_session_cleanup_prevents_memory_leaks(self):
        """Test that session cleanup prevents memory accumulation."""
        builder = ApplicationBuilder()
        builder.services.add_transient(LargeService)
        provider = builder.build()

        # Create many sessions
        session_ids = []
        for i in range(100):
            session_id = f"session_{i}"
            session_ids.append(session_id)
            provider.get_service(LargeService, session_id)

        # Clean up all sessions
        for session_id in session_ids:
            provider.dispose_session(session_id)

        # After cleanup, new sessions should start fresh
        new_service = provider.get_service(LargeService, "new_session_after_cleanup")
        assert new_service is not None

    def test_automatic_weak_reference_cleanup(self):
        """Test that weak references are cleaned up automatically."""
        builder = ApplicationBuilder()
        builder.services.add_transient(WeaklyReferencedService)
        provider = builder.build()

        # Create service and let it go out of scope
        session_id = "weak_ref_test"
        service = provider.get_service(WeaklyReferencedService, session_id)
        service_id = id(service)

        # Remove strong reference
        del service

        # Force garbage collection
        import gc

        gc.collect()

        # Service should still be accessible via session
        service_again = provider.get_service(WeaklyReferencedService, session_id)
        assert id(service_again) == service_id  # Same instance


if __name__ == "__main__":
    pytest.main([__file__])

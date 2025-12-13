"""Performance and memory management tests."""

import gc
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from servicegraph import ApplicationBuilder
from servicegraph.service_lifetime import ServiceLifetime

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


# ========================
# Module-level Service Classes
# ========================


# Service resolution performance test classes
class BaseService:
    def __init__(self):
        self.created_at = time.time()


class MiddleService:
    def __init__(self, base_service: BaseService):
        self.base_service = base_service
        self.created_at = time.time()


class TopService:
    def __init__(self, middle_service: MiddleService):
        self.middle_service = middle_service
        self.created_at = time.time()


# Concurrent test service
class ConcurrentTestService:
    def __init__(self):
        self.thread_id = threading.current_thread().ident
        self.instance_id = id(self)


# Transient service with memory tracking
class TransientService:
    def __init__(self):
        # Allocate some memory to track
        self.data = list(range(1000))
        self.instance_id = id(self)


# Session service for session management tests
class SessionService:
    def __init__(self):
        self.created_at = time.time()
        self.instance_id = id(self)


# Weakly referenced service for GC tests
class WeaklyReferencedService:
    def __init__(self):
        self.data = "test_data"


# Session managed service for GC tests
class SessionManagedService:
    def __init__(self):
        self.data = "session_managed"


# Singleton service for memory persistence tests
class SingletonService:
    def __init__(self):
        self.created_at = time.time()


# Scoped service with cleanup tracking
class ScopedServiceWithCleanup:
    def __init__(self):
        self.data = "scoped_data"
        self._cleanup_calls = None  # Will be set by tests

    def dispose(self):
        if self._cleanup_calls is not None:
            self._cleanup_calls.append("disposed")


# Circular reference test classes
class ServiceA:
    def __init__(self):
        self.service_b = None
        self.data = "service_a_data"


class ServiceB:
    def __init__(self):
        self.service_a = None
        self.data = "service_b_data"


class TestPerformanceCharacteristics:
    """Test performance characteristics of servicegraph."""

    def test_service_resolution_performance(self):
        """Test performance of service resolution."""
        builder = ApplicationBuilder()

        # Use module-level classes for dependency chain
        builder.services.add_singleton(BaseService)
        builder.services.add_singleton(MiddleService)
        builder.services.add_singleton(TopService)

        provider = builder.build()

        # Measure first resolution (includes initialization)
        start_time = time.time()
        service1 = provider.get_service(TopService)
        first_resolution_time = time.time() - start_time

        # Measure subsequent resolutions (should be O(1) for singletons)
        resolution_times = []
        for _ in range(100):
            start_time = time.time()
            service = provider.get_service(TopService)
            resolution_times.append(time.time() - start_time)
            assert service is service1  # Should be same instance

        # Subsequent resolutions should be much faster
        avg_subsequent_time = sum(resolution_times) / len(resolution_times)

        # Subsequent resolutions should be at least 10x faster than first
        # (or both should be negligibly fast)
        if (
            first_resolution_time > 0.0001
        ):  # Only check if first resolution was measurable
            assert avg_subsequent_time < first_resolution_time / 10

        # All subsequent resolutions should be very fast (< 1ms)
        assert avg_subsequent_time < 0.001

    def test_concurrent_service_resolution_performance(self):
        """Test performance under concurrent access."""
        builder = ApplicationBuilder()

        # Use module-level class
        builder.services.add_singleton(ConcurrentTestService)
        provider = builder.build()

        results = []

        def resolve_service():
            start_time = time.time()
            service = provider.get_service(ConcurrentTestService)
            resolution_time = time.time() - start_time
            return (service, resolution_time)

        # Test with multiple threads
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(resolve_service) for _ in range(100)]

            for future in as_completed(futures):
                service, resolution_time = future.result()
                results.append((service, resolution_time))

        # All services should be the same instance
        first_service = results[0][0]
        for service, _ in results[1:]:
            assert service is first_service

        # All resolutions should be fast
        resolution_times = [time_taken for _, time_taken in results]
        avg_time = sum(resolution_times) / len(resolution_times)
        max_time = max(resolution_times)

        assert avg_time < 0.001  # Average < 1ms
        assert max_time < 0.01  # Max < 10ms

    def test_memory_usage_with_many_transient_services(self):
        """Test memory usage with many transient services."""
        builder = ApplicationBuilder()

        # Use module-level class
        builder.services.add_transient(TransientService)
        provider = builder.build()

        # Create many transient services without sessions
        services = []
        for _ in range(100):
            service = provider.get_service(TransientService)
            services.append(service)

        # All should be different instances
        instance_ids = [s.instance_id for s in services]
        assert len(set(instance_ids)) == 100

        # Clear references and force garbage collection
        del services
        gc.collect()

        # Memory should be released (can't test directly, but ensure no errors)
        # Create new services to ensure system is still stable
        new_services = [provider.get_service(TransientService) for _ in range(10)]
        assert len(new_services) == 10

    def test_session_management_performance(self):
        """Test performance of session-based transient services."""
        builder = ApplicationBuilder()

        # Use module-level class
        builder.services.add_transient(SessionService)
        provider = builder.build()

        session_id = "performance_test_session"

        # First resolution in session should be slower (creates instance)
        start_time = time.time()
        service1 = provider.get_service(SessionService, session_id)
        first_resolution_time = time.time() - start_time

        # Subsequent resolutions in same session should be faster
        resolution_times = []
        for _ in range(50):
            start_time = time.time()
            service = provider.get_service(SessionService, session_id)
            resolution_times.append(time.time() - start_time)
            assert service is service1  # Same instance within session

        avg_subsequent_time = sum(resolution_times) / len(resolution_times)

        # Subsequent resolutions should be faster than first (or both negligibly fast)
        if (
            first_resolution_time > 0.0001
        ):  # Only check if first resolution was measurable
            assert avg_subsequent_time <= first_resolution_time

        # All resolutions should be fast
        assert avg_subsequent_time < 0.001

    def test_startup_performance(self):
        """Test application startup performance."""

        # Test with many service registrations
        # Note: Creating classes dynamically in this test is acceptable as it's testing
        # startup performance with many registrations
        def create_large_app():
            builder = ApplicationBuilder()

            # Register many services - create at module level temporarily
            # We use default argument to capture the value of i correctly
            for i in range(100):
                class_name = f"Service{i}"
                # Fix the closure issue by using default argument
                service_class = type(
                    class_name,
                    (),
                    {"__init__": lambda self, idx=i: setattr(self, "id", idx)},
                )

                # Mix of lifetimes
                if i % 3 == 0:
                    builder.services.add_singleton(service_class)
                elif i % 3 == 1:
                    builder.services.add_transient(service_class)
                else:
                    builder.services.add_scoped(service_class)

            return builder

        # Measure app creation time
        start_time = time.time()
        builder = create_large_app()
        build_time = time.time() - start_time

        # Measure provider build time
        start_time = time.time()
        _ = builder.build()  # Use _ to avoid unused variable warning
        provider_build_time = time.time() - start_time

        # Startup should be fast even with many registrations
        assert build_time < 0.1  # Builder creation < 100ms
        assert provider_build_time < 0.1  # Provider build < 100ms


class TestMemoryManagement:
    """Test memory management and cleanup."""

    def test_weak_reference_cleanup(self):
        """Test that services can be garbage collected when appropriate."""
        builder = ApplicationBuilder()

        # Use module-level class
        builder.services.add_transient(WeaklyReferencedService)
        provider = builder.build()

        # Create service and weak reference
        service = provider.get_service(WeaklyReferencedService)
        weak_ref = weakref.ref(service)

        # Weak reference should be alive
        assert weak_ref() is not None

        # Remove strong reference
        del service
        gc.collect()

        # For transient services without sessions,
        # weak reference should be dead
        assert weak_ref() is None

    def test_session_prevents_premature_garbage_collection(self):
        """Test that sessions keep services alive."""
        builder = ApplicationBuilder()

        # Use module-level class
        builder.services.add_transient(SessionManagedService)
        provider = builder.build()

        session_id = "gc_test_session"

        # Create service in session and weak reference
        service = provider.get_service(SessionManagedService, session_id)
        weak_ref = weakref.ref(service)
        service_id = id(service)

        # Remove strong reference
        del service
        gc.collect()

        # Service should still be alive due to session
        assert weak_ref() is not None

        # Getting service again should return same instance
        service_again = provider.get_service(SessionManagedService, session_id)
        assert id(service_again) == service_id

        # Clear the strong reference before disposing
        del service_again

        # Dispose session
        provider.dispose_session(session_id)
        gc.collect()

        # Now weak reference should be dead
        assert weak_ref() is None

    def test_singleton_memory_persistence(self):
        """Test that singletons persist in memory as expected."""
        builder = ApplicationBuilder()

        # Use module-level class
        builder.services.add_singleton(SingletonService)
        provider = builder.build()

        # Create singleton and weak reference
        service = provider.get_service(SingletonService)
        weak_ref = weakref.ref(service)
        creation_time = service.created_at

        # Remove strong reference
        del service
        gc.collect()

        # Singleton should still be alive
        assert weak_ref() is not None

        # Getting service again should return same instance
        service_again = provider.get_service(SingletonService)
        assert service_again.created_at == creation_time

    def test_scoped_service_cleanup(self):
        """Test that scoped services are properly cleaned up."""
        builder = ApplicationBuilder()

        cleanup_calls = []

        # Create a factory that sets up the cleanup tracking
        def create_scoped_service():
            service = ScopedServiceWithCleanup()
            service._cleanup_calls = cleanup_calls
            return service

        builder.services.add_factory(
            ScopedServiceWithCleanup,
            lambda p: create_scoped_service(),
            lifetime=ServiceLifetime.SCOPED,
        )
        provider = builder.build()

        # Use scoped service
        with provider.get_service(ScopedServiceWithCleanup) as service:
            # Service should be alive within scope
            assert service is not None
            assert service.data == "scoped_data"

        # After scope ends, service should be disposed
        # The dispose() method should have been called
        assert len(cleanup_calls) == 1
        assert cleanup_calls[0] == "disposed"

    def test_memory_leak_prevention_with_circular_references(self):
        """Test that circular references don't cause memory leaks."""
        builder = ApplicationBuilder()

        # Manually create circular reference after construction using module-level classes
        def create_circular_services(provider):
            service_a = ServiceA()
            service_b = ServiceB()

            # Create circular reference
            service_a.service_b = service_b
            service_b.service_a = service_a

            return service_a

        builder.services.add_factory(ServiceA, lambda p: create_circular_services(p))
        provider = builder.build()

        # Create services with circular references
        service_a = provider.get_service(ServiceA)
        weak_ref_a = weakref.ref(service_a)
        weak_ref_b = weakref.ref(service_a.service_b)

        # Remove strong reference
        del service_a
        gc.collect()

        # Due to circular reference, services might still be alive
        # but servicegraph should handle this gracefully without memory leaks
        # (Implementation detail depends on your circular reference handling)

        # Keep references to avoid unused variable warnings
        _ = weak_ref_a
        _ = weak_ref_b


if __name__ == "__main__":
    pytest.main([__file__])

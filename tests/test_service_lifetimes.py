"""Service lifetime management tests."""

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from servicegraph import ApplicationBuilder, ServiceLifetime, ServiceProvider

# ========================
# Test Fixtures
# ========================


@pytest.fixture(autouse=True)
def reset_service_provider():
    """Reset the ServiceProvider state before each test for isolation."""
    from servicegraph.service_provider import ServiceProvider

    ServiceProvider._reset_for_testing()
    yield


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
        ServiceProvider._reset_for_testing()
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


class TestDisposeSessionConcurrency:
    """
    Tests that dispose_session and its internal callers do not hold _instance_lock
    while executing user-defined close()/dispose() methods.

    The original bug:
      _get_or_create_session_service held _instance_lock, then called
      _cleanup_expired_sessions → dispose_session → _dispose_service → user close().
      Any concurrent thread that tried to acquire _instance_lock blocked for the full
      duration of close().  If close() in turn waited on that second thread, the
      result was a classic deadlock.

      clear_all_sessions() acquired _instance_lock and then called dispose_session,
      which re-acquired it (fine with RLock but still held the lock during close()).

    Fix: _dispose_service is called *outside* the lock in all paths.

    Lock-probing design
    -------------------
    Python's RLock allows the *owning thread* to non-blockingly re-acquire itself,
    so the probe must run from a *different* thread.  Each test does:

      1. Service.close() signals a dedicated probe thread via an Event and then
         waits for that thread to finish before returning.
      2. The probe thread calls _instance_lock.acquire(blocking=False) and records
         whether the call succeeded.
         * False → lock was held by another thread (the dispose/cleanup frame) → BUG
         * True  → lock was free → correct; probe releases it immediately
      3. After dispose returns, the test asserts the recorded value is False (free).
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_probing_service(provider_ref, lock_held_results):
        """
        Return a class whose close() synchronises with a probe thread to test
        whether _instance_lock is held at the time close() is called.
        """
        start_probe = threading.Event()
        probe_done = threading.Event()

        class _ProbingService:
            # Keep events as class attributes so the spawned thread can see them.
            _start_probe = start_probe
            _probe_done = probe_done

            def close(self):
                # Wake the probe thread, then wait for it to record the result.
                self._start_probe.set()
                self._probe_done.wait(timeout=2.0)

        def probe():
            start_probe.wait(timeout=2.0)
            p = provider_ref[0]
            acquired = p._instance_lock.acquire(blocking=False)
            if acquired:
                p._instance_lock.release()
            # True  → acquire succeeded → lock was FREE at close() time (good)
            # False → acquire failed   → lock was HELD at close() time (bad)
            lock_held_results.append(not acquired)
            probe_done.set()

        return _ProbingService, threading.Thread(target=probe, daemon=True)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_dispose_session_does_not_hold_lock_during_close(self):
        """dispose_session must NOT hold _instance_lock while calling service.close()."""
        lock_held: list = []
        provider_ref: list = []

        ProbingService, probe_thread = self._make_probing_service(
            provider_ref, lock_held
        )
        probe_thread.start()

        builder = ApplicationBuilder()
        builder.services.add_transient(ProbingService)
        provider = builder.build()
        provider_ref.append(provider)

        provider.get_service(ProbingService, "probe_session")
        provider.dispose_session("probe_session")
        probe_thread.join(timeout=5.0)

        assert (
            not probe_thread.is_alive()
        ), "Probe thread timed out — possible deadlock."
        assert lock_held == [False], (
            "dispose_session held _instance_lock while calling service.close(). "
            "Any concurrent session-aware call will block for the full duration of "
            "the user's close() method — a potential deadlock."
        )

    def test_cleanup_expired_sessions_does_not_hold_lock_during_close(self):
        """
        _get_or_create_session_service → _cleanup_expired_sessions → dispose_session
        must NOT hold _instance_lock during service.close().

        We back-date a session timestamp to force it to appear expired, then trigger
        a new get_service call so _cleanup_expired_sessions fires while the
        _get_or_create_session_service frame already holds _instance_lock.
        """
        lock_held: list = []
        provider_ref: list = []

        ProbingService, probe_thread = self._make_probing_service(
            provider_ref, lock_held
        )
        probe_thread.start()

        class TriggerService:
            pass

        builder = ApplicationBuilder()
        builder.services.add_transient(ProbingService)
        builder.services.add_transient(TriggerService)
        provider = builder.build()
        provider_ref.append(provider)

        provider.get_service(ProbingService, "expiry_session")

        # Back-date so _cleanup_expired_sessions picks this session up.
        with provider._instance_lock:
            provider._session_timestamps["expiry_session"] = (
                datetime.now(timezone.utc)
                - provider._session_timeout
                - timedelta(seconds=1)
            )

        # A new get_service call triggers _cleanup_expired_sessions internally.
        provider.get_service(TriggerService, "trigger_session")
        probe_thread.join(timeout=5.0)

        assert (
            not probe_thread.is_alive()
        ), "Probe thread timed out — possible deadlock."
        assert lock_held == [False], (
            "_cleanup_expired_sessions held _instance_lock while calling service.close(). "
            "Any concurrent session-aware call will stall for the full duration of "
            "the user's cleanup code."
        )

    def test_clear_all_sessions_does_not_hold_lock_during_close(self):
        """clear_all_sessions must NOT hold _instance_lock while calling service.close()."""
        lock_held: list = []
        provider_ref: list = []

        # We need 3 independent probe threads (one per session).
        start_probes = [threading.Event() for _ in range(3)]
        probe_dones = [threading.Event() for _ in range(3)]
        call_index = [0]  # which close() invocation is this?

        class MultiSessionProbingService:
            def close(self):
                idx = call_index[0]
                call_index[0] += 1
                start_probes[idx].set()
                probe_dones[idx].wait(timeout=2.0)

        def make_probe(idx):
            def probe():
                start_probes[idx].wait(timeout=2.0)
                p = provider_ref[0]
                acquired = p._instance_lock.acquire(blocking=False)
                if acquired:
                    p._instance_lock.release()
                lock_held.append(not acquired)
                probe_dones[idx].set()

            return threading.Thread(target=probe, daemon=True)

        probe_threads = [make_probe(i) for i in range(3)]
        for pt in probe_threads:
            pt.start()

        builder = ApplicationBuilder()
        builder.services.add_transient(MultiSessionProbingService)
        provider = builder.build()
        provider_ref.append(provider)

        for i in range(3):
            provider.get_service(MultiSessionProbingService, f"sess_{i}")

        provider.clear_all_sessions()
        for pt in probe_threads:
            pt.join(timeout=5.0)

        assert all(
            not pt.is_alive() for pt in probe_threads
        ), "At least one probe thread timed out — possible deadlock."
        assert provider.get_active_session_count() == 0
        assert len(lock_held) == 3
        assert all(not held for held in lock_held), (
            f"clear_all_sessions held _instance_lock during "
            f"{sum(lock_held)} close() call(s)."
        )

    def test_concurrent_dispose_and_get_service_complete_without_deadlock(self):
        """
        Multiple threads disposing sessions while others resolve session-scoped
        services must all complete within the timeout — no deadlock, no starvation.
        """
        NUM_SESSIONS = 20
        errors: list = []

        class SessionService:
            pass

        builder = ApplicationBuilder()
        builder.services.add_transient(SessionService)
        provider = builder.build()

        for i in range(NUM_SESSIONS):
            provider.get_service(SessionService, f"concurrent_{i}")

        dispose_done = threading.Event()

        def dispose_all():
            try:
                for i in range(NUM_SESSIONS):
                    provider.dispose_session(f"concurrent_{i}")
            except Exception as e:
                errors.append(e)
            finally:
                dispose_done.set()

        def resolve_continuously():
            deadline = time.time() + 0.5
            while time.time() < deadline and not dispose_done.is_set():
                try:
                    provider.get_service(SessionService, "live_session")
                except Exception as e:
                    errors.append(e)
                    break

        threads = [threading.Thread(target=dispose_all, daemon=True)]
        threads += [
            threading.Thread(target=resolve_continuously, daemon=True) for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert all(
            not t.is_alive() for t in threads
        ), "One or more threads are still alive — likely a deadlock."
        assert not errors, f"Thread errors: {errors}"


if __name__ == "__main__":
    pytest.main([__file__])

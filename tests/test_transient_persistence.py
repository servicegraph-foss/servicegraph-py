"""Test to verify transient instances persist after scoped service disposal."""

import pytest

from servicegraph import ApplicationBuilder


class TransientService:
    """Test service to track instance creation."""

    instance_count = 0

    def __init__(self):
        TransientService.instance_count += 1
        self.instance_id = TransientService.instance_count

    def get_id(self):
        return self.instance_id

    @classmethod
    def reset_count(cls):
        """Reset instance counter between tests."""
        cls.instance_count = 0


class ScopedService:
    """Scoped service that depends on a transient service."""

    def __init__(self, transient: TransientService):
        self.transient = transient

    def get_transient_id(self):
        return self.transient.get_id()


@pytest.fixture
def provider():
    """Create a service provider with transient and scoped services."""
    TransientService.reset_count()

    builder = ApplicationBuilder()
    builder.services.add_transient(TransientService)
    builder.services.add_scoped(ScopedService)

    return builder.build()


def test_transient_persists_across_scoped_lifecycles(provider):
    """
    Test that a transient service instance persists in its session
    even after the scoped service that first created it is disposed.
    """
    session_id = "test_session_123"

    # First scoped service creates and uses transient
    with provider.get_service(ScopedService, session_id=session_id) as scoped1:
        transient_id_1 = scoped1.get_transient_id()

    # Verify session still exists after first scoped service is disposed
    session_info = provider.get_session_info(session_id)
    assert session_info is not None
    assert session_info["session_id"] == session_id
    assert "TransientService" in session_info["services"]

    # Second scoped service should reuse the same transient instance
    with provider.get_service(ScopedService, session_id=session_id) as scoped2:
        transient_id_2 = scoped2.get_transient_id()

    # Verify same transient instance was used
    assert (
        transient_id_1 == transient_id_2
    ), "Transient instance should persist across scoped service lifecycles"
    assert (
        TransientService.instance_count == 1
    ), "Only one transient instance should have been created"

    # Cleanup
    provider.dispose_session(session_id)
    assert provider.get_session_info(session_id) is None


def test_different_sessions_get_different_transients(provider):
    """
    Test that different sessions get different transient instances,
    even when using the same scoped service type.
    """
    session_1 = "session_1"
    session_2 = "session_2"

    # Create scoped service in first session
    with provider.get_service(ScopedService, session_id=session_1) as scoped1:
        transient_id_1 = scoped1.get_transient_id()

    # Create scoped service in second session
    with provider.get_service(ScopedService, session_id=session_2) as scoped2:
        transient_id_2 = scoped2.get_transient_id()

    # Different sessions should have different transient instances
    assert (
        transient_id_1 != transient_id_2
    ), "Different sessions should get different transient instances"
    assert (
        TransientService.instance_count == 2
    ), "Two transient instances should have been created for two sessions"

    # Cleanup
    provider.dispose_session(session_1)
    provider.dispose_session(session_2)


def test_transient_cleanup_on_session_disposal(provider):
    """
    Test that transient instances are properly cleaned up when
    the session is explicitly disposed.
    """
    session_id = "cleanup_test_session"

    # Create scoped service with transient dependency
    with provider.get_service(ScopedService, session_id=session_id) as scoped:
        transient_id = scoped.get_transient_id()
        assert transient_id == 1

    # Session should still exist
    assert provider.get_session_info(session_id) is not None

    # Dispose session
    provider.dispose_session(session_id)

    # Session should be gone
    assert provider.get_session_info(session_id) is None

    # Creating a new scoped service with the same session_id should create new transient
    with provider.get_service(ScopedService, session_id=session_id) as scoped:
        new_transient_id = scoped.get_transient_id()
        assert new_transient_id == 2, "New session should get a new transient instance"

    # Cleanup
    provider.dispose_session(session_id)


def test_no_session_id_creates_new_transients(provider):
    """
    Test that not providing a session_id creates new transient instances
    for each scoped service resolution.
    """
    # First scoped service without session_id
    with provider.get_service(ScopedService) as scoped1:
        transient_id_1 = scoped1.get_transient_id()

    # Second scoped service without session_id
    with provider.get_service(ScopedService) as scoped2:
        transient_id_2 = scoped2.get_transient_id()

    # Without session_id, each should get a new transient
    assert (
        transient_id_1 != transient_id_2
    ), "Without session_id, each scoped service should get a new transient"
    assert (
        TransientService.instance_count == 2
    ), "Two separate transient instances should have been created"

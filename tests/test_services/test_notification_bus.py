"""Tests for the in-process notification fan-out bus."""

import asyncio

import pytest

from src.services.notification_bus import clear_subscribers, publish, subscribe, unsubscribe


@pytest.fixture(autouse=True)
def _clean_bus():
    """Keep module-level subscriber state isolated between tests."""
    clear_subscribers()
    yield
    clear_subscribers()


def test_publish_wakes_only_target_subscribers() -> None:
    """A publish reaches the target user's queue and nobody else's."""
    lead_queue = subscribe(99)
    other_queue = subscribe(7)
    try:
        assert publish([99]) == 1
        assert lead_queue.get_nowait() is None
        with pytest.raises(asyncio.QueueEmpty):
            other_queue.get_nowait()
    finally:
        unsubscribe(99, lead_queue)
        unsubscribe(7, other_queue)


def test_publish_coalesces_bursts_into_one_wake_up() -> None:
    """Burst publishes collapse to a single pending snapshot request."""
    queue = subscribe(5)
    try:
        publish([5, 5])
        publish([5])
        assert queue.get_nowait() is None
        with pytest.raises(asyncio.QueueEmpty):
            queue.get_nowait()
    finally:
        unsubscribe(5, queue)


def test_unsubscribe_removes_listener() -> None:
    """A removed queue no longer receives wake-ups."""
    queue = subscribe(3)
    unsubscribe(3, queue)
    assert publish([3]) == 0

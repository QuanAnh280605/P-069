"""In-process fan-out bus waking open notification streams.

Single-process design: the API runs under one uvicorn worker, so an
in-memory registry is sufficient and no external broker is required.
"""

import asyncio

WakeQueue = asyncio.Queue[None]

_subscribers: dict[int, set[WakeQueue]] = {}


def subscribe(user_id: int) -> WakeQueue:
    """Register one wake-up queue for a user and return it."""
    queue: WakeQueue = asyncio.Queue(maxsize=1)
    _subscribers.setdefault(user_id, set()).add(queue)
    return queue


def unsubscribe(user_id: int, queue: WakeQueue) -> None:
    """Remove one queue; drop the user entry when no listener remains."""
    queues = _subscribers.get(user_id)
    if queues is None:
        return
    queues.discard(queue)
    if not queues:
        _subscribers.pop(user_id, None)


def publish(user_ids) -> int:
    """Wake every listener of the given users; return woken queue count."""
    woken = 0
    for user_id in set(user_ids):
        for queue in tuple(_subscribers.get(user_id, ())):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass  # a snapshot request is already pending
            woken += 1
    return woken


def clear_subscribers() -> None:
    """Drop all listeners — test isolation helper."""
    _subscribers.clear()

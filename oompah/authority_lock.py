"""Bounded acquisition helpers for cross-loop task authority locks."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any


async def acquire_bounded_task_lock(
    lock: Any,
    *,
    timeout_seconds: float,
) -> bool | None:
    """Acquire an async or legacy synchronous lock without an unbounded wait.

    ``True`` means the caller owns the lock and must release it. ``False``
    means a supported lock remained busy through the deadline. ``None`` means
    the legacy adapter has no safe non-blocking acquisition surface, so callers
    preserve the historical self-serialization fallback without touching it.

    Synchronous locks are polled only through ``blocking=False``.  In
    particular, this helper never falls back to a bare synchronous
    ``acquire()`` call on the event-loop thread.
    """

    timeout = float(timeout_seconds)
    if timeout <= 0:
        raise ValueError("timeout_seconds must be positive")
    acquire = getattr(lock, "acquire", None)
    if not callable(acquire):
        return None

    if inspect.iscoroutinefunction(acquire):
        try:
            acquisition = acquire(timeout_seconds=timeout)
        except TypeError:
            acquisition = acquire()
        if not inspect.isawaitable(acquisition):
            return None
        try:
            return bool(await asyncio.wait_for(acquisition, timeout=timeout))
        except TimeoutError:
            return False

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        try:
            acquisition = acquire(blocking=False)
        except TypeError:
            try:
                acquisition = acquire(False)
            except TypeError:
                return None
        if inspect.isawaitable(acquisition):
            remaining = deadline - loop.time()
            if remaining <= 0:
                close = getattr(acquisition, "close", None)
                if callable(close):
                    close()
                return False
            try:
                return bool(
                    await asyncio.wait_for(acquisition, timeout=remaining)
                )
            except TimeoutError:
                return False
        if bool(acquisition):
            return True
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(0.01, remaining))

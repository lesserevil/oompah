"""Thread-safe intake and coalescing for workflow scheduler events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WorkflowEventHost(Protocol):
    """Minimal scheduler state used by the event-intake owner."""

    _dispatch_loop: asyncio.AbstractEventLoop | None
    _dispatch_queue: asyncio.Queue[Any]
    _refresh_requested: asyncio.Event
    _stopping: bool
    config: Any

    def _dispatch_event_key(self, event: Any) -> str: ...
    def _running_loop(self) -> asyncio.AbstractEventLoop | None: ...
    def _post_event_on_loop(self, event: Any) -> None: ...
    def _post_event(self, event: Any) -> None: ...


class WorkflowEventIntake:
    """Own event identity, cross-thread admission, and queue coalescing."""

    @staticmethod
    def event_key(event: Any) -> str:
        return str(event.event_type)

    @staticmethod
    def running_loop() -> asyncio.AbstractEventLoop | None:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    @staticmethod
    def set_refresh_requested(host: WorkflowEventHost) -> None:
        loop = host._dispatch_loop
        if loop is not None and loop.is_running() and host._running_loop() is not loop:
            loop.call_soon_threadsafe(host._refresh_requested.set)
            return
        host._refresh_requested.set()

    def mark_dequeued(self, host: WorkflowEventHost, event: Any) -> int:
        key = host._dispatch_event_key(event)
        lock = getattr(host, "_dispatch_event_lock", None)
        pending = getattr(host, "_dispatch_pending_event_keys", None)
        counts = getattr(host, "_dispatch_pending_coalesced_counts", None)
        if lock is None or pending is None or counts is None:
            return 0
        with lock:
            pending.discard(key)
            return counts.pop(key, 0)

    def post_on_loop(self, host: WorkflowEventHost, event: Any) -> None:
        """Put one event on its owning loop, coalescing duplicate signals."""

        key = host._dispatch_event_key(event)
        lock = getattr(host, "_dispatch_event_lock", None)
        pending = getattr(host, "_dispatch_pending_event_keys", None)
        if lock is not None and pending is not None:
            with lock:
                if key in pending:
                    host._dispatch_events_coalesced = (
                        getattr(host, "_dispatch_events_coalesced", 0) + 1
                    )
                    counts = getattr(
                        host, "_dispatch_pending_coalesced_counts", None
                    )
                    if counts is not None:
                        counts[key] = counts.get(key, 0) + 1
                    logger.debug("Coalesced pending dispatch event %s", key)
                    return
                pending.add(key)
        try:
            host._dispatch_queue.put_nowait(event)
        except asyncio.QueueFull:
            if lock is not None and pending is not None:
                with lock:
                    pending.discard(key)
            logger.warning(
                "Dispatch queue unexpectedly full; dropping event %s",
                event.event_type,
            )

    @staticmethod
    def post(host: WorkflowEventHost, event: Any) -> None:
        """Admit an event from either the scheduler loop or another thread."""

        loop = host._dispatch_loop
        if loop is not None and loop.is_running() and host._running_loop() is not loop:
            loop.call_soon_threadsafe(host._post_event_on_loop, event)
            return
        host._post_event_on_loop(event)

    @staticmethod
    async def full_sync_loop(
        host: WorkflowEventHost,
        event_factory: Callable[[], Any],
    ) -> None:
        """Post bounded full-sync events as the event stream's safety net."""

        while not host._stopping:
            interval_s = host.config.full_sync_interval_ms / 1000.0
            await asyncio.sleep(interval_s)
            if not host._stopping:
                host._post_event(event_factory())


WORKFLOW_EVENT_INTAKE = WorkflowEventIntake()

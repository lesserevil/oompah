"""Event-driven infrastructure for oompah.

Provides a typed EventBus for in-process pub/sub without external dependencies.
Handlers may be sync or async; errors in one handler are isolated and logged so
they cannot prevent other handlers from running.

Usage::

    from oompah.events import EventBus, EventType

    bus = EventBus()

    # Subscribe
    def on_dispatch(payload):
        print("dispatched:", payload["identifier"])

    bus.subscribe(EventType.AGENT_DISPATCHED, on_dispatch)

    # Emit (all matching handlers called synchronously)
    bus.emit(EventType.AGENT_DISPATCHED, {"identifier": "abc-1"})

    # Unsubscribe
    bus.unsubscribe(EventType.AGENT_DISPATCHED, on_dispatch)

    # Emit async (awaits async handlers, calls sync ones directly)
    await bus.emit_async(EventType.AGENT_DISPATCHED, {"identifier": "abc-1"})
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)

LIFECYCLE_PUBLICATION_PERMIT_KEY = "_oompah_lifecycle_publication_permit"


class EventType(str, Enum):
    """Canonical event types for the oompah event bus.

    Using ``str`` as the base allows event types to be used directly as
    dictionary keys and compared against plain strings in tests/logging.
    """

    # Agent lifecycle
    AGENT_DISPATCHED = "agent_dispatched"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_STALLED = "agent_stalled"
    AGENT_MAX_TURNS = "agent_max_turns"
    AGENT_TERMINATED = "agent_terminated"

    # Orchestrator lifecycle
    ORCHESTRATOR_PAUSED = "orchestrator_paused"
    ORCHESTRATOR_RESUMED = "orchestrator_resumed"
    ORCHESTRATOR_TICK = "orchestrator_tick"

    # Issue state
    ISSUE_STATE_CHANGED = "issue_state_changed"
    ISSUE_RETRY_SCHEDULED = "issue_retry_scheduled"

    # Activity (high-frequency, per agent turn)
    AGENT_ACTIVITY = "agent_activity"

    # State-only (lightweight broadcast without issue refresh)
    STATE_UPDATED = "state_updated"

    # Forge webhook
    FORGE_WEBHOOK_RECEIVED = "forge_webhook_received"

    # Release addendum queue
    RELEASE_ADDENDUM_READY = "release_addendum_ready"


# Type alias for event handler callables.
# A handler receives the event type and a payload dict.
Handler = Callable[[EventType, dict[str, Any]], Any]


class EventBus:
    """In-process pub/sub event bus with sync and async dispatch.

    Design goals:
    - **Error isolation**: a handler that raises must not prevent other
      handlers from running.  Errors are logged at WARNING level.
    - **Ordering**: handlers are called in subscription order.
    - **No external dependencies**: pure Python, no queues, no threads.
    - **Async-aware**: ``emit_async`` awaits async handlers; ``emit`` calls
      sync handlers only (async handlers registered during a sync context are
      *skipped with a warning*).

    Thread safety: subscribing/unsubscribing is not thread-safe.  The bus is
    intended to be used from the asyncio event loop only.
    """

    def __init__(self) -> None:
        # Maps EventType -> list of (handler, is_async) tuples in order
        self._handlers: dict[str, list[tuple[Handler, bool]]] = {}
        self._lifecycle_publication_lock = threading.RLock()
        self._lifecycle_publication_condition = threading.Condition(
            self._lifecycle_publication_lock
        )
        self._lifecycle_publication_authority: tuple[Any, int, int] | None = None
        self._lifecycle_publication_inflight: dict[Any, int] = {}

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    @staticmethod
    def _key(event_type: EventType | str) -> str:
        """Normalise an event_type to a plain string key.

        ``EventType`` is a ``str`` subclass, so ``str(EventType.X)`` returns
        ``"EventType.X"`` in Python's enum machinery.  We want the *value*
        (e.g. ``"agent_dispatched"``), not the repr.  Using ``.value`` when
        the input is already an ``EventType`` member handles this cleanly.
        """
        if isinstance(event_type, EventType):
            return event_type.value
        return str(event_type)

    def subscribe(self, event_type: EventType | str, handler: Handler) -> None:
        """Register *handler* to be called when *event_type* is emitted.

        Registering the same handler twice for the same event type is a no-op
        (idempotent).  Supports both sync and async handlers.
        """
        key = self._key(event_type)
        is_async = asyncio.iscoroutinefunction(handler)
        handlers = self._handlers.setdefault(key, [])
        # Idempotency: don't add the same handler twice
        for existing, _ in handlers:
            if existing is handler:
                return
        handlers.append((handler, is_async))
        logger.debug("EventBus: subscribed %s to %s (async=%s)", handler, key, is_async)

    def activate_lifecycle_publication_authority(
        self,
        source: Any,
        epoch: int,
        generation: int,
    ) -> None:
        """Install the exact lifecycle source accepted by this event sink."""

        with self._lifecycle_publication_lock:
            self._lifecycle_publication_authority = (
                source,
                int(epoch),
                int(generation),
            )

    def advance_lifecycle_publication_authority(
        self,
        source: Any,
        epoch: int,
        generation: int,
    ) -> bool:
        """Advance one source monotonically without reviving stale work."""

        candidate = (source, int(epoch), int(generation))
        with self._lifecycle_publication_lock:
            authority = self._lifecycle_publication_authority
            if authority is not None:
                if authority[0] is not source:
                    return False
                if authority[1:] > candidate[1:]:
                    return False
            self._lifecycle_publication_authority = candidate
            return True

    def deactivate_lifecycle_publication_authority(
        self,
        source: Any,
        *,
        timeout: float,
    ) -> bool:
        """Close admission and drain callbacks without locking across them."""

        deadline = time.monotonic() + max(float(timeout), 0.0)
        with self._lifecycle_publication_condition:
            authority = self._lifecycle_publication_authority
            if authority is not None and authority[0] is source:
                self._lifecycle_publication_authority = None
            while self._lifecycle_publication_inflight.get(source, 0):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if authority is not None and authority[0] is source:
                        self._lifecycle_publication_authority = authority
                    return False
                self._lifecycle_publication_condition.wait(timeout=remaining)
            self._lifecycle_publication_inflight.pop(source, None)
            return True

    def unsubscribe(self, event_type: EventType | str, handler: Handler) -> bool:
        """Remove *handler* from *event_type*.

        Returns True if the handler was found and removed, False otherwise.
        """
        key = self._key(event_type)
        handlers = self._handlers.get(key, [])
        before = len(handlers)
        self._handlers[key] = [(h, a) for h, a in handlers if h is not handler]
        removed = len(self._handlers[key]) < before
        if removed:
            logger.debug("EventBus: unsubscribed %s from %s", handler, key)
        return removed

    def unsubscribe_all(self, event_type: EventType | str | None = None) -> None:
        """Remove all handlers, optionally scoped to *event_type*.

        If *event_type* is None, clears every handler for all event types.
        """
        if event_type is None:
            self._handlers.clear()
        else:
            self._handlers.pop(self._key(event_type), None)

    def subscriber_count(self, event_type: EventType | str) -> int:
        """Return the number of handlers registered for *event_type*."""
        return len(self._handlers.get(self._key(event_type), []))

    # ------------------------------------------------------------------
    # Synchronous dispatch
    # ------------------------------------------------------------------

    def emit(
        self,
        event_type: EventType | str,
        payload: dict[str, Any] | None = None,
        *,
        source_is_current: Callable[[], bool] | None = None,
        publication_permit: Any | None = None,
    ) -> int:
        """Dispatch *event_type* to all **sync** handlers.

        Async handlers registered for this event are skipped with a warning —
        use :meth:`emit_async` if you need to call async handlers. Lifecycle
        publishers can provide a source predicate; checking it inside the bus
        and again before each handler prevents a retired orchestrator from
        entering a replacement-owned subscriber.

        Returns the number of handlers successfully called.
        """
        if source_is_current is not None and not source_is_current():
            return 0
        key = self._key(event_type)
        # Resolve to the EventType member if possible, else keep as raw string
        value_map = EventType._value2member_map_  # type: ignore[attr-defined]
        et: EventType | str = value_map[key] if key in value_map else key
        payload = dict(payload or {})
        if publication_permit is not None:
            payload[LIFECYCLE_PUBLICATION_PERMIT_KEY] = publication_permit
        handlers = list(self._handlers.get(key, []))
        called = 0
        for handler, is_async in handlers:
            if source_is_current is not None and not source_is_current():
                break
            admitted_source = None
            if publication_permit is not None:
                with self._lifecycle_publication_condition:
                    if self._lifecycle_publication_authority != (
                        publication_permit.source,
                        publication_permit.epoch,
                        publication_permit.expected_generation,
                    ):
                        break
                    admitted_source = publication_permit.source
                    self._lifecycle_publication_inflight[admitted_source] = (
                        self._lifecycle_publication_inflight.get(
                            admitted_source,
                            0,
                        )
                        + 1
                    )
            if is_async:
                logger.warning(
                    "EventBus.emit: async handler %s skipped for %s — use emit_async()",
                    handler,
                    key,
                )
                if admitted_source is not None:
                    with self._lifecycle_publication_condition:
                        self._lifecycle_publication_inflight[admitted_source] -= 1
                        self._lifecycle_publication_condition.notify_all()
                continue
            try:
                handler(et, payload)
                called += 1
            except Exception:
                logger.warning(
                    "EventBus.emit: handler %s raised for event %s",
                    handler,
                    key,
                    exc_info=True,
                )
            finally:
                if admitted_source is not None:
                    with self._lifecycle_publication_condition:
                        self._lifecycle_publication_inflight[admitted_source] -= 1
                        self._lifecycle_publication_condition.notify_all()
        return called

    # ------------------------------------------------------------------
    # Async dispatch
    # ------------------------------------------------------------------

    async def emit_async(
        self, event_type: EventType | str, payload: dict[str, Any] | None = None
    ) -> int:
        """Dispatch *event_type* to all handlers, awaiting async ones.

        Sync handlers are called directly (not scheduled on the loop).
        Returns the number of handlers successfully called.
        """
        key = self._key(event_type)
        value_map = EventType._value2member_map_  # type: ignore[attr-defined]
        et: EventType | str = value_map[key] if key in value_map else key
        payload = payload or {}
        handlers = list(self._handlers.get(key, []))
        called = 0
        for handler, is_async in handlers:
            try:
                if is_async:
                    await handler(et, payload)
                else:
                    handler(et, payload)
                called += 1
            except Exception:
                logger.warning(
                    "EventBus.emit_async: handler %s raised for event %s",
                    handler,
                    key,
                    exc_info=True,
                )
        return called

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        counts = {k: len(v) for k, v in self._handlers.items() if v}
        return f"EventBus({counts!r})"

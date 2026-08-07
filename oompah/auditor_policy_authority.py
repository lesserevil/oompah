"""Linearization authority for live terminal-auditor policy changes."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class AuditorPolicyAuthority:
    """Shared optimistic generation and short admission/mutation mutex."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._generation = 0

    def generation(self) -> int:
        with self._lock:
            return self._generation

    @contextmanager
    def admission(self, expected_generation: int) -> Iterator[bool]:
        """Hold the policy boundary and report whether a snapshot is current."""

        with self._lock:
            yield self._generation == expected_generation

    @contextmanager
    def mutation(self) -> Iterator[None]:
        """Serialize a policy write and publish it before releasing writers."""

        with self._lock:
            try:
                yield
            finally:
                # Failed writes bump conservatively: a concurrent admission
                # may retry, but can never contact using a stale snapshot.
                self._generation += 1


AUDITOR_POLICY_AUTHORITY = AuditorPolicyAuthority()

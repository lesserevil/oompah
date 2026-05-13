"""Per-backend console event translators.

The console transcript on disk is normalized (see
:mod:`oompah.console_format`); but the SDKs that produce and consume it
speak backend-specific dialects. This package owns the mapping in both
directions:

* :func:`acp_to_normalized` — backend event → normalized event
* :func:`normalized_to_sdk_history` — list of normalized events →
  SDK-compatible conversation history

Each registered backend lives in a submodule (``claude.py``,
``codex.py``, …) and provides those two functions. This package's
:func:`get_translator` dispatches by backend name so callers
(``oompah.console`` in the downstream bead) don't have to import each
backend individually.
"""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from oompah.console_format import ConsoleEvent

if TYPE_CHECKING:
    from oompah.agent import AgentEvent  # noqa: F401  # used in type hints


# ---------------------------------------------------------------------------
# Translator protocol
# ---------------------------------------------------------------------------


class Translator:
    """Bundle of the two translator functions a backend exposes.

    Kept as a thin namedtuple-shaped class rather than a Protocol so
    callers can do attribute access and modules can register
    themselves with one line.
    """

    __slots__ = ("backend", "acp_to_normalized", "normalized_to_sdk_history")

    def __init__(
        self,
        backend: str,
        acp_to_normalized: Callable[[Any], ConsoleEvent],
        normalized_to_sdk_history: Callable[[list[ConsoleEvent]], list[dict]],
    ) -> None:
        self.backend = backend
        self.acp_to_normalized = acp_to_normalized
        self.normalized_to_sdk_history = normalized_to_sdk_history


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_TRANSLATORS: dict[str, Translator] = {}


def register_translator(translator: Translator) -> None:
    """Register a backend translator. Idempotent — later registrations
    of the same backend name override earlier ones (mirrors how
    :mod:`oompah.acp_backends.registry` handles re-registration)."""
    _TRANSLATORS[translator.backend] = translator


def get_translator(backend: str | None) -> Translator:
    """Return the translator for ``backend``. Defaults to ``"claude"``
    when ``backend`` is ``None`` to preserve back-compat with old
    transcripts that pre-date the multi-backend split.

    Raises :class:`KeyError` for an unregistered backend name.
    """
    name = backend or "claude"
    try:
        return _TRANSLATORS[name]
    except KeyError as exc:
        raise KeyError(
            f"No console translator registered for backend {name!r}. "
            f"Known: {sorted(_TRANSLATORS)}"
        ) from exc


def known_backends() -> list[str]:
    """Sorted list of registered backend names. Useful for tests and
    diagnostics."""
    return sorted(_TRANSLATORS)


# ---------------------------------------------------------------------------
# Convenience wrappers (dispatch by backend name)
# ---------------------------------------------------------------------------


def acp_to_normalized(acp_event: Any, *, backend: str | None = None) -> ConsoleEvent:
    """Dispatch ``acp_event`` to the configured backend's translator.

    Defaults to the ``"claude"`` translator when no backend is given.
    The caller can also import the backend's translator directly if
    they prefer the explicit path.
    """
    return get_translator(backend).acp_to_normalized(acp_event)


def normalized_to_sdk_history(
    events: list[ConsoleEvent], *, backend: str | None = None
) -> list[dict]:
    """Dispatch ``events`` to the configured backend's history builder."""
    return get_translator(backend).normalized_to_sdk_history(events)


# ---------------------------------------------------------------------------
# Side-effect imports: each submodule registers itself on import.
# ---------------------------------------------------------------------------

from oompah.console_translators import claude as _claude  # noqa: E402,F401
from oompah.console_translators import codex as _codex  # noqa: E402,F401


__all__ = [
    "Translator",
    "register_translator",
    "get_translator",
    "known_backends",
    "acp_to_normalized",
    "normalized_to_sdk_history",
]

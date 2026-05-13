"""Codex-backend console event translator (v1 stub).

The full mapping between Codex's ``openai-agents`` SDK events and the
normalized :class:`oompah.console_format.ConsoleEvent` form is tracked
in oompah-zlz_2-elug (Console 6/6). This module ships only the
registration shim so :mod:`oompah.console_translators` can dispatch
``backend="codex"`` calls; both translator functions raise
:class:`NotImplementedError` until elug lands.

The shim is in place so the ConsoleManager / ConsoleSession bead
(oompah-zlz_2-49tv) can validate the dispatch path end-to-end —
calling code that asks for the codex translator gets a clear,
actionable error instead of a ``KeyError`` from the registry, and
tests can assert the stub raises without an SDK install.
"""

from __future__ import annotations

import logging
from typing import Any

from oompah.console_format import ConsoleEvent
from oompah.console_translators import Translator, register_translator

logger = logging.getLogger(__name__)


_BACKEND_NAME = "codex"

_NOT_IMPLEMENTED_MSG = (
    "Codex console translator is not implemented yet. Tracked in "
    "oompah-zlz_2-elug (Console 6/6). Use backend='claude' for the v1 "
    "console session."
)


def acp_to_normalized(acp_event: Any) -> ConsoleEvent:
    """Stub: raises :class:`NotImplementedError` until elug lands."""
    raise NotImplementedError(_NOT_IMPLEMENTED_MSG)


def normalized_to_sdk_history(events: list[ConsoleEvent]) -> list[dict]:
    """Stub: raises :class:`NotImplementedError` until elug lands."""
    raise NotImplementedError(_NOT_IMPLEMENTED_MSG)


register_translator(
    Translator(
        backend=_BACKEND_NAME,
        acp_to_normalized=acp_to_normalized,
        normalized_to_sdk_history=normalized_to_sdk_history,
    )
)

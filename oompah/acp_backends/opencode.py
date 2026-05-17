"""OpenCode backend (the third registered ACP backend).

Placeholder stub for the OpenCode ACP backend. This registers itself
in the BACKENDS registry so the GET /api/v1/acp-backends endpoint
surfaces opencode as a selectable option in the provider edit dialog.

The session implementation (OpencodeAcpBackendSession) is a minimal
stub that returns an error status until the real SDK-backed
implementation lands. The orchestrator will not dispatch to opencode
until a real session is wired up.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from oompah.acp_backends.base import (
    AcpBackend,
    AcpBackendOptions,
    AcpBackendSession,
    BackendEvent,
)
from oompah.acp_backends.registry import register_backend

if TYPE_CHECKING:
    from oompah.models import ModelProvider

logger = logging.getLogger(__name__)


class OpencodeAcpBackendSession(AcpBackendSession):
    """Minimal stub session for the OpenCode backend.

    Returns an error status so the orchestrator can detect and surface
    the unimplemented backend rather than silently spinning.
    """

    def __init__(self, options: AcpBackendOptions):
        self._options = options
        self._status: str = "pending"
        self._last_error: str | None = None

    async def run_turn(self):
        self._last_error = "OpenCode ACP backend is not yet implemented"
        logger.warning(self._last_error)
        self._status = "errored"
        return
        yield  # pragma: no cover — not reached

    async def close(self) -> None:
        pass

    @property
    def status(self) -> str:
        return self._status

    @property
    def input_tokens(self) -> int:
        return 0

    @property
    def output_tokens(self) -> int:
        return 0

    @property
    def total_tokens(self) -> int:
        return 0

    @property
    def session_id(self) -> str | None:
        return None

    @property
    def turn_count(self) -> int:
        return 0

    @property
    def total_cost_usd(self) -> float | None:
        return None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def permission_denials(self) -> list:
        return []


class OpencodeAcpBackend(AcpBackend):
    """OpenCode ACP backend (stub).

    Until the real SDK-backed implementation lands, attempting to
    start a session produces an error event so the orchestrator can
    surface a useful message rather than silently failing.
    """

    @classmethod
    def name(cls) -> str:
        return "opencode"

    def start_session(self, options: AcpBackendOptions) -> OpencodeAcpBackendSession:
        return OpencodeAcpBackendSession(options)

    def validate_provider(self, provider: "ModelProvider") -> list[str]:
        """Placeholder validation — accepts any provider since OpenCode
        may use any SDK-provided authentication mechanism."""
        return []


# Register on import. ``oompah/acp_backends/__init__.py`` imports this
# module so the package import wires ``opencode`` into the registry
# alongside ``claude`` and ``codex``.
register_backend(OpencodeAcpBackend.name(), OpencodeAcpBackend)
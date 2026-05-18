"""ACP backend abstraction.

This package introduces a pluggable backend layer for ACP-mode sessions.
The first registered backend is :class:`ClaudeAcpBackend` (the historical
default — drives the bundled ``claude`` CLI via the Claude Agent SDK so
per-token cost bills against the operator's Pro/Max subscription).

Future backends (Codex, OpenCode, etc.) plug in by subclassing
:class:`AcpBackend` and registering themselves at import time via
:func:`register_backend`. See ``plans/acp-agent.md`` for the design
motivation and the multi-backend epic.

Public surface:

* :class:`AcpBackend` — the abstract base class every backend implements.
* :class:`AcpBackendSession` — the session-shaped protocol every
  backend yields from ``start_session``.
* :class:`AcpBackendOptions` — typed kwargs passed to ``start_session``.
* :class:`BackendEvent` — typed dataclass the backend session yields
  from ``run_turn``.
* :data:`BACKENDS` — the registry dict mapping ``name -> class``.
* :func:`register_backend` — register a new backend at import time.
* :func:`get_backend` — look up a backend class by name (``None`` if
  not registered).
* :func:`get_backend_or_raise` — same, but raises a ValueError with a
  clear list of available backends.
* :func:`validate_provider_backend` — validate a ModelProvider's
  ``backend`` field for a given profile-mode context.
"""

from __future__ import annotations

from oompah.acp_backends.base import (
    AcpBackend,
    AcpBackendOptions,
    AcpBackendSession,
    BackendEvent,
)
from oompah.acp_backends.registry import (
    BACKENDS,
    get_backend,
    get_backend_or_raise,
    register_backend,
    validate_provider_backend,
)

# Importing the backend modules registers each concrete backend
# (``ClaudeAcpBackend`` as ``claude``, ``CodexAcpBackend`` as
# ``codex``, ``OpenCodeAcpBackend`` as ``opencode``) at import time.
# Side-effect imports are awkward but necessary for the zero-config
# back-compat path: a fresh ``import oompah.acp_backends`` must
# produce a fully-populated registry without callers having to
# remember to import each backend module separately.
#
# Order matters only for the registry's deterministic ordering when
# the /providers UI lists backends — Claude is the historical
# default and remains first; Codex follows as the second backend;
# OpenCode is the third (bead oompah-zlz_2-p1ti).
from oompah.acp_backends import claude as _claude  # noqa: F401, E402
from oompah.acp_backends import codex as _codex  # noqa: F401, E402
from oompah.acp_backends import opencode as _opencode  # noqa: F401, E402
from oompah.acp_backends import opencode as _opencode  # noqa: F401, E402
from oompah.acp_backends.opencode import (  # noqa: F401, E402
    OpencodeAcpBackend,
    OpencodeAcpBackendSession,
)

__all__ = [
    "AcpBackend",
    "AcpBackendOptions",
    "AcpBackendSession",
    "BackendEvent",
    "BACKENDS",
    "register_backend",
    "get_backend",
    "get_backend_or_raise",
    "validate_provider_backend",
    "OpencodeAcpBackend",
    "OpencodeAcpBackendSession",
]

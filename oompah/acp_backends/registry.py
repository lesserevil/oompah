"""ACP backend registry.

A tiny module-level dict + a few helpers. Concrete backend modules
(claude.py, future codex.py) call :func:`register_backend` at import
time to wire themselves in.

The registry is intentionally a plain dict rather than a class — we
have at most a handful of backends, never need thread-safety beyond
import-time mutation, and the test suite needs to insert/remove
``"fake"`` entries without monkey-patching state hidden behind a
class instance.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from oompah.acp_backends.base import AcpBackend

if TYPE_CHECKING:
    from oompah.models import ModelProvider

logger = logging.getLogger(__name__)


# Module-level registry. Keys are stable strings persisted in
# ModelProvider.backend on disk — change them carefully or document
# migrations.
BACKENDS: dict[str, type[AcpBackend]] = {}


def register_backend(name: str, cls: type[AcpBackend]) -> None:
    """Register a backend under ``name`` in the global :data:`BACKENDS`.

    Re-registering an existing key is a logged warning rather than an
    error so tests can override the production registration with a
    fake. The persisted-on-disk default for ACP-mode providers is
    ``"claude"`` so production code should not register over that key.
    """
    if not isinstance(name, str) or not name:
        raise ValueError(f"backend name must be a non-empty string, got {name!r}")
    if not (isinstance(cls, type) and issubclass(cls, AcpBackend)):
        raise TypeError(
            f"backend class must subclass AcpBackend, got {cls!r}"
        )
    if name in BACKENDS and BACKENDS[name] is not cls:
        logger.warning(
            "Re-registering ACP backend %r (was %s, now %s)",
            name, BACKENDS[name].__name__, cls.__name__,
        )
    BACKENDS[name] = cls


def get_backend(name: str | None) -> type[AcpBackend] | None:
    """Look up a backend class by name; return ``None`` if unknown.

    ``None`` (passed when a legacy provider has no backend field) is
    treated as the empty string and returns ``None``; callers that
    want the default should fall back to ``"claude"`` explicitly.
    """
    if not name:
        return None
    return BACKENDS.get(name)


def get_backend_or_raise(name: str | None) -> type[AcpBackend]:
    """Same as :func:`get_backend` but raises a ValueError with a
    list of available backends when the name is unregistered.

    Used by dispatch code paths that cannot proceed without a backend.
    """
    cls = get_backend(name)
    if cls is None:
        raise ValueError(
            f"Unknown ACP backend: {name!r}. "
            f"Registered backends: {sorted(BACKENDS)}"
        )
    return cls


def validate_provider_backend(
    provider: "ModelProvider", mode: str
) -> list[str]:
    """Validate ``provider.backend`` for the given profile-mode context.

    Rules (locked in by issue oompah-zlz_2-0hzh acceptance criteria):

    * When ``mode == "acp"``: ``provider.backend`` must resolve to a
      registered backend. A ``None`` field defaults to ``"claude"``
      for back-compat with providers persisted before this field
      existed.
    * When ``mode != "acp"``: ``provider.backend`` is ignored. We do
      not return an error even if the field is set (operators are
      allowed to pre-populate the backend in case they later switch
      a profile to ACP mode).

    Returns a list of human-readable error strings. Empty list means
    the (provider, mode) tuple is valid.
    """
    errors: list[str] = []
    if mode != "acp":
        return errors
    name = getattr(provider, "backend", None) or "claude"
    if name not in BACKENDS:
        errors.append(
            f"Unknown ACP backend: {name!r}. "
            f"Registered backends: {sorted(BACKENDS)}"
        )
    return errors

"""Server-authenticated username → project actor login mapping (OOMPAH-624).

When HTTP Basic authentication is enabled, the authenticated htpasswd
username is the *server principal*.  Owner-gated project mutations decide
authorization from that principal rather than from a client-supplied
``actor_login`` string.  Some deployments run a service account whose
htpasswd username does not match the project owner's GitHub / GitLab
login (for example, a service account named ``ci-bot`` acting for
``alice``).  This module provides an explicit, validated mapping between
those identities.

Configuration
-------------
Two mutually exclusive sources are consulted at startup, in priority order:

``OOMPAH_ACTOR_MAP``
    Inline JSON object mapping htpasswd usernames to project actor logins::

        OOMPAH_ACTOR_MAP='{"ci-bot": "alice", "release-bot": "carol"}'

``OOMPAH_ACTOR_MAP_FILE``
    Path to a JSON file (identical object shape).  Relative paths are
    resolved against the selected env-file directory.

``OOMPAH_ACTOR_MAP_STRICT``
    When ``"true"`` / ``"1"`` / ``"yes"``, an authenticated user that has
    no mapping entry cannot perform *any* actor-bound mutation — the
    request is refused at authorization time.  When falsy (default),
    unmapped users use identity mapping: their htpasswd username IS the
    project actor login.

Validation
----------
The map is validated at load time.  Failures raise
:class:`ActorMapError` and cause startup to abort:

* JSON must decode to an object.
* Keys and values must be non-empty strings.
* Keys must be unique after case-folding (JSON already prohibits
  duplicate keys, but we defend against overrides through env + file
  interactions).
* Values (target project actor logins) must be unique after
  case-folding.  Two htpasswd usernames mapping to the same project
  actor would create an ambiguous audit trail, so we fail closed.

Security posture
----------------
* If neither variable is set: identity mapping.  No configuration
  required for single-tenant deployments where the operator's htpasswd
  username matches the project owner's login.
* If configuration is present but invalid: startup fails.  We never
  silently fall back to identity mapping when the operator explicitly
  configured a mapping.
* Case-insensitive comparison follows the same conventions as
  :mod:`oompah.label_auth` and :mod:`oompah.transition_gate`.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Mapping

logger = logging.getLogger(__name__)


class ActorMapError(Exception):
    """Raised when the actor-mapping configuration is malformed or ambiguous."""


_ENV_MAP = "OOMPAH_ACTOR_MAP"
_ENV_MAP_FILE = "OOMPAH_ACTOR_MAP_FILE"
_ENV_STRICT = "OOMPAH_ACTOR_MAP_STRICT"


def _is_truthy(value: str | None) -> bool:
    """Return True when *value* is a common truthy string spelling."""

    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class ActorMap:
    """Immutable server-username → project-actor-login map.

    Attributes:
        entries: The case-folded username → actor mapping.  Keys and
            values are lowercased strings.
        strict: When True, unmapped usernames cannot resolve to an actor
            login (:meth:`resolve` returns ``None``).
        source: Human-readable provenance for diagnostics (env, file
            path, or ``"unset"``).
    """

    entries: Mapping[str, str] = field(default_factory=dict)
    strict: bool = False
    source: str = "unset"

    def resolve(self, username: str) -> str | None:
        """Return the project actor login for *username*.

        Args:
            username: The authenticated server principal (htpasswd user).

        Returns:
            The mapped actor login when an entry exists.  When no entry
            exists and :attr:`strict` is False, the original username is
            returned unchanged (identity mapping).  When strict mode is
            on and no entry exists, returns ``None`` — callers must
            treat this as *no authorized actor*.
        """

        if not username:
            return None
        key = username.strip().lower()
        if key in self.entries:
            return self.entries[key]
        if self.strict:
            return None
        return username.strip()


def _parse_json_map(raw: str, source: str) -> dict[str, str]:
    """Parse *raw* JSON and validate that it is an object of strings.

    Args:
        raw: JSON text from env var or file contents.
        source: Provenance label for diagnostics.

    Returns:
        Dict of key → value with entries pre-validated (non-empty).  The
        caller normalizes the keys/values and enforces uniqueness.

    Raises:
        ActorMapError: When *raw* does not decode to a mapping of
            non-empty strings.
    """

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ActorMapError(
            f"{source}: not valid JSON ({exc.msg}, line {exc.lineno} col {exc.colno})"
        ) from None
    if not isinstance(parsed, dict):
        raise ActorMapError(f"{source}: expected a JSON object, got {type(parsed).__name__}")
    validated: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not key.strip():
            raise ActorMapError(f"{source}: keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ActorMapError(
                f"{source}: value for {key!r} must be a non-empty string"
            )
        validated[key.strip()] = value.strip()
    return validated


def _normalize(entries: dict[str, str], source: str) -> dict[str, str]:
    """Lowercase keys and enforce uniqueness.

    Args:
        entries: Raw {username: actor} pairs (may have mixed case).
        source: Provenance label for diagnostics.

    Returns:
        Case-folded {username_lower: actor_login_original_case} where
        keys and values are unique.  Values retain their original casing
        so that audit messages display them as the operator configured.

    Raises:
        ActorMapError: When two htpasswd users collide after case-fold
            OR when two htpasswd users map to the same project actor.
    """

    normalized: dict[str, str] = {}
    values_seen: dict[str, str] = {}
    for user, actor in entries.items():
        key = user.lower()
        if key in normalized:
            raise ActorMapError(
                f"{source}: duplicate htpasswd username {user!r} "
                "(matches an earlier entry after case-folding)"
            )
        value_key = actor.lower()
        prior_user = values_seen.get(value_key)
        if prior_user is not None:
            raise ActorMapError(
                f"{source}: ambiguous mapping — {user!r} and "
                f"{prior_user!r} both target project actor {actor!r}. "
                "Each htpasswd username must map to a unique actor."
            )
        normalized[key] = actor
        values_seen[value_key] = user
    return normalized


def _read_map_file(path: str, env_file_dir: str) -> str:
    """Read the actor-map file, resolving relative paths safely.

    Args:
        path: Configured file path (relative or absolute).
        env_file_dir: Anchor directory for relative paths.

    Returns:
        The file's UTF-8 contents.

    Raises:
        ActorMapError: When the file does not exist or cannot be read.
    """

    resolved = path if os.path.isabs(path) else os.path.normpath(os.path.join(env_file_dir, path))
    if not os.path.isfile(resolved):
        raise ActorMapError(f"OOMPAH_ACTOR_MAP_FILE not found: {resolved!r}")
    try:
        with open(resolved, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise ActorMapError(
            f"OOMPAH_ACTOR_MAP_FILE {resolved!r} could not be read: {exc.strerror}"
        ) from exc


def load_actor_map(env_file_dir: str, env: Mapping[str, str] | None = None) -> ActorMap:
    """Load and validate the actor-map configuration.

    Args:
        env_file_dir: Anchor directory used to resolve relative
            ``OOMPAH_ACTOR_MAP_FILE`` values.  Callers pass the
            currently-selected env file's directory.
        env: Environment override.  Defaults to :data:`os.environ`.

    Returns:
        The parsed :class:`ActorMap`.  When no configuration is present,
        the returned map is empty and non-strict — every authenticated
        username resolves through identity mapping.

    Raises:
        ActorMapError: On invalid configuration (bad JSON, missing file,
            ambiguous mapping, empty strings, ...).  Fail-closed by
            design; do not fall back to identity mapping when a
            configured source is broken.
    """

    environ = env if env is not None else os.environ
    strict = _is_truthy(environ.get(_ENV_STRICT))

    inline_raw = (environ.get(_ENV_MAP) or "").strip()
    file_path = (environ.get(_ENV_MAP_FILE) or "").strip()

    if inline_raw and file_path:
        raise ActorMapError(
            "Set exactly one of OOMPAH_ACTOR_MAP or OOMPAH_ACTOR_MAP_FILE, "
            "not both."
        )

    if inline_raw:
        entries_raw = _parse_json_map(inline_raw, source=_ENV_MAP)
        entries = _normalize(entries_raw, source=_ENV_MAP)
        return ActorMap(entries=entries, strict=strict, source=_ENV_MAP)

    if file_path:
        text = _read_map_file(file_path, env_file_dir)
        source = f"OOMPAH_ACTOR_MAP_FILE={file_path!r}"
        entries_raw = _parse_json_map(text, source=source)
        entries = _normalize(entries_raw, source=source)
        return ActorMap(entries=entries, strict=strict, source=source)

    if strict:
        # Strict mode without an explicit map is a config error: every
        # user would be unable to mutate anything.  Rather than silently
        # locking the entire deployment out, refuse to start.
        raise ActorMapError(
            "OOMPAH_ACTOR_MAP_STRICT is set but no mapping is configured. "
            "Set OOMPAH_ACTOR_MAP or OOMPAH_ACTOR_MAP_FILE, or unset "
            "OOMPAH_ACTOR_MAP_STRICT to allow identity mapping."
        )

    return ActorMap()

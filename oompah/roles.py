"""Role storage and management.

File-backed CRUD store for role_name → (provider_id, model) mappings,
parallel to AgentProfileStore / ProviderStore.
Roles are persisted to ``.oompah/roles.json``.

Each role maps a human-readable name (e.g. "fast", "standard", "deep",
"default") to a (provider_id, model) pair that tells the dispatcher
which provider and model to use for that role.

Validation rules (enforced by ``set``):

- ``name`` must be non-empty.
- ``provider_id`` must exist in ProviderStore.
- ``model`` must be in provider.models (or provider must be ACP-mode
  with empty catalog).

See oompah-zlz_2-fuug for the design of this foundation.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_ROLES_PATH = ".oompah/roles.json"


@dataclass
class Role:
    """A role mapping: name → (provider_id, model)."""

    name: str
    provider_id: str
    model: str
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-friendly dict."""
        return {
            "name": self.name,
            "provider_id": self.provider_id,
            "model": self.model,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Role:
        """Construct a Role from its JSON dict.

        Permissive about types: parses datetime from ISO string,
        falls back to now() for missing updated_at.
        """
        raw_ts = d.get("updated_at")
        updated_at: datetime
        if raw_ts:
            if isinstance(raw_ts, datetime):
                updated_at = raw_ts
            else:
                try:
                    updated_at = datetime.fromisoformat(str(raw_ts))
                except (ValueError, TypeError):
                    updated_at = datetime.now(timezone.utc)
        else:
            updated_at = datetime.now(timezone.utc)

        return cls(
            name=str(d.get("name", "")),
            provider_id=str(d.get("provider_id", "")),
            model=str(d.get("model", "")),
            updated_at=updated_at,
        )


class RoleError(ValueError):
    """Raised when a CRUD operation fails validation.

    Subclass of ValueError so callers that already catch ValueError keep
    working; new code should catch RoleError to distinguish role-store
    errors from generic value errors.
    """


# Callback signature: receives a fresh ``dict[str, Role]`` snapshot and a
# free-form ``source`` string (e.g. 'set', 'delete').
# Callbacks must NOT raise — failures are logged and the write still succeeds.
ReloadCallback = Callable[[dict[str, Role], str], None]


class RoleStore:
    """File-backed CRUD store for Role.

    Roles are keyed by ``name`` (the role identifier surfaced in the
    dashboard and used by the dispatcher). The on-disk format is a
    JSON array of role dicts produced by ``Role.to_dict()``; loading
    uses ``Role.from_dict``.
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        provider_store: Any = None,
        reload_callback: ReloadCallback | None = None,
    ):
        """Open or create the store at ``path``.

        ``provider_store`` is an instance of ``ProviderStore`` used for
        validation. When None, validation is skipped (test-only).

        ``reload_callback``, if provided, is invoked after every
        successful set/delete with the post-mutation role dict and a
        free-form source string. It runs OUTSIDE the internal lock so a
        slow callback cannot block other writers. See
        ``set_reload_callback`` for late binding.
        """
        self.path = path or DEFAULT_ROLES_PATH
        self._roles: dict[str, Role] = {}
        self._provider_store = provider_store
        self._lock = threading.Lock()
        self._reload_callback: ReloadCallback | None = reload_callback
        self._load()

    # ------------------------------------------------------------------
    # Reload-callback wiring
    # ------------------------------------------------------------------

    def set_reload_callback(self, cb: ReloadCallback | None) -> None:
        """Register (or clear) the reload callback.

        Safe to call at any time.
        """
        self._reload_callback = cb

    def _fire_reload(self, source: str) -> None:
        """Invoke the reload callback with a fresh role snapshot.

        Invoked outside the lock so a slow callback cannot block other
        writers. Exceptions are swallowed and logged.
        """
        cb = self._reload_callback
        if cb is None:
            return
        snapshot = self.list_all()
        snapshot_dict = {r.name: r for r in snapshot}
        try:
            cb(snapshot_dict, source)
        except Exception as exc:  # noqa: BLE001 — callback must never break a write
            logger.warning(
                "Role store reload callback failed (source=%s): %s",
                source, exc,
            )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self.path):
            self._roles = {}
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self._roles = {}
            if isinstance(data, list):
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    role = Role.from_dict(entry)
                    if role.name and role.name not in self._roles:
                        self._roles[role.name] = role
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load roles from %s: %s", self.path, exc
            )
            self._roles = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(
                [r.to_dict() for r in self._roles.values()],
                f,
                indent=2,
            )

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def list_all(self) -> list[Role]:
        """Return all roles as a list (snapshot under lock)."""
        with self._lock:
            return list(self._roles.values())

    def get(self, name: str) -> Role | None:
        """Get a role by name."""
        with self._lock:
            return self._roles.get(name)

    @property
    def is_empty(self) -> bool:
        """True when the store has no roles."""
        return not self._roles

    # ------------------------------------------------------------------
    # Write API (validates; persists; idempotent)
    # ------------------------------------------------------------------

    def set(self, name: str, provider_id: str, model: str) -> Role:
        """Create or update a role mapping.

        Validates that provider_id exists in ProviderStore and model is
        in provider.models (or provider is ACP-mode with empty catalog).

        Args:
            name: Role name (e.g. "fast", "standard").
            provider_id: Provider ID (must exist in ProviderStore).
            model: Model name (must be in provider's catalog, or
                   provider is ACP-mode with empty catalog).

        Returns:
            The created or updated Role.

        Raises:
            RoleError: On validation failure.
        """
        self._validate(name, provider_id, model)
        with self._lock:
            role = Role(
                name=name,
                provider_id=provider_id,
                model=model,
                updated_at=datetime.now(timezone.utc),
            )
            self._roles[name] = role
            self._save()
        self._fire_reload("set")
        return role

    def delete(self, name: str) -> bool:
        """Delete a role by name.

        Returns True iff something was removed.
        """
        with self._lock:
            if name not in self._roles:
                return False
            del self._roles[name]
            self._save()
        self._fire_reload("delete")
        return True

    def snapshot(self) -> dict[str, Role]:
        """Return a snapshot of the current state for later rollback.

        The returned dict is a deep copy — mutations to it do not
        affect the store.
        """
        with self._lock:
            return {name: Role(
                name=r.name,
                provider_id=r.provider_id,
                model=r.model,
                updated_at=r.updated_at,
            ) for name, r in self._roles.items()}

    def restore(self, snapshot: dict[str, Role]) -> None:
        """Restore the store to a previous snapshot.

        Replaces the entire store with the snapshot contents.
        """
        with self._lock:
            self._roles = dict(snapshot)
            self._save()
        self._fire_reload("restore")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, name: str, provider_id: str, model: str) -> None:
        """Validate role fields against ProviderStore.

        Raises RoleError on the first failure with a human-readable
        message.
        """
        name = (name or "").strip()
        if not name:
            raise RoleError("name must be non-empty")

        provider_id = (provider_id or "").strip()
        if not provider_id:
            raise RoleError("provider_id must be non-empty")

        model = (model or "").strip()
        # Provider lookup runs first so we can decide whether model is
        # required based on provider mode + catalog.
        provider = (
            self._provider_store.get(provider_id)
            if self._provider_store is not None
            else None
        )
        if self._provider_store is not None and provider is None:
            raise RoleError(
                f"provider_id {provider_id!r} does not exist in ProviderStore"
            )

        # ACP-mode providers with an empty catalog manage model
        # selection through the SDK (e.g. Claude SDK uses the operator's
        # subscription tier). For those, model is optional.
        is_acp = (
            provider is not None
            and getattr(provider, "mode", "api") == "acp"
        )
        catalog = list((provider.models if provider else None) or [])
        if not model:
            if not (is_acp and not catalog):
                raise RoleError("model must be non-empty")
            return
        if catalog and model not in catalog:
            raise RoleError(
                f"model {model!r} not in provider {provider.name!r}'s catalog "
                f"(have: {', '.join(catalog)})"
            )


# ---------------------------------------------------------------------------
# Migration from AgentProfileStore (oompah-zlz_2-fuug)
# ---------------------------------------------------------------------------


def migrate_agent_profiles_to_roles(
    role_store: "RoleStore",
    profiles: list["AgentProfile"],
    provider_store: Any = None,
) -> int:
    """Migrate agent profiles into RoleStore, inferring the model when needed.

    For each profile that has ``provider_id`` and ``model_role``, write
    into ``role_store[profile.model_role]`` if that slot is empty.
    Model resolution order (first non-empty wins):

      1. ``profile.model`` (explicit override on the profile)
      2. ``provider.model_roles[profile.model_role]`` (pre-xau7 per-provider role map)
      3. ``provider.default_model``

    Roles that can't be resolved to a (provider, model) pair are
    skipped with a debug log. Returns the number of roles migrated.

    ``provider_store`` is optional for back-compat with callers that
    don't have one in scope; when None, only profile.model is used.
    """
    migrated = 0
    for profile in profiles:
        if not profile.provider_id or not profile.model_role:
            continue
        if role_store.get(profile.model_role) is not None:
            continue

        # Resolve the model: profile.model > provider.model_roles[role] > provider.default_model
        model = profile.model
        if not model and provider_store is not None:
            provider = provider_store.get(profile.provider_id)
            if provider is not None:
                model_roles = getattr(provider, "model_roles", None) or {}
                model = model_roles.get(profile.model_role) or getattr(provider, "default_model", None)
        if not model:
            logger.debug(
                "Migration skipped role %r from profile %r: no model resolvable",
                profile.model_role, profile.name,
            )
            continue

        try:
            role_store.set(
                name=profile.model_role,
                provider_id=profile.provider_id,
                model=model,
            )
            migrated += 1
            logger.info(
                "Migrated role %r from profile %r (provider=%s, model=%s)",
                profile.model_role, profile.name, profile.provider_id, model,
            )
        except RoleError as exc:
            logger.warning(
                "Migration skipped role %r from profile %r: %s",
                profile.model_role, profile.name, exc,
            )
    if migrated:
        logger.info(
            "Migrated %d role(s) from agent profiles to RoleStore", migrated
        )
    return migrated
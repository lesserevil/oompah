"""Role storage and management.

File-backed CRUD store for role_name → (strategy, candidates) mappings,
parallel to AgentProfileStore / ProviderStore.
Roles are persisted to ``.oompah/roles.json``.

Each role maps a human-readable name (e.g. "fast", "standard", "deep",
"default") to a strategy and an ordered list of provider/model candidates.
The strategy governs how the dispatcher selects from the list at runtime
(e.g. priority → try first candidate, fall back on failure; round_robin
→ cycle across candidates).

Backward compatibility:
  Old roles.json files that store a single ``provider_id`` / ``model``
  at the top level of each entry are loaded automatically as one-candidate
  "priority" roles.  The persisted schema is always the new multi-candidate
  format.

Validation rules (enforced by ``set`` / ``set_candidates``):

- ``name`` must be non-empty.
- ``strategy`` must be one of ``VALID_STRATEGIES``.
- ``candidates`` must be non-empty.
- Each candidate's ``provider_id`` must exist in ProviderStore.
- Each candidate's ``model`` must be in provider.models (or provider must
  be ACP-mode with empty catalog).
- Duplicate ``(provider_id, model)`` pairs within a role are rejected.

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

#: The set of strategies a role may declare.
VALID_STRATEGIES: frozenset[str] = frozenset({"priority", "round_robin"})
DEFAULT_STRATEGY = "priority"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """A single provider/model candidate for a role."""

    provider_id: str
    model: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to JSON-friendly dict."""
        return {"provider_id": self.provider_id, "model": self.model}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Candidate":
        """Construct from a JSON dict."""
        return cls(
            provider_id=str(d.get("provider_id") or ""),
            model=str(d.get("model") or ""),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Candidate):
            return NotImplemented
        return self.provider_id == other.provider_id and self.model == other.model

    def __hash__(self) -> int:
        return hash((self.provider_id, self.model))


@dataclass
class Role:
    """A role mapping: name → strategy + candidates.

    ``strategy`` controls how the dispatcher selects among ``candidates``
    at runtime.  Allowed values: "priority", "round_robin".

    ``candidates`` is an ordered list of :class:`Candidate` objects.

    Backward-compat properties ``provider_id`` and ``model`` delegate to
    the first candidate so existing callers that access these fields
    continue to work without modification.
    """

    name: str
    strategy: str
    candidates: list[Candidate]
    updated_at: datetime

    # ------------------------------------------------------------------
    # Backward-compat properties (first-candidate projection)
    # ------------------------------------------------------------------

    @property
    def provider_id(self) -> str:
        """First candidate's provider_id (backward-compat convenience)."""
        return self.candidates[0].provider_id if self.candidates else ""

    @property
    def model(self) -> str:
        """First candidate's model (backward-compat convenience)."""
        return self.candidates[0].model if self.candidates else ""

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-friendly dict (new multi-candidate schema)."""
        return {
            "name": self.name,
            "strategy": self.strategy,
            "candidates": [c.to_dict() for c in self.candidates],
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Role":
        """Construct a Role from its JSON dict.

        Supports both the new multi-candidate schema::

            {
              "name": "fast",
              "strategy": "priority",
              "candidates": [{"provider_id": "p", "model": "m"}],
              "updated_at": "..."
            }

        and the legacy single-candidate schema::

            {
              "name": "fast",
              "provider_id": "p",
              "model": "m",
              "updated_at": "..."
            }

        Legacy entries are promoted to a one-candidate ``priority`` role.
        Permissive about types: parses datetime from ISO string, falls
        back to now() for missing/invalid updated_at.  Invalid strategy
        values default to ``"priority"`` so corrupt files load cleanly.
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

        # Determine candidates: new format takes precedence.
        if "candidates" in d and isinstance(d["candidates"], list):
            candidates: list[Candidate] = []
            for entry in d["candidates"]:
                if isinstance(entry, dict):
                    candidates.append(Candidate.from_dict(entry))
            # Strategy from dict; default to priority if missing/invalid.
            raw_strategy = str(d.get("strategy") or DEFAULT_STRATEGY)
            strategy = raw_strategy if raw_strategy in VALID_STRATEGIES else DEFAULT_STRATEGY
        elif "provider_id" in d or "model" in d:
            # Legacy single-candidate format.
            pid = str(d.get("provider_id") or "")
            model = str(d.get("model") or "")
            candidates = [Candidate(provider_id=pid, model=model)]
            strategy = DEFAULT_STRATEGY
        else:
            candidates = []
            strategy = DEFAULT_STRATEGY

        return cls(
            name=str(d.get("name") or ""),
            strategy=strategy,
            candidates=candidates,
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

    Old single-candidate files are transparently migrated on load;
    saves always write the new multi-candidate schema.
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
        """Create or update a role with a single candidate (priority strategy).

        Convenience wrapper around :meth:`set_candidates` that accepts the
        single provider/model pair used by existing callers (API endpoint,
        migration helpers, tests).

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
        candidate = Candidate(
            provider_id=(provider_id or "").strip(),
            model=(model or "").strip(),
        )
        return self.set_candidates(name, DEFAULT_STRATEGY, [candidate])

    def set_candidates(
        self,
        name: str,
        strategy: str,
        candidates: list[Candidate],
    ) -> Role:
        """Create or update a role with an arbitrary candidate list.

        Args:
            name: Role name (e.g. "fast", "standard").
            strategy: Selection strategy; must be one of
                ``VALID_STRATEGIES`` ("priority" or "round_robin").
            candidates: Non-empty ordered list of :class:`Candidate`
                objects; duplicates (same provider_id+model) are
                rejected.

        Returns:
            The created or updated Role.

        Raises:
            RoleError: On validation failure.
        """
        self._validate_multi(name, strategy, candidates)
        with self._lock:
            role = Role(
                name=name.strip(),
                strategy=strategy,
                candidates=list(candidates),
                updated_at=datetime.now(timezone.utc),
            )
            self._roles[role.name] = role
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
            return {
                name: Role(
                    name=r.name,
                    strategy=r.strategy,
                    candidates=[
                        Candidate(provider_id=c.provider_id, model=c.model)
                        for c in r.candidates
                    ],
                    updated_at=r.updated_at,
                )
                for name, r in self._roles.items()
            }

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

    def _validate_multi(
        self,
        name: str,
        strategy: str,
        candidates: list[Candidate],
    ) -> None:
        """Validate name, strategy, and candidate list.

        Raises RoleError on the first failure with a human-readable
        message.
        """
        name = (name or "").strip()
        if not name:
            raise RoleError("name must be non-empty")

        if strategy not in VALID_STRATEGIES:
            raise RoleError(
                f"strategy {strategy!r} is not valid; "
                f"must be one of: {', '.join(sorted(VALID_STRATEGIES))}"
            )

        if not candidates:
            raise RoleError("candidates must be non-empty")

        seen: set[tuple[str, str]] = set()
        for idx, candidate in enumerate(candidates):
            key = (candidate.provider_id, candidate.model)
            if key in seen:
                raise RoleError(
                    f"duplicate candidate at index {idx}: "
                    f"provider_id={candidate.provider_id!r}, model={candidate.model!r}"
                )
            seen.add(key)
            self._validate(name, candidate.provider_id, candidate.model)

    def _validate(self, name: str, provider_id: str, model: str) -> None:
        """Validate a single provider/model pair against ProviderStore.

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


# ---------------------------------------------------------------------------
# CandidateSelector — runtime state and ordering for role dispatch
# ---------------------------------------------------------------------------

DEFAULT_USAGE_PATH = ".oompah/role_usage.json"


class CandidateSelector:
    """Runtime state and ordering for role candidate selection.

    Tracks ``last_used_at`` per ``(role_name, provider_id, model)`` triple
    in a separate state file (default: ``.oompah/role_usage.json``) so
    normal dispatches do not touch ``.oompah/roles.json``.

    Thread-safe via an in-process lock — concurrent dispatches within the
    same server process will not race on the usage state.

    Usage key format on disk::

        {
          "role_name": {
            "provider_id": {
              "model": "2026-01-01T12:00:00+00:00"
            }
          }
        }

    The nested structure lets the same provider appear with multiple models
    without ambiguity.
    """

    def __init__(self, path: str | None = None) -> None:
        """Open or create the usage-state store at ``path``.

        ``path`` defaults to ``DEFAULT_USAGE_PATH`` if not supplied.
        """
        self.path = path or DEFAULT_USAGE_PATH
        # {role_name: {provider_id: {model: last_used_at_iso_string}}}
        self._usage: dict[str, dict[str, dict[str, str]]] = {}
        self._lock = threading.Lock()
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load usage state from disk (called once at construction)."""
        if not os.path.exists(self.path):
            self._usage = {}
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._usage = data
            else:
                self._usage = {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load selector usage from %s: %s", self.path, exc
            )
            self._usage = {}

    def _save(self) -> None:
        """Persist usage state to disk (must be called while holding self._lock).

        Disk I/O errors (e.g. ENOSPC) are logged as warnings and swallowed
        so that a full disk never causes usage-tracking to crash the caller.
        Usage state is best-effort: losing a write means a round-robin role
        may repeat a candidate one extra time, which is preferable to
        crashing a worker.
        """
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self._usage, f, indent=2)
        except OSError as exc:
            logger.warning(
                "Failed to persist candidate usage state to %s: %s",
                self.path,
                exc,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_last_used(self, role_name: str, candidate: Candidate) -> str | None:
        """Return the ``last_used_at`` ISO string for a candidate, or None.

        None means the candidate has never been used for this role.
        Called while holding ``self._lock``.
        """
        return (
            self._usage
            .get(role_name, {})
            .get(candidate.provider_id, {})
            .get(candidate.model)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ordered_candidates(self, role: "Role") -> list[Candidate]:
        """Return candidates in dispatch order according to ``role.strategy``.

        ``priority``
            Return candidates in configured (saved) order.

        ``round_robin``
            Return the least-recently-used candidate first.  Candidates
            that have never been used sort before any candidate with a
            recorded ``last_used_at``.  Ties (both never used, or the
            same ``last_used_at``) are broken by configured candidate
            order so results are deterministic.

        Stale usage entries for candidates no longer in the role are
        silently ignored — they never appear in the result.
        """
        candidates = list(role.candidates)
        if not candidates:
            return candidates

        if role.strategy != "round_robin":
            # priority (and any unknown strategy): configured order
            return candidates

        # round_robin: snapshot usage under lock, then sort outside lock
        with self._lock:
            usage_snapshot = {
                c: self._get_last_used(role.name, c) for c in candidates
            }

        def sort_key(indexed: tuple[int, Candidate]) -> tuple:
            idx, candidate = indexed
            last_used = usage_snapshot[candidate]
            if last_used is None:
                # Never used → sorts before any used entry; tie-break by index
                return (0, "", idx)
            # Used → sorts after never-used; tie-break by ISO timestamp then index
            return (1, last_used, idx)

        indexed_sorted = sorted(enumerate(candidates), key=sort_key)
        return [c for _, c in indexed_sorted]

    def record_used(self, role_name: str, candidate: Candidate) -> None:
        """Record that ``candidate`` was used for the named role.

        Sets ``last_used_at`` to the current UTC time and persists the
        updated state to disk.  Safe to call from multiple threads
        concurrently.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            if role_name not in self._usage:
                self._usage[role_name] = {}
            if candidate.provider_id not in self._usage[role_name]:
                self._usage[role_name][candidate.provider_id] = {}
            self._usage[role_name][candidate.provider_id][candidate.model] = now_iso
            self._save()

    def reserve_candidate(
        self,
        role: "Role",
        exclude: "list[Candidate] | None" = None,
    ) -> "Candidate | None":
        """Atomically select the LRU eligible candidate and stamp it as reserved.

        For ``round_robin`` roles this is the atomic operation that prevents
        concurrent dispatches from all selecting the same candidate:

        1.  Under ``self._lock``, find the least-recently-used candidate
            that is not in *exclude*.
        2.  Write the current UTC time as ``last_used_at`` for that
            candidate (still under the lock).
        3.  Persist the updated state to disk before releasing the lock.
        4.  Return the selected :class:`Candidate`.

        Because the stamp is written *before* this method returns, a
        concurrent call to :meth:`reserve_candidate` or
        :meth:`ordered_candidates` will observe the updated state and
        select a different candidate.

        For non-``round_robin`` roles (``priority`` or unknown strategy)
        no stamping occurs — priority ordering is configuration-driven, not
        usage-driven, so atomic reservation is not needed.

        Args:
            role: The :class:`Role` to select a candidate from.
            exclude: Candidates already attempted (failed preflight or
                startup) for this dispatch.  They are skipped so the
                caller does not repeatedly receive the same failed
                candidate.

        Returns:
            The selected :class:`Candidate`, or ``None`` if all
            candidates are exhausted (empty role or all in *exclude*).
        """
        exclude_set: frozenset[Candidate] = frozenset(exclude or [])

        if role.strategy != "round_robin":
            # Priority (or unknown): return first eligible candidate without
            # stamping.  Ordering is configuration-driven, not usage-driven.
            for c in role.candidates:
                if c not in exclude_set:
                    return c
            return None

        with self._lock:
            eligible = [c for c in role.candidates if c not in exclude_set]
            if not eligible:
                return None

            def sort_key(indexed: tuple[int, "Candidate"]) -> tuple:
                idx, candidate = indexed
                last_used = self._get_last_used(role.name, candidate)
                if last_used is None:
                    return (0, "", idx)
                return (1, last_used, idx)

            indexed_sorted = sorted(enumerate(eligible), key=sort_key)
            selected = indexed_sorted[0][1]

            # Stamp the selected candidate immediately while still holding
            # the lock.  This makes the selection visible to any concurrent
            # reserve_candidate() / ordered_candidates() call before it
            # returns, preventing the all-first-candidate race.
            now_iso = datetime.now(timezone.utc).isoformat()
            if role.name not in self._usage:
                self._usage[role.name] = {}
            if selected.provider_id not in self._usage[role.name]:
                self._usage[role.name][selected.provider_id] = {}
            self._usage[role.name][selected.provider_id][selected.model] = now_iso
            self._save()

            return selected

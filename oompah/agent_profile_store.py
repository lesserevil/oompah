"""Agent profile storage and management.

File-backed CRUD store for AgentProfile, mirroring oompah/providers.py.
Profiles are persisted to ``.oompah/agent_profiles.json``.

On first load, when the JSON file does not exist but a non-empty list of
profiles is supplied (typically materialized from WORKFLOW.md by
``ServiceConfig.from_workflow``), the store seeds itself from that list
and writes the JSON file. This is the migration path from the legacy
WORKFLOW.md-only world to the new UI-editable JSON store.

Validation rules (enforced by ``create``/``update``):

- ``name`` must be non-empty and unique across the store.
- ``mode`` must be one of {auto, api, cli, acp}.
- ``mode`` in {auto, api} requires ``provider_id``; ``mode == "acp"`` does
  not. ``mode == "cli"`` does not require ``provider_id`` either (the
  legacy subprocess path resolves the model via the agent command).

See oompah-zlz_2-xaj for the design of this foundation. The /api/v1/agent-profiles
HTTP endpoints in oompah/server.py are the primary client.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable

from oompah.models import AgentProfile

logger = logging.getLogger(__name__)

DEFAULT_AGENT_PROFILES_PATH = ".oompah/agent_profiles.json"

VALID_MODES = ("auto", "api", "cli", "acp")
PROVIDER_REQUIRED_MODES = ("auto", "api")


class AgentProfileError(ValueError):
    """Raised when a CRUD operation fails validation.

    Subclass of ValueError so callers that already catch ValueError keep
    working; new code should catch AgentProfileError to distinguish
    profile-store errors from generic value errors.
    """


def _validate(
    profile: AgentProfile,
    *,
    existing_names: Iterable[str],
) -> None:
    """Validate profile fields and uniqueness against ``existing_names``.

    Raises AgentProfileError on the first failure with a human-readable
    message suitable for surfacing through the HTTP API as a 400.
    """
    name = (profile.name or "").strip()
    if not name:
        raise AgentProfileError("name must be non-empty")
    if name in set(existing_names):
        raise AgentProfileError(f"name {name!r} already exists")
    mode = (profile.mode or "").strip().lower()
    if mode not in VALID_MODES:
        raise AgentProfileError(
            f"mode must be one of {VALID_MODES}, got {profile.mode!r}"
        )
    if mode in PROVIDER_REQUIRED_MODES and not profile.provider_id:
        raise AgentProfileError(
            f"mode={mode!r} requires provider_id"
        )


class AgentProfileStore:
    """File-backed CRUD store for AgentProfile.

    Profiles are keyed by ``name`` (the user-facing identifier surfaced
    in the dashboard and used by ``Orchestrator._get_profile_by_name``).
    The on-disk format is a JSON array of profile dicts produced by
    ``AgentProfile.to_dict()``; loading uses ``AgentProfile.from_dict``.
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        seed_from: list[AgentProfile] | None = None,
    ):
        """Open or create the store at ``path``.

        If the file does not exist and ``seed_from`` is non-empty, the
        store materializes its initial state from ``seed_from`` and
        immediately persists it. This is the WORKFLOW.md → JSON
        migration entry point: ``ServiceConfig.from_workflow`` parses
        WORKFLOW.md, hands the parsed profile list to this constructor
        as ``seed_from``, and the store creates the JSON file on first
        boot. Subsequent boots find the JSON file and ignore
        ``seed_from``.
        """
        self.path = path or DEFAULT_AGENT_PROFILES_PATH
        self._profiles: dict[str, AgentProfile] = {}
        self._migrated_from_workflow = False
        self._loaded_from_disk = False
        self._load(seed_from=seed_from)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self, *, seed_from: list[AgentProfile] | None = None) -> None:
        if not os.path.exists(self.path):
            # First-boot migration: seed JSON from WORKFLOW.md if profiles
            # were passed in. Do nothing (empty store) otherwise.
            if seed_from:
                self._profiles = {}
                for p in seed_from:
                    if p.name and p.name not in self._profiles:
                        self._profiles[p.name] = p
                if self._profiles:
                    self._save()
                    self._migrated_from_workflow = True
                    logger.info(
                        "Migrated %d agent profile(s) from WORKFLOW.md to %s",
                        len(self._profiles), self.path,
                    )
            else:
                self._profiles = {}
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self._profiles = {}
            if isinstance(data, list):
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    p = AgentProfile.from_dict(entry)
                    if p.name and p.name not in self._profiles:
                        self._profiles[p.name] = p
            self._loaded_from_disk = True
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load agent profiles from %s: %s", self.path, exc
            )
            self._profiles = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(
                [p.to_dict() for p in self._profiles.values()],
                f,
                indent=2,
            )

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def list_all(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    def get(self, name: str) -> AgentProfile | None:
        return self._profiles.get(name)

    @property
    def is_empty(self) -> bool:
        return not self._profiles

    @property
    def migrated_from_workflow(self) -> bool:
        """True iff ``__init__`` materialized the store from WORKFLOW.md.

        Used by ``ServiceConfig.from_workflow`` to log the source
        precedence ("loaded from .oompah/agent_profiles.json" vs.
        "loaded from WORKFLOW.md and migrated to JSON").
        """
        return self._migrated_from_workflow

    @property
    def loaded_from_disk(self) -> bool:
        """True iff ``__init__`` parsed the JSON file (file existed)."""
        return self._loaded_from_disk

    # ------------------------------------------------------------------
    # Write API (validates; persists; idempotent)
    # ------------------------------------------------------------------

    def create(self, profile: AgentProfile | dict[str, Any]) -> AgentProfile:
        """Create a new profile. Validates name uniqueness + mode rules.

        Accepts either an AgentProfile dataclass instance or a dict
        (which is run through ``AgentProfile.from_dict``).
        """
        if isinstance(profile, dict):
            profile = AgentProfile.from_dict(profile)
        _validate(profile, existing_names=self._profiles.keys())
        self._profiles[profile.name] = profile
        self._save()
        return profile

    def update(self, _profile_name: str, /, **fields: Any) -> AgentProfile | None:
        """Update a profile in place; returns None if not found.

        Validates the resulting profile against the same rules as
        ``create`` (renaming to a duplicate name is rejected; mode is
        re-checked for provider_id presence). The original is left
        untouched if validation fails.

        The lookup key is positional-only (``_profile_name``) so callers
        can pass ``name="new-name"`` as a kwarg to rename the profile
        without colliding with the lookup argument.
        """
        existing = self._profiles.get(_profile_name)
        if existing is None:
            return None
        # Build a candidate by copying current values then overlaying
        # the requested fields, so partial PATCHes work.
        candidate_dict = existing.to_dict()
        for key, value in fields.items():
            if key == "name" and value is not None:
                candidate_dict["name"] = str(value)
                continue
            candidate_dict[key] = value
        candidate = AgentProfile.from_dict(candidate_dict)
        # Uniqueness check skips the original entry's own name so the
        # caller can no-op rename to the same value.
        existing_names = [
            n for n in self._profiles.keys() if n != _profile_name
        ]
        _validate(candidate, existing_names=existing_names)
        # Apply: drop the old key if rename, set the new entry.
        if candidate.name != _profile_name:
            del self._profiles[_profile_name]
        self._profiles[candidate.name] = candidate
        self._save()
        return candidate

    def delete(self, name: str) -> bool:
        """Delete a profile by name. Returns True iff something was removed."""
        if name in self._profiles:
            del self._profiles[name]
            self._save()
            return True
        return False

    def replace_all(self, profiles: list[AgentProfile]) -> None:
        """Replace the entire store with ``profiles`` and persist.

        Used by callers that want to atomically apply a full snapshot
        (e.g. ``Orchestrator.reload_config`` after a workflow reload
        when the JSON store is the source of truth, or admin reset).
        Validates all profiles before persisting.
        """
        new_map: dict[str, AgentProfile] = {}
        for p in profiles:
            _validate(p, existing_names=new_map.keys())
            new_map[p.name] = p
        self._profiles = new_map
        self._save()

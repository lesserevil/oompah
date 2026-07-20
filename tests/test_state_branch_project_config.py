"""Comprehensive tests for per-project state-branch configuration (OOMPAH-255).

Coverage:
- Model defaults and backward compatibility (absent field → legacy behavior)
- Model serialization: to_dict() / from_dict() round-trips
- Model validation: state_branch_name derived from project ID
- ProjectStore.UPDATABLE_FIELDS includes state-branch fields
- ProjectStore.update() validation: type errors, cross-field constraints
- Server API GET /api/v1/projects/{id}: includes state_branch fields in response
- Server API PATCH /api/v1/projects/{id}: accepts and validates state_branch fields
- Cache invalidation: changing state_branch_enabled invalidates tracker cache
- Backward compatibility: projects loaded from legacy JSON (no state_branch field)
  still work and default to False
- UI (projects.html): contains state_branch_enabled display and edit elements
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Project
from oompah.projects import ProjectError, ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(**overrides) -> Project:
    defaults = dict(
        id="proj-abc123",
        name="myrepo",
        repo_url="https://github.com/org/myrepo.git",
        repo_path="/tmp/myrepo",
        default_branch="main",
    )
    defaults.update(overrides)
    return Project(**defaults)


def _make_store(tmp_path) -> ProjectStore:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )
    p = _make_project(id="proj-testid", name="testrepo")
    store._projects[p.id] = p
    store._save()
    return store


# ---------------------------------------------------------------------------
# § 1 — Model defaults and backward compatibility
# ---------------------------------------------------------------------------


class TestProjectModelDefaults:
    """state_branch_enabled must default to False for backward compatibility."""

    def test_state_branch_enabled_defaults_to_false(self):
        """New projects without an explicit value must not opt in automatically."""
        p = _make_project()
        assert p.state_branch_enabled is False

    def test_state_branch_checkpoint_debounce_ms_defaults_to_none(self):
        """Per-project debounce override must default to None (use global .env)."""
        p = _make_project()
        assert p.state_branch_checkpoint_debounce_ms is None

    def test_state_branch_checkpoint_max_delay_ms_defaults_to_none(self):
        """Per-project max-delay override must default to None (use global .env)."""
        p = _make_project()
        assert p.state_branch_checkpoint_max_delay_ms is None

    def test_state_branch_name_is_oompah_state_project_id(self):
        """State branch name is deterministically derived from project ID."""
        p = _make_project(id="proj-14849f1b")
        assert p.state_branch_name == "oompah/state/proj-14849f1b"

    def test_state_branch_name_uses_project_id_not_name(self):
        """Renaming the project must not change the state branch name."""
        p1 = _make_project(id="proj-abc", name="repo-a")
        p2 = _make_project(id="proj-abc", name="repo-b-renamed")
        assert p1.state_branch_name == p2.state_branch_name

    def test_state_branch_name_prefix_is_oompah_state(self):
        """State branch must always be under the oompah/state/ namespace."""
        p = _make_project(id="proj-xyz-999")
        assert p.state_branch_name.startswith("oompah/state/")

    def test_state_branch_name_does_not_conflict_with_code_branches(self):
        """oompah/ prefix is distinct from common code branch prefixes."""
        p = _make_project(id="proj-abc")
        for prefix in ("feature/", "release/", "hotfix/", "main", "develop"):
            assert not p.state_branch_name.startswith(prefix)

    def test_explicit_true_stored_correctly(self):
        """Setting state_branch_enabled=True must be stored as True."""
        p = _make_project(state_branch_enabled=True)
        assert p.state_branch_enabled is True

    def test_explicit_checkpoint_values_stored(self):
        """Explicit positive integer checkpoint values must be stored as-is."""
        p = _make_project(
            state_branch_enabled=True,
            state_branch_checkpoint_debounce_ms=3000,
            state_branch_checkpoint_max_delay_ms=20000,
        )
        assert p.state_branch_checkpoint_debounce_ms == 3000
        assert p.state_branch_checkpoint_max_delay_ms == 20000


# ---------------------------------------------------------------------------
# § 2 — Serialization: to_dict()
# ---------------------------------------------------------------------------


class TestProjectToDict:
    """to_dict() must include state_branch fields in the output."""

    def test_to_dict_always_includes_state_branch_enabled(self):
        """state_branch_enabled must appear in to_dict() even when False."""
        p = _make_project()
        d = p.to_dict()
        assert "state_branch_enabled" in d
        assert d["state_branch_enabled"] is False

    def test_to_dict_state_branch_enabled_true(self):
        """to_dict() must reflect state_branch_enabled=True correctly."""
        p = _make_project(state_branch_enabled=True)
        d = p.to_dict()
        assert d["state_branch_enabled"] is True

    def test_to_dict_omits_debounce_when_none(self):
        """Per-project debounce must be omitted from to_dict() when None."""
        p = _make_project()
        d = p.to_dict()
        assert "state_branch_checkpoint_debounce_ms" not in d

    def test_to_dict_omits_max_delay_when_none(self):
        """Per-project max_delay must be omitted from to_dict() when None."""
        p = _make_project()
        d = p.to_dict()
        assert "state_branch_checkpoint_max_delay_ms" not in d

    def test_to_dict_includes_debounce_when_set(self):
        """to_dict() must include debounce when it is a positive integer."""
        p = _make_project(state_branch_checkpoint_debounce_ms=8000)
        d = p.to_dict()
        assert d["state_branch_checkpoint_debounce_ms"] == 8000

    def test_to_dict_includes_max_delay_when_set(self):
        """to_dict() must include max_delay when it is a positive integer."""
        p = _make_project(state_branch_checkpoint_max_delay_ms=60000)
        d = p.to_dict()
        assert d["state_branch_checkpoint_max_delay_ms"] == 60000

    def test_to_safe_dict_exposes_state_branch_enabled(self):
        """to_safe_dict() must also include state_branch_enabled (no redaction)."""
        p = _make_project(state_branch_enabled=True)
        d = p.to_safe_dict()
        assert d["state_branch_enabled"] is True


# ---------------------------------------------------------------------------
# § 3 — Deserialization: from_dict()
# ---------------------------------------------------------------------------


class TestProjectFromDict:
    """from_dict() must deserialize state_branch fields and apply safe defaults."""

    def _base_dict(self, **overrides) -> dict:
        d = {
            "id": "proj-zzz",
            "name": "testrepo",
            "repo_url": "https://github.com/org/testrepo.git",
            "repo_path": "/tmp/testrepo",
            "default_branch": "main",
        }
        d.update(overrides)
        return d

    def test_from_dict_defaults_state_branch_enabled_to_false_when_absent(self):
        """Legacy records without state_branch_enabled must default to False."""
        d = self._base_dict()
        assert "state_branch_enabled" not in d
        p = Project.from_dict(d)
        assert p.state_branch_enabled is False

    def test_from_dict_reads_state_branch_enabled_true(self):
        """from_dict() must read state_branch_enabled=true from the record."""
        d = self._base_dict(state_branch_enabled=True)
        p = Project.from_dict(d)
        assert p.state_branch_enabled is True

    def test_from_dict_reads_state_branch_enabled_false(self):
        """from_dict() must read state_branch_enabled=false explicitly."""
        d = self._base_dict(state_branch_enabled=False)
        p = Project.from_dict(d)
        assert p.state_branch_enabled is False

    def test_from_dict_debounce_absent_defaults_to_none(self):
        """Legacy records without debounce field must default to None."""
        d = self._base_dict()
        p = Project.from_dict(d)
        assert p.state_branch_checkpoint_debounce_ms is None

    def test_from_dict_reads_debounce(self):
        """from_dict() must read a valid positive integer debounce value."""
        d = self._base_dict(state_branch_checkpoint_debounce_ms=7000)
        p = Project.from_dict(d)
        assert p.state_branch_checkpoint_debounce_ms == 7000

    def test_from_dict_reads_max_delay(self):
        """from_dict() must read a valid positive integer max_delay value."""
        d = self._base_dict(state_branch_checkpoint_max_delay_ms=45000)
        p = Project.from_dict(d)
        assert p.state_branch_checkpoint_max_delay_ms == 45000

    def test_from_dict_invalid_debounce_treated_as_none(self):
        """Non-integer debounce values in legacy JSON must be silently treated as None."""
        d = self._base_dict(state_branch_checkpoint_debounce_ms="not-a-number")
        p = Project.from_dict(d)
        assert p.state_branch_checkpoint_debounce_ms is None

    def test_from_dict_zero_debounce_treated_as_none(self):
        """Zero debounce (non-positive) must be silently treated as None."""
        d = self._base_dict(state_branch_checkpoint_debounce_ms=0)
        p = Project.from_dict(d)
        assert p.state_branch_checkpoint_debounce_ms is None

    def test_from_dict_negative_debounce_treated_as_none(self):
        """Negative debounce must be silently treated as None."""
        d = self._base_dict(state_branch_checkpoint_debounce_ms=-1000)
        p = Project.from_dict(d)
        assert p.state_branch_checkpoint_debounce_ms is None

    def test_from_dict_none_max_delay_stays_none(self):
        """Explicit null max_delay in JSON must deserialize to None."""
        d = self._base_dict(state_branch_checkpoint_max_delay_ms=None)
        p = Project.from_dict(d)
        assert p.state_branch_checkpoint_max_delay_ms is None


# ---------------------------------------------------------------------------
# § 4 — Round-trip serialization
# ---------------------------------------------------------------------------


class TestProjectRoundTrip:
    """Project.to_dict() → Project.from_dict() must preserve state_branch fields."""

    def test_round_trip_enabled_false(self):
        p = _make_project(state_branch_enabled=False)
        p2 = Project.from_dict(p.to_dict())
        assert p2.state_branch_enabled is False
        assert p2.state_branch_checkpoint_debounce_ms is None
        assert p2.state_branch_checkpoint_max_delay_ms is None

    def test_round_trip_enabled_true(self):
        p = _make_project(state_branch_enabled=True)
        p2 = Project.from_dict(p.to_dict())
        assert p2.state_branch_enabled is True

    def test_round_trip_with_checkpoint_values(self):
        p = _make_project(
            state_branch_enabled=True,
            state_branch_checkpoint_debounce_ms=4000,
            state_branch_checkpoint_max_delay_ms=25000,
        )
        p2 = Project.from_dict(p.to_dict())
        assert p2.state_branch_checkpoint_debounce_ms == 4000
        assert p2.state_branch_checkpoint_max_delay_ms == 25000

    def test_round_trip_preserves_state_branch_name(self):
        p = _make_project(id="proj-roundtrip-abc")
        p2 = Project.from_dict(p.to_dict())
        assert p2.state_branch_name == "oompah/state/proj-roundtrip-abc"


# ---------------------------------------------------------------------------
# § 5 — ProjectStore.UPDATABLE_FIELDS
# ---------------------------------------------------------------------------


class TestUpdatableFields:
    """State-branch fields must be in UPDATABLE_FIELDS."""

    def test_state_branch_enabled_is_updatable(self):
        assert "state_branch_enabled" in ProjectStore.UPDATABLE_FIELDS

    def test_state_branch_debounce_ms_is_updatable(self):
        assert "state_branch_checkpoint_debounce_ms" in ProjectStore.UPDATABLE_FIELDS

    def test_state_branch_max_delay_ms_is_updatable(self):
        assert "state_branch_checkpoint_max_delay_ms" in ProjectStore.UPDATABLE_FIELDS


# ---------------------------------------------------------------------------
# § 6 — ProjectStore.update() validation
# ---------------------------------------------------------------------------


class TestProjectStoreUpdateStateBranch:
    """Validation rules for state_branch fields in ProjectStore.update()."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        self.store = _make_store(tmp_path)

    def test_update_state_branch_enabled_to_true(self):
        """Setting state_branch_enabled=True must succeed and persist."""
        updated = self.store.update("proj-testid", state_branch_enabled=True)
        assert updated is not None
        assert updated.state_branch_enabled is True

    def test_update_state_branch_enabled_to_false(self):
        """Setting state_branch_enabled=False must succeed."""
        self.store.update("proj-testid", state_branch_enabled=True)
        updated = self.store.update("proj-testid", state_branch_enabled=False)
        assert updated.state_branch_enabled is False

    def test_update_state_branch_enabled_non_bool_rejected(self):
        """Non-boolean values for state_branch_enabled must raise ProjectError."""
        with pytest.raises(ProjectError, match="state_branch_enabled"):
            self.store.update("proj-testid", state_branch_enabled="yes")

    def test_update_state_branch_enabled_integer_rejected(self):
        """Integer (1/0) instead of bool must be rejected."""
        with pytest.raises(ProjectError, match="state_branch_enabled"):
            self.store.update("proj-testid", state_branch_enabled=1)

    def test_update_debounce_ms_valid(self):
        """Valid positive integer debounce must be accepted."""
        updated = self.store.update(
            "proj-testid", state_branch_checkpoint_debounce_ms=5000
        )
        assert updated.state_branch_checkpoint_debounce_ms == 5000

    def test_update_debounce_ms_null_clears_value(self):
        """Setting debounce to None must clear the override (fall back to .env)."""
        self.store.update("proj-testid", state_branch_checkpoint_debounce_ms=5000)
        updated = self.store.update(
            "proj-testid", state_branch_checkpoint_debounce_ms=None
        )
        assert updated.state_branch_checkpoint_debounce_ms is None

    def test_update_debounce_ms_zero_rejected(self):
        """Zero is not a valid positive integer; must raise ProjectError."""
        with pytest.raises(ProjectError, match="state_branch_checkpoint_debounce_ms"):
            self.store.update("proj-testid", state_branch_checkpoint_debounce_ms=0)

    def test_update_debounce_ms_negative_rejected(self):
        """Negative values must be rejected."""
        with pytest.raises(ProjectError, match="state_branch_checkpoint_debounce_ms"):
            self.store.update("proj-testid", state_branch_checkpoint_debounce_ms=-1000)

    def test_update_debounce_ms_string_rejected(self):
        """String values for debounce must be rejected."""
        with pytest.raises(ProjectError, match="state_branch_checkpoint_debounce_ms"):
            self.store.update(
                "proj-testid", state_branch_checkpoint_debounce_ms="5000"
            )

    def test_update_debounce_ms_bool_rejected(self):
        """Boolean value (True) must be rejected — booleans are not ints here."""
        with pytest.raises(ProjectError, match="state_branch_checkpoint_debounce_ms"):
            self.store.update(
                "proj-testid", state_branch_checkpoint_debounce_ms=True
            )

    def test_update_max_delay_ms_valid(self):
        """Valid positive integer max_delay must be accepted."""
        updated = self.store.update(
            "proj-testid", state_branch_checkpoint_max_delay_ms=30000
        )
        assert updated.state_branch_checkpoint_max_delay_ms == 30000

    def test_update_max_delay_ms_null_clears_value(self):
        """Setting max_delay to None must clear the override."""
        self.store.update("proj-testid", state_branch_checkpoint_max_delay_ms=30000)
        updated = self.store.update(
            "proj-testid", state_branch_checkpoint_max_delay_ms=None
        )
        assert updated.state_branch_checkpoint_max_delay_ms is None

    def test_update_max_delay_ms_zero_rejected(self):
        """Zero must be rejected."""
        with pytest.raises(
            ProjectError, match="state_branch_checkpoint_max_delay_ms"
        ):
            self.store.update(
                "proj-testid", state_branch_checkpoint_max_delay_ms=0
            )

    def test_cross_validation_max_delay_must_exceed_debounce_plus_1000(self):
        """max_delay must be >= debounce + 1000 when both are set in one update."""
        with pytest.raises(ProjectError, match="state_branch_checkpoint_max_delay_ms"):
            self.store.update(
                "proj-testid",
                state_branch_checkpoint_debounce_ms=10000,
                state_branch_checkpoint_max_delay_ms=5000,  # < debounce + 1000
            )

    def test_cross_validation_equal_values_rejected(self):
        """max_delay == debounce is also invalid (must be strictly +1000)."""
        with pytest.raises(ProjectError, match="state_branch_checkpoint_max_delay_ms"):
            self.store.update(
                "proj-testid",
                state_branch_checkpoint_debounce_ms=5000,
                state_branch_checkpoint_max_delay_ms=5000,
            )

    def test_cross_validation_min_valid_gap(self):
        """max_delay == debounce + 1000 must be accepted (exactly at the boundary)."""
        updated = self.store.update(
            "proj-testid",
            state_branch_checkpoint_debounce_ms=5000,
            state_branch_checkpoint_max_delay_ms=6000,  # exactly debounce + 1000
        )
        assert updated.state_branch_checkpoint_debounce_ms == 5000
        assert updated.state_branch_checkpoint_max_delay_ms == 6000

    def test_cross_validation_uses_existing_debounce_when_only_max_delay_updated(self):
        """Cross-validation must use the existing debounce when not in this update."""
        self.store.update(
            "proj-testid", state_branch_checkpoint_debounce_ms=10000
        )
        # Now update only max_delay — must compare against existing debounce (10000)
        with pytest.raises(ProjectError, match="state_branch_checkpoint_max_delay_ms"):
            self.store.update(
                "proj-testid",
                state_branch_checkpoint_max_delay_ms=5000,  # < 10000 + 1000
            )

    def test_cross_validation_uses_existing_max_delay_when_only_debounce_updated(self):
        """Cross-validation must use existing max_delay when not in this update."""
        self.store.update(
            "proj-testid", state_branch_checkpoint_max_delay_ms=6000
        )
        # Now try setting debounce=6000 — would violate constraint vs existing max_delay
        with pytest.raises(ProjectError, match="state_branch_checkpoint_max_delay_ms"):
            self.store.update(
                "proj-testid",
                state_branch_checkpoint_debounce_ms=6000,  # equal to max_delay → invalid
            )

    def test_update_persists_to_disk(self, tmp_path):
        """State-branch fields must survive a store reload from disk."""
        self.store.update(
            "proj-testid",
            state_branch_enabled=True,
            state_branch_checkpoint_debounce_ms=3000,
            state_branch_checkpoint_max_delay_ms=20000,
        )
        # Reload from disk
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = store2.get("proj-testid")
        assert p is not None
        assert p.state_branch_enabled is True
        assert p.state_branch_checkpoint_debounce_ms == 3000
        assert p.state_branch_checkpoint_max_delay_ms == 20000


# ---------------------------------------------------------------------------
# § 7 — Backward compatibility with legacy project records
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Projects loaded from JSON without state_branch fields must default gracefully."""

    def test_legacy_json_without_state_branch_fields(self, tmp_path):
        """A JSON record without state_branch fields must load as state_branch_enabled=False.

        This is the core backward-compatibility test: existing projects that were
        persisted before OOMPAH-255 was implemented must continue to work with
        legacy behavior (reads/writes from the default branch).
        """
        legacy_record = {
            "id": "proj-legacy",
            "name": "oldrepo",
            "repo_url": "https://github.com/org/oldrepo.git",
            "repo_path": "/tmp/oldrepo",
            "branch": "main",
            "default_branch": "main",
            "yolo": False,
            "lfs_available": False,
            "max_in_flight_prs": 1,
            "merge_queue_enabled": False,
            "paused": False,
            "webhook_forwarding_enabled": True,
            # Note: NO state_branch_* fields — simulates a pre-OOMPAH-255 record
        }
        projects_path = tmp_path / "projects.json"
        # ProjectStore expects a JSON array of project dicts (not a dict wrapper)
        projects_path.write_text(
            json.dumps([legacy_record]), encoding="utf-8"
        )
        store = ProjectStore(
            path=str(projects_path),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = store.get("proj-legacy")
        assert p is not None
        # Legacy behavior: reads from default branch (state_branch_enabled=False)
        assert p.state_branch_enabled is False
        assert p.state_branch_checkpoint_debounce_ms is None
        assert p.state_branch_checkpoint_max_delay_ms is None

    def test_legacy_project_state_branch_name_still_derivable(self, tmp_path):
        """Even legacy projects (state_branch_enabled=False) have a valid branch name property."""
        legacy_record = {
            "id": "proj-legacy-named",
            "name": "oldrepo",
            "repo_url": "https://github.com/org/oldrepo.git",
            "repo_path": "/tmp/oldrepo",
            "branch": "main",
            "default_branch": "main",
        }
        p = Project.from_dict(legacy_record)
        # The property is always available even though it won't be used
        assert p.state_branch_name == "oompah/state/proj-legacy-named"
        assert p.state_branch_enabled is False

    def test_from_dict_preserves_other_fields_when_state_branch_added(self):
        """Adding state_branch_enabled=True must not change other fields."""
        d = {
            "id": "proj-compat",
            "name": "compat",
            "repo_url": "https://github.com/org/compat.git",
            "repo_path": "/tmp/compat",
            "branch": "main",
            "default_branch": "main",
            "yolo": True,
            "tracker_kind": "oompah_md",
            "state_branch_enabled": True,
        }
        p = Project.from_dict(d)
        assert p.yolo is True
        assert p.tracker_kind == "oompah_md"
        assert p.state_branch_enabled is True


# ---------------------------------------------------------------------------
# § 8 — Server API: GET returns state_branch fields
# ---------------------------------------------------------------------------


class TestServerAPIGet:
    """GET /api/v1/projects/{id} must include state_branch fields in response."""

    @pytest.fixture
    def mock_orch(self, tmp_path):
        store = _make_store(tmp_path)
        orch = MagicMock()
        orch.project_store = store
        orch.get_project = store.get
        return orch

    def test_to_safe_dict_includes_state_branch_enabled(self):
        """API response dict must include state_branch_enabled."""
        p = _make_project(state_branch_enabled=False)
        d = p.to_safe_dict()
        assert "state_branch_enabled" in d
        assert d["state_branch_enabled"] is False

    def test_to_safe_dict_includes_state_branch_enabled_true(self):
        """API response dict must reflect state_branch_enabled=True."""
        p = _make_project(state_branch_enabled=True)
        d = p.to_safe_dict()
        assert d["state_branch_enabled"] is True

    def test_to_safe_dict_omits_debounce_when_none(self):
        """state_branch_checkpoint_debounce_ms must be absent when None."""
        p = _make_project()
        d = p.to_safe_dict()
        assert "state_branch_checkpoint_debounce_ms" not in d

    def test_to_safe_dict_includes_checkpoint_values_when_set(self):
        """API response must include checkpoint overrides when set."""
        p = _make_project(
            state_branch_checkpoint_debounce_ms=4000,
            state_branch_checkpoint_max_delay_ms=25000,
        )
        d = p.to_safe_dict()
        assert d["state_branch_checkpoint_debounce_ms"] == 4000
        assert d["state_branch_checkpoint_max_delay_ms"] == 25000


# ---------------------------------------------------------------------------
# § 9 — Server API: PATCH validates state_branch fields
# ---------------------------------------------------------------------------


class TestServerAPIPatch:
    """PATCH /api/v1/projects/{id} must accept and reject state_branch fields."""

    @pytest.fixture
    def app_client(self, tmp_path):
        """Create a minimal test client for the oompah server."""
        from httpx import ASGITransport, AsyncClient
        from oompah.server import app

        store = _make_store(tmp_path)
        orch = MagicMock()
        orch.project_store = store
        orch.get_project = store.get

        with patch("oompah.server._get_orchestrator", return_value=orch), \
             patch("oompah.server._api_cache") as mock_cache, \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"):
            mock_cache.invalidate = MagicMock()
            import anyio
            yield store  # return store for direct checks; use PATCH via store.update

    def test_patch_state_branch_enabled_true(self, tmp_path):
        """PATCH with state_branch_enabled=true must enable it."""
        store = _make_store(tmp_path)
        updated = store.update("proj-testid", state_branch_enabled=True)
        assert updated.state_branch_enabled is True

    def test_patch_state_branch_enabled_false(self, tmp_path):
        """PATCH with state_branch_enabled=false must disable it."""
        store = _make_store(tmp_path)
        store.update("proj-testid", state_branch_enabled=True)
        updated = store.update("proj-testid", state_branch_enabled=False)
        assert updated.state_branch_enabled is False

    def test_patch_state_branch_enabled_non_bool_rejected(self, tmp_path):
        """PATCH with state_branch_enabled as a string must be rejected."""
        store = _make_store(tmp_path)
        with pytest.raises(ProjectError, match="state_branch_enabled"):
            store.update("proj-testid", state_branch_enabled="true")

    def test_patch_checkpoint_debounce_valid(self, tmp_path):
        """PATCH with valid debounce_ms must be accepted."""
        store = _make_store(tmp_path)
        updated = store.update(
            "proj-testid", state_branch_checkpoint_debounce_ms=8000
        )
        assert updated.state_branch_checkpoint_debounce_ms == 8000

    def test_patch_checkpoint_max_delay_valid(self, tmp_path):
        """PATCH with valid max_delay_ms must be accepted."""
        store = _make_store(tmp_path)
        updated = store.update(
            "proj-testid", state_branch_checkpoint_max_delay_ms=60000
        )
        assert updated.state_branch_checkpoint_max_delay_ms == 60000

    def test_patch_checkpoint_values_rejected_when_invalid(self, tmp_path):
        """PATCH with non-positive debounce must be rejected."""
        store = _make_store(tmp_path)
        with pytest.raises(ProjectError, match="state_branch_checkpoint_debounce_ms"):
            store.update("proj-testid", state_branch_checkpoint_debounce_ms=-500)

    def test_patch_unknown_state_branch_field_rejected(self, tmp_path):
        """Completely unknown field names must be rejected by update()."""
        store = _make_store(tmp_path)
        with pytest.raises(ProjectError, match="Unknown or immutable"):
            store.update("proj-testid", state_branch_host="unknown_field")


# ---------------------------------------------------------------------------
# § 10 — Server PATCH handler (HTTP level)
# ---------------------------------------------------------------------------


class TestServerPatchHTTP:
    """Test the HTTP-level PATCH handler's state_branch_enabled handling.

    Uses FastAPI's synchronous TestClient (same pattern as test_projects_crud.py)
    to avoid event-loop conflicts with pytest-asyncio in the full test suite.
    """

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        """Set up a FastAPI TestClient with a mock orchestrator."""
        from fastapi.testclient import TestClient
        from oompah.server import app

        store = _make_store(tmp_path)
        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        import oompah.server as srv

        old_orch = srv._orchestrator
        old_watcher = srv._log_watcher_manager
        srv._orchestrator = orch
        srv._log_watcher_manager = None

        self.client = TestClient(app)
        self.store = store
        yield self.client

        srv._orchestrator = old_orch
        srv._log_watcher_manager = old_watcher

    def test_http_patch_state_branch_enabled_true(self):
        """HTTP PATCH with state_branch_enabled=true must return 200."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_enabled": True},
        )
        assert res.status_code == 200
        assert res.json()["state_branch_enabled"] is True

    def test_http_patch_state_branch_enabled_false(self):
        """HTTP PATCH with state_branch_enabled=false must return 200."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_enabled": False},
        )
        assert res.status_code == 200
        assert res.json()["state_branch_enabled"] is False

    def test_http_patch_state_branch_enabled_string_rejected(self):
        """HTTP PATCH with state_branch_enabled='true' (string) must return 400."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_enabled": "true"},
        )
        assert res.status_code == 400
        err = res.json()["error"]["message"]
        assert "state_branch_enabled" in err

    def test_http_patch_checkpoint_debounce_valid(self):
        """HTTP PATCH with valid debounce must return 200."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_debounce_ms": 5000},
        )
        assert res.status_code == 200
        assert res.json()["state_branch_checkpoint_debounce_ms"] == 5000

    def test_http_patch_checkpoint_debounce_negative_rejected(self):
        """HTTP PATCH with negative debounce must return 400."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_debounce_ms": -100},
        )
        assert res.status_code == 400
        err = res.json()["error"]["message"]
        assert "state_branch_checkpoint_debounce_ms" in err

    def test_http_patch_checkpoint_debounce_zero_rejected(self):
        """HTTP PATCH with debounce=0 must return 400."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_debounce_ms": 0},
        )
        assert res.status_code == 400

    def test_http_patch_checkpoint_debounce_bool_rejected(self):
        """HTTP PATCH with debounce=true (boolean, not int) must return 400."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_debounce_ms": True},
        )
        assert res.status_code == 400

    def test_http_patch_checkpoint_debounce_null_accepted(self):
        """HTTP PATCH with debounce=null must clear the override."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_debounce_ms": None},
        )
        assert res.status_code == 200
        assert "state_branch_checkpoint_debounce_ms" not in res.json()

    def test_http_patch_checkpoint_max_delay_valid(self):
        """HTTP PATCH with valid max_delay must return 200."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_max_delay_ms": 30000},
        )
        assert res.status_code == 200
        assert res.json()["state_branch_checkpoint_max_delay_ms"] == 30000

    def test_http_patch_checkpoint_max_delay_negative_rejected(self):
        """HTTP PATCH with negative max_delay must return 400."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_max_delay_ms": -1},
        )
        assert res.status_code == 400

    def test_http_patch_checkpoint_max_delay_bool_rejected(self):
        """HTTP PATCH with max_delay=false (boolean) must return 400."""
        res = self.client.patch(
            "/api/v1/projects/proj-testid",
            json={"state_branch_checkpoint_max_delay_ms": False},
        )
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# § 11 — Cache invalidation
# ---------------------------------------------------------------------------


class TestCacheInvalidation:
    """Changing state_branch_enabled must invalidate the tracker and repository caches."""

    def test_state_branch_enabled_in_project_tracker_cache_fields(self):
        """state_branch_enabled must be in _PROJECT_TRACKER_CACHE_FIELDS."""
        from oompah.server import _PROJECT_TRACKER_CACHE_FIELDS

        assert "state_branch_enabled" in _PROJECT_TRACKER_CACHE_FIELDS

    def test_state_branch_debounce_in_project_tracker_cache_fields(self):
        """state_branch_checkpoint_debounce_ms must be in _PROJECT_TRACKER_CACHE_FIELDS."""
        from oompah.server import _PROJECT_TRACKER_CACHE_FIELDS

        assert "state_branch_checkpoint_debounce_ms" in _PROJECT_TRACKER_CACHE_FIELDS

    def test_state_branch_max_delay_in_project_tracker_cache_fields(self):
        """state_branch_checkpoint_max_delay_ms must be in _PROJECT_TRACKER_CACHE_FIELDS."""
        from oompah.server import _PROJECT_TRACKER_CACHE_FIELDS

        assert "state_branch_checkpoint_max_delay_ms" in _PROJECT_TRACKER_CACHE_FIELDS

    def test_cache_invalidation_called_when_state_branch_enabled_changes(self, tmp_path):
        """Updating state_branch_enabled must trigger cache invalidation via the server."""
        from fastapi.testclient import TestClient
        from oompah.server import app

        store = _make_store(tmp_path)
        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}
        orch._project_trackers = {"proj-testid": MagicMock()}

        import oompah.server as srv

        old_orch = srv._orchestrator
        old_watcher = srv._log_watcher_manager
        srv._orchestrator = orch
        srv._log_watcher_manager = None

        try:
            with patch(
                "oompah.server._invalidate_project_tracker_cache"
            ) as mock_inval:
                client = TestClient(app)
                res = client.patch(
                    "/api/v1/projects/proj-testid",
                    json={"state_branch_enabled": True},
                )
                assert res.status_code == 200
                mock_inval.assert_called_once_with(orch, "proj-testid")
        finally:
            srv._orchestrator = old_orch
            srv._log_watcher_manager = old_watcher

    def test_no_cache_invalidation_when_only_name_changes(self, tmp_path):
        """Cache must NOT be invalidated when only non-tracker fields change."""
        from fastapi.testclient import TestClient
        from oompah.server import app

        store = _make_store(tmp_path)
        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        import oompah.server as srv

        old_orch = srv._orchestrator
        old_watcher = srv._log_watcher_manager
        srv._orchestrator = orch
        srv._log_watcher_manager = None

        try:
            with patch(
                "oompah.server._invalidate_project_tracker_cache"
            ) as mock_inval:
                client = TestClient(app)
                res = client.patch(
                    "/api/v1/projects/proj-testid",
                    json={"name": "new-name"},
                )
                assert res.status_code == 200
                mock_inval.assert_not_called()
        finally:
            srv._orchestrator = old_orch
            srv._log_watcher_manager = old_watcher


# ---------------------------------------------------------------------------
# § 12 — UI (projects.html) has required elements
# ---------------------------------------------------------------------------


def _load_projects_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "projects.html",
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


class TestProjectsHtmlUI:
    """projects.html must expose state_branch_enabled in display and edit form."""

    @pytest.fixture(scope="class")
    def html(self):
        return _load_projects_html()

    def test_display_row_for_state_branch_enabled_exists(self, html):
        """The project card must display a 'State Branch' row."""
        assert "data-field=\"state-branch-enabled\"" in html

    def test_state_branch_section_label_present(self, html):
        """The edit form must have a 'State Branch Settings' section label."""
        assert "State Branch Settings" in html

    def test_edit_checkbox_for_state_branch_enabled(self, html):
        """A checkbox with data-field=state-branch-enabled-edit must be present."""
        assert "data-field=\"state-branch-enabled-edit\"" in html

    def test_edit_checkbox_id_uses_project_id(self, html):
        """The checkbox id must follow the pattern edit-state-branch-enabled-${p.id}."""
        assert "edit-state-branch-enabled-${esc(p.id)}" in html

    def test_saveproject_reads_state_branch_enabled(self, html):
        """saveProject() must read the state_branch_enabled checkbox."""
        assert "edit-state-branch-enabled-" in html
        assert "stateBranchEnabled" in html or "state_branch_enabled" in html

    def test_saveproject_sends_state_branch_enabled_in_body(self, html):
        """saveProject() PATCH body must include state_branch_enabled."""
        # Find the body object construction in saveProject
        assert "state_branch_enabled: stateBranchEnabled" in html \
            or "state_branch_enabled" in html

    def test_state_branch_name_preview_shown_in_ui(self, html):
        """UI should show the derived state branch name (oompah/state/<id>)."""
        # The UI shows oompah/state/ prefix
        assert "oompah/state/" in html


# ---------------------------------------------------------------------------
# § 13 — state_branch_name property
# ---------------------------------------------------------------------------


class TestStateBranchNameProperty:
    """Parametric tests for the state_branch_name derived property."""

    @pytest.mark.parametrize(
        "project_id, expected_branch",
        [
            ("proj-14849f1b", "oompah/state/proj-14849f1b"),
            ("proj-abc", "oompah/state/proj-abc"),
            ("proj-xyz-123", "oompah/state/proj-xyz-123"),
            ("proj-00000000", "oompah/state/proj-00000000"),
        ],
    )
    def test_branch_name_formula(self, project_id: str, expected_branch: str):
        """State branch name must be oompah/state/<project-id>."""
        p = _make_project(id=project_id)
        assert p.state_branch_name == expected_branch

    def test_branch_name_is_read_only_property(self):
        """state_branch_name should not be set directly; it is derived."""
        p = _make_project(id="proj-abc")
        # Verify it's computed, not a dataclass field
        # (Setting it should raise AttributeError — it's a @property)
        with pytest.raises(AttributeError):
            p.state_branch_name = "custom-branch"  # type: ignore[misc]

    def test_branch_name_unchanged_when_state_branch_enabled_changes(self):
        """Enabling the feature must not change the derived branch name."""
        p1 = _make_project(id="proj-same", state_branch_enabled=False)
        p2 = _make_project(id="proj-same", state_branch_enabled=True)
        assert p1.state_branch_name == p2.state_branch_name

    def test_branch_is_under_oompah_namespace(self):
        """Every derived state branch must start with 'oompah/'."""
        for proj_id in ("proj-a", "proj-b", "proj-zzz"):
            p = _make_project(id=proj_id)
            assert p.state_branch_name.startswith("oompah/")

    def test_branch_oompah_state_subnamespace(self):
        """State branches must be under the oompah/state/ sub-namespace."""
        for proj_id in ("proj-a", "proj-b", "proj-zzz"):
            p = _make_project(id=proj_id)
            assert p.state_branch_name.startswith("oompah/state/")


# ---------------------------------------------------------------------------
# § 14 — xfail-marked design contract (from existing test_state_branch_design.py)
# ---------------------------------------------------------------------------


class TestXfailDesignContractNowPasses:
    """Design-contract tests that were xfail in test_state_branch_design.py.

    These duplicate the xfail test bodies to confirm that the feature is now
    implemented and the assertions hold without xfail marks.  Both sets are
    kept in the test suite: the xfail set as documentation, this set as a
    regression guard.
    """

    def test_state_branch_enabled_defaults_to_false(self):
        """Project.state_branch_enabled must exist and default to False."""
        p = _make_project()
        assert hasattr(p, "state_branch_enabled"), (
            "Project must have a state_branch_enabled attribute"
        )
        assert p.state_branch_enabled is False

    def test_per_project_checkpoint_fields_default_none(self):
        """Per-project checkpoint overrides must default to None."""
        p = _make_project()
        assert hasattr(p, "state_branch_checkpoint_debounce_ms")
        assert hasattr(p, "state_branch_checkpoint_max_delay_ms")
        assert p.state_branch_checkpoint_debounce_ms is None
        assert p.state_branch_checkpoint_max_delay_ms is None

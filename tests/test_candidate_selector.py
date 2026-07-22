"""Tests for CandidateSelector — runtime state and ordering for role dispatch.

Covers acceptance criteria from TASK-407.4:
  AC#1  Priority strategy always returns candidates in configured order.
  AC#2  Round-robin strategy returns never-used candidates before recently
        used candidates.
  AC#3  Round-robin ties are resolved by configured order.
  AC#4  Recording usage updates only the selector-state file, not roles.json.
  AC#5  Removed candidates in stale usage state do not appear in ordered results.
  AC#6  Concurrent selector updates are protected by an in-process lock.

Definition of Done checks:
  DoD#1  Selector state and ordering tests run without depending on the HTTP server.
  DoD#2  The selector API is small enough for the orchestrator to use without
         duplicating ordering logic.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from oompah.roles import (
    Candidate,
    CandidateSelector,
    DEFAULT_USAGE_PATH,
    Role,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _role(
    name: str,
    strategy: str,
    candidates: list[Candidate],
) -> Role:
    return Role(
        name=name,
        strategy=strategy,
        candidates=candidates,
        updated_at=datetime.now(timezone.utc),
    )


def _c(provider_id: str, model: str) -> Candidate:
    return Candidate(provider_id=provider_id, model=model)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ago_iso(seconds: float) -> str:
    """Return an ISO timestamp ``seconds`` seconds in the past."""
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------------------
# Default path constant
# ---------------------------------------------------------------------------


class TestDefaultUsagePath:
    def test_default_path_constant_is_defined(self):
        assert DEFAULT_USAGE_PATH == ".oompah/role_usage.json"

    def test_selector_uses_default_path_when_none(self, tmp_path, monkeypatch):
        """CandidateSelector with path=None resolves to DEFAULT_USAGE_PATH."""
        monkeypatch.chdir(tmp_path)
        sel = CandidateSelector(path=None)
        assert sel.path == DEFAULT_USAGE_PATH


# ---------------------------------------------------------------------------
# Construction and persistence
# ---------------------------------------------------------------------------


class TestCandidateSelectorConstruction:
    def test_new_selector_empty_state(self, tmp_path):
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("standard", "priority", [_c("p1", "m1")])
        assert sel.ordered_candidates(role) == [_c("p1", "m1")]

    def test_missing_file_creates_empty_state(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        sel = CandidateSelector(path=path)
        assert sel._usage == {}

    def test_corrupt_json_falls_back_to_empty(self, tmp_path):
        path = str(tmp_path / "usage.json")
        with open(path, "w") as f:
            f.write("not valid json{{")
        sel = CandidateSelector(path=path)
        assert sel._usage == {}

    def test_non_dict_top_level_falls_back_to_empty(self, tmp_path):
        path = str(tmp_path / "usage.json")
        with open(path, "w") as f:
            json.dump(["unexpected", "list"], f)
        sel = CandidateSelector(path=path)
        assert sel._usage == {}

    def test_valid_usage_file_is_loaded(self, tmp_path):
        path = str(tmp_path / "usage.json")
        ts = _now_iso()
        with open(path, "w") as f:
            json.dump({
                "standard": {
                    "prov-1": {"gpt-4o": ts}
                }
            }, f)
        sel = CandidateSelector(path=path)
        assert sel._usage["standard"]["prov-1"]["gpt-4o"] == ts


# ---------------------------------------------------------------------------
# AC#1 — Priority strategy always returns candidates in configured order
# ---------------------------------------------------------------------------


class TestPriorityStrategy:
    def test_priority_single_candidate(self, tmp_path):
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("fast", "priority", [_c("p1", "m1")])
        assert sel.ordered_candidates(role) == [_c("p1", "m1")]

    def test_priority_two_candidates_configured_order(self, tmp_path):
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("fast", "priority", [_c("p1", "m1"), _c("p2", "m2")])
        result = sel.ordered_candidates(role)
        assert result == [_c("p1", "m1"), _c("p2", "m2")]

    def test_priority_three_candidates_configured_order(self, tmp_path):
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        cands = [_c("p1", "m1"), _c("p2", "m2"), _c("p3", "m3")]
        role = _role("fast", "priority", cands)
        assert sel.ordered_candidates(role) == cands

    def test_priority_ignores_usage_state(self, tmp_path):
        """Priority strategy returns configured order even when usage state exists."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("fast", "priority", [c1, c2])
        # Record c1 as used → in round-robin c2 (never used) would come first;
        # but priority must ignore this entirely.
        sel.record_used("fast", c1)
        result = sel.ordered_candidates(role)
        assert result == [c1, c2]  # priority order preserved

    def test_priority_repeated_calls_stable(self, tmp_path):
        """Multiple calls to ordered_candidates for priority always return the same order."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        cands = [_c("p1", "m1"), _c("p2", "m2"), _c("p3", "m3")]
        role = _role("fast", "priority", cands)
        for _ in range(5):
            assert sel.ordered_candidates(role) == cands

    def test_priority_empty_candidates(self, tmp_path):
        """Empty candidate list returns empty list without error."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("fast", "priority", [])
        assert sel.ordered_candidates(role) == []

    def test_priority_returns_copy_not_original(self, tmp_path):
        """ordered_candidates returns a copy; mutating it doesn't affect the role."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("fast", "priority", [c1, c2])
        result = sel.ordered_candidates(role)
        result.clear()
        assert len(role.candidates) == 2  # original unaffected


# ---------------------------------------------------------------------------
# AC#2 — Round-robin: never-used candidates come before recently-used
# ---------------------------------------------------------------------------


class TestRoundRobinNeverUsedFirst:
    def test_all_never_used_returns_configured_order(self, tmp_path):
        """All candidates never used → same as configured order."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        cands = [_c("p1", "m1"), _c("p2", "m2"), _c("p3", "m3")]
        role = _role("rr", "round_robin", cands)
        assert sel.ordered_candidates(role) == cands

    def test_one_used_one_never_used_never_used_first(self, tmp_path):
        """A candidate used recently should come after a never-used candidate."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")  # used
        c2 = _c("p2", "m2")  # never used
        role = _role("rr", "round_robin", [c1, c2])
        sel.record_used("rr", c1)
        result = sel.ordered_candidates(role)
        assert result[0] == c2  # never-used comes first
        assert result[1] == c1  # used comes second

    def test_two_used_one_never_used_never_used_first(self, tmp_path):
        """Never-used candidate is first even when multiple others have been used."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")  # never used
        role = _role("rr", "round_robin", [c1, c2, c3])
        sel.record_used("rr", c1)
        sel.record_used("rr", c2)
        result = sel.ordered_candidates(role)
        assert result[0] == c3

    def test_lru_comes_first_among_used(self, tmp_path):
        """Among used candidates, the least recently used comes first."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])
        # Inject controlled timestamps: c1 used first (older), c2 used second (newer)
        older_ts = _ago_iso(60)
        newer_ts = _ago_iso(5)
        with sel._lock:
            sel._usage = {
                "rr": {
                    "p1": {"m1": older_ts},
                    "p2": {"m2": newer_ts},
                }
            }
        result = sel.ordered_candidates(role)
        assert result[0] == c1  # older last_used → LRU → comes first
        assert result[1] == c2

    def test_three_used_in_order_lru_first(self, tmp_path):
        """Three candidates used at t1 < t2 < t3; order should be c1, c2, c3."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")
        role = _role("rr", "round_robin", [c1, c2, c3])
        t1 = _ago_iso(300)
        t2 = _ago_iso(200)
        t3 = _ago_iso(100)
        with sel._lock:
            sel._usage = {
                "rr": {
                    "p1": {"m1": t1},
                    "p2": {"m2": t2},
                    "p3": {"m3": t3},
                }
            }
        result = sel.ordered_candidates(role)
        assert result == [c1, c2, c3]

    def test_round_robin_single_candidate(self, tmp_path):
        """Single candidate round-robin always returns that candidate."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        role = _role("rr", "round_robin", [c1])
        sel.record_used("rr", c1)
        assert sel.ordered_candidates(role) == [c1]

    def test_round_robin_advances_on_record_used(self, tmp_path):
        """After using the first candidate, the second becomes first."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        # Initially: both never used → configured order
        assert sel.ordered_candidates(role)[0] == c1

        # After recording c1 as used, c2 (never used) comes first
        sel.record_used("rr", c1)
        assert sel.ordered_candidates(role)[0] == c2

    def test_different_roles_independent_state(self, tmp_path):
        """Usage state for one role does not affect another role's ordering."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role_a = _role("role_a", "round_robin", [c1, c2])
        role_b = _role("role_b", "round_robin", [c1, c2])

        # Record c1 used only in role_a
        sel.record_used("role_a", c1)

        # role_a: c2 (never used there) comes first
        assert sel.ordered_candidates(role_a)[0] == c2
        # role_b: c1 has never been used there → configured order
        assert sel.ordered_candidates(role_b)[0] == c1


# ---------------------------------------------------------------------------
# AC#3 — Round-robin ties resolved by configured order
# ---------------------------------------------------------------------------


class TestRoundRobinTieBreaking:
    def test_all_never_used_tie_breaks_by_configured_order(self, tmp_path):
        """All candidates never used — configured order is the tiebreaker."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        cands = [_c("p1", "m1"), _c("p2", "m2"), _c("p3", "m3")]
        role = _role("rr", "round_robin", cands)
        result = sel.ordered_candidates(role)
        assert result == cands

    def test_same_timestamp_tie_breaks_by_configured_order(self, tmp_path):
        """Candidates with identical last_used_at are ordered by configured index."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")
        role = _role("rr", "round_robin", [c1, c2, c3])
        # All same timestamp
        ts = _now_iso()
        with sel._lock:
            sel._usage = {
                "rr": {
                    "p1": {"m1": ts},
                    "p2": {"m2": ts},
                    "p3": {"m3": ts},
                }
            }
        result = sel.ordered_candidates(role)
        assert result == [c1, c2, c3]  # configured order (tiebreak)

    def test_never_used_tie_among_multiple_candidates(self, tmp_path):
        """When multiple candidates are never used, configured order is preserved."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")
        c4 = _c("p4", "m4")
        role = _role("rr", "round_robin", [c1, c2, c3, c4])
        # c1 was used; c2, c3, c4 never used → c2, c3, c4 all "tie" as never-used
        sel.record_used("rr", c1)
        result = sel.ordered_candidates(role)
        # Never-used candidates come first in configured order: c2, c3, c4
        assert result[0] == c2
        assert result[1] == c3
        assert result[2] == c4
        assert result[3] == c1

    def test_same_provider_different_models_tiebreaks_by_index(self, tmp_path):
        """Same provider, different models — never-used tie breaks by configured index."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p1", "m2")  # same provider, different model
        role = _role("rr", "round_robin", [c1, c2])
        result = sel.ordered_candidates(role)
        assert result == [c1, c2]


# ---------------------------------------------------------------------------
# AC#4 — Recording usage updates only the selector-state file, not roles.json
# ---------------------------------------------------------------------------


class TestRecordUsedPersistence:
    def test_record_used_persists_to_usage_file(self, tmp_path):
        """After record_used, usage.json contains the entry."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        sel.record_used("fast", _c("prov-1", "gpt-4o"))
        with open(path) as f:
            data = json.load(f)
        assert "fast" in data
        assert "prov-1" in data["fast"]
        assert "gpt-4o" in data["fast"]["prov-1"]

    def test_record_used_does_not_create_roles_json(self, tmp_path):
        """record_used should not touch roles.json — only usage.json."""
        usage_path = str(tmp_path / "usage.json")
        roles_path = str(tmp_path / "roles.json")
        sel = CandidateSelector(path=usage_path)
        sel.record_used("fast", _c("prov-1", "gpt-4o"))
        assert not (tmp_path / "roles.json").exists(), (
            "record_used must NOT write to roles.json"
        )

    def test_usage_state_survives_reload(self, tmp_path):
        """Usage persisted by record_used is visible after a fresh CandidateSelector."""
        path = str(tmp_path / "usage.json")
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        sel1 = CandidateSelector(path=path)
        sel1.record_used("rr", c1)  # c1 was used

        # Reload from disk
        sel2 = CandidateSelector(path=path)
        result = sel2.ordered_candidates(role)
        assert result[0] == c2  # c2 (never used) still comes first after reload

    def test_record_used_updates_last_used_at(self, tmp_path):
        """Second record_used for the same candidate updates the timestamp."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")

        sel.record_used("rr", c1)
        with open(path) as f:
            data1 = json.load(f)
        ts1 = data1["rr"]["p1"]["m1"]

        # Sleep a tiny bit and record again
        time.sleep(0.01)
        sel.record_used("rr", c1)
        with open(path) as f:
            data2 = json.load(f)
        ts2 = data2["rr"]["p1"]["m1"]

        assert ts2 > ts1, "Second record_used should have a newer timestamp"

    def test_record_used_stores_iso_timestamp(self, tmp_path):
        """Stored timestamp should be a valid ISO 8601 string."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        sel.record_used("fast", _c("p1", "m1"))
        with open(path) as f:
            data = json.load(f)
        ts_str = data["fast"]["p1"]["m1"]
        # Should parse without error
        dt = datetime.fromisoformat(ts_str)
        assert dt.tzinfo is not None  # timezone-aware

    def test_record_used_multiple_roles_separate_keys(self, tmp_path):
        """Usage state for different roles is stored under separate top-level keys."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        sel.record_used("fast", _c("p1", "m1"))
        sel.record_used("deep", _c("p2", "m2"))
        with open(path) as f:
            data = json.load(f)
        assert "fast" in data
        assert "deep" in data
        assert data["fast"] != data["deep"]

    def test_record_used_same_provider_multiple_models(self, tmp_path):
        """Same provider with different models stores entries independently."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        sel.record_used("rr", _c("prov-1", "gpt-4"))
        sel.record_used("rr", _c("prov-1", "gpt-4o"))
        with open(path) as f:
            data = json.load(f)
        assert "gpt-4" in data["rr"]["prov-1"]
        assert "gpt-4o" in data["rr"]["prov-1"]


# ---------------------------------------------------------------------------
# AC#5 — Removed candidates in stale usage state do not appear in results
# ---------------------------------------------------------------------------


class TestStaleUsageIgnored:
    def test_stale_entry_for_removed_candidate_not_in_results(self, tmp_path):
        """Usage state for a candidate no longer in the role is silently ignored."""
        path = str(tmp_path / "usage.json")
        # Pre-populate usage state for a candidate that won't be in the role
        stale_ts = _ago_iso(100)
        with open(path, "w") as f:
            json.dump({
                "rr": {
                    "p_removed": {"m_removed": stale_ts}
                }
            }, f)
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])
        result = sel.ordered_candidates(role)
        # Only the role's actual candidates should appear
        assert len(result) == 2
        assert _c("p_removed", "m_removed") not in result

    def test_stale_entry_does_not_affect_ordering(self, tmp_path):
        """Stale usage entries should not pollute the ordering of live candidates."""
        path = str(tmp_path / "usage.json")
        # Stale entry exists for a non-existent candidate — live candidates never used
        with open(path, "w") as f:
            json.dump({
                "rr": {
                    "stale_p": {"stale_m": _ago_iso(500)}
                }
            }, f)
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])
        # Both live candidates are never-used → configured order
        assert sel.ordered_candidates(role) == [c1, c2]

    def test_priority_with_stale_state_returns_configured_order(self, tmp_path):
        """Priority strategy returns configured order regardless of any usage state."""
        path = str(tmp_path / "usage.json")
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        with open(path, "w") as f:
            json.dump({
                "fast": {
                    "p1": {"m1": _ago_iso(1)},  # c1 used recently
                }
            }, f)
        sel = CandidateSelector(path=path)
        role = _role("fast", "priority", [c1, c2])
        # Priority must still return configured order
        assert sel.ordered_candidates(role) == [c1, c2]

    def test_empty_candidates_stale_state_returns_empty(self, tmp_path):
        """Empty candidate list returns empty list even if stale state exists."""
        path = str(tmp_path / "usage.json")
        with open(path, "w") as f:
            json.dump({
                "rr": {"p1": {"m1": _ago_iso(10)}}
            }, f)
        sel = CandidateSelector(path=path)
        role = _role("rr", "round_robin", [])
        assert sel.ordered_candidates(role) == []


# ---------------------------------------------------------------------------
# AC#6 — Concurrent selector updates are protected by an in-process lock
# ---------------------------------------------------------------------------


class TestConcurrencyLock:
    def test_lock_exists(self, tmp_path):
        """CandidateSelector has a threading.Lock."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        assert isinstance(sel._lock, type(threading.Lock()))

    def test_concurrent_record_used_no_crash(self, tmp_path):
        """Multiple threads calling record_used concurrently complete without errors."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        errors: list[Exception] = []
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")

        def worker_a():
            try:
                for _ in range(20):
                    sel.record_used("rr", c1)
            except Exception as exc:
                errors.append(exc)

        def worker_b():
            try:
                for _ in range(20):
                    sel.record_used("rr", c2)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker_a), threading.Thread(target=worker_b)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors from concurrent threads: {errors}"

    def test_concurrent_record_used_final_state_valid(self, tmp_path):
        """After concurrent record_used calls, the usage file is valid JSON."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")

        threads = [
            threading.Thread(target=lambda: [sel.record_used("rr", c1) for _ in range(10)]),
            threading.Thread(target=lambda: [sel.record_used("rr", c2) for _ in range(10)]),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with open(path) as f:
            data = json.load(f)
        # Both candidates should have been recorded
        assert "rr" in data
        assert "p1" in data["rr"] and "m1" in data["rr"]["p1"]
        assert "p2" in data["rr"] and "m2" in data["rr"]["p2"]

    def test_concurrent_ordered_candidates_no_crash(self, tmp_path):
        """Multiple threads reading ordered_candidates concurrently complete without errors."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])
        errors: list[Exception] = []

        def reader():
            try:
                for _ in range(50):
                    result = sel.ordered_candidates(role)
                    assert len(result) == 2
            except Exception as exc:
                errors.append(exc)

        def writer():
            try:
                for _ in range(20):
                    sel.record_used("rr", c1)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent access: {errors}"


# ---------------------------------------------------------------------------
# Round-trip: ordered_candidates → record_used cycle
# ---------------------------------------------------------------------------


class TestRoundRobinCycleSimulation:
    def test_full_cycle_two_candidates(self, tmp_path):
        """Simulate two dispatches cycling through two candidates."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        # Dispatch 1: both never used → c1 first (configured order)
        ordered1 = sel.ordered_candidates(role)
        assert ordered1[0] == c1
        sel.record_used("rr", c1)  # record that c1 was selected

        # Dispatch 2: c1 used, c2 never used → c2 first
        ordered2 = sel.ordered_candidates(role)
        assert ordered2[0] == c2
        sel.record_used("rr", c2)  # record that c2 was selected

        # Dispatch 3: both used, c1 is LRU → c1 first again
        ordered3 = sel.ordered_candidates(role)
        assert ordered3[0] == c1

    def test_full_cycle_three_candidates(self, tmp_path):
        """Simulate three dispatches cycling through three candidates."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")
        role = _role("rr", "round_robin", [c1, c2, c3])

        # Round 1: all never used → c1 first
        assert sel.ordered_candidates(role)[0] == c1
        sel.record_used("rr", c1)

        # Round 2: c1 used, c2/c3 never used → c2 first (configured order tiebreak)
        assert sel.ordered_candidates(role)[0] == c2
        sel.record_used("rr", c2)

        # Round 3: c1/c2 used, c3 never used → c3 first
        assert sel.ordered_candidates(role)[0] == c3
        sel.record_used("rr", c3)

        # Round 4: all used, c1 LRU → c1 first
        assert sel.ordered_candidates(role)[0] == c1

    def test_cycle_with_timestamps_injected(self, tmp_path):
        """Inject timestamps to verify exact LRU ordering across a cycle."""
        path = str(tmp_path / "usage.json")
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")
        role = _role("rr", "round_robin", [c1, c2, c3])

        t1 = _ago_iso(300)  # oldest (LRU)
        t2 = _ago_iso(200)
        t3 = _ago_iso(100)  # most recent

        sel = CandidateSelector(path=path)
        with sel._lock:
            sel._usage = {
                "rr": {
                    "p1": {"m1": t1},
                    "p2": {"m2": t2},
                    "p3": {"m3": t3},
                }
            }
        result = sel.ordered_candidates(role)
        assert result == [c1, c2, c3]  # oldest first


# ---------------------------------------------------------------------------
# DoD#1 — Tests run without depending on the HTTP server
# ---------------------------------------------------------------------------


class TestNoServerDependency:
    def test_imports_do_not_require_server(self):
        """CandidateSelector can be imported and used without a running server."""
        # Just the fact that the import at the top of this file succeeded proves this,
        # but we can also exercise the full API here.
        from oompah.roles import CandidateSelector, Candidate
        sel = CandidateSelector.__new__(CandidateSelector)
        # No server needed

    def test_selector_works_without_role_store(self, tmp_path):
        """CandidateSelector does not require a RoleStore — it only needs a Role."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("fast", "round_robin", [_c("p1", "m1"), _c("p2", "m2")])
        # No RoleStore involved
        result = sel.ordered_candidates(role)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# DoD#2 — Selector API is small and usable by orchestrator
# ---------------------------------------------------------------------------


class TestSelectorAPIContract:
    def test_ordered_candidates_returns_list(self, tmp_path):
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("fast", "priority", [_c("p1", "m1")])
        result = sel.ordered_candidates(role)
        assert isinstance(result, list)

    def test_ordered_candidates_elements_are_candidates(self, tmp_path):
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("fast", "priority", [_c("p1", "m1"), _c("p2", "m2")])
        result = sel.ordered_candidates(role)
        for c in result:
            assert isinstance(c, Candidate)

    def test_ordered_candidates_preserves_candidate_fields(self, tmp_path):
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c = _c("my-provider", "my-model")
        role = _role("fast", "priority", [c])
        result = sel.ordered_candidates(role)
        assert result[0].provider_id == "my-provider"
        assert result[0].model == "my-model"

    def test_record_used_returns_none(self, tmp_path):
        """record_used should return None (clean fire-and-forget API)."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        ret = sel.record_used("fast", _c("p1", "m1"))
        assert ret is None

    def test_selector_can_be_instantiated_with_path(self, tmp_path):
        path = str(tmp_path / "custom.json")
        sel = CandidateSelector(path=path)
        assert sel.path == path

    def test_selector_ordered_candidates_accepts_role_not_rolestore(self, tmp_path):
        """ordered_candidates takes a Role object, not a role name or RoleStore."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("x", "priority", [_c("p", "m")])
        # This must work with a plain Role object
        result = sel.ordered_candidates(role)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TASK-449 — Disk-full (ENOSPC) must not crash record_used
# ---------------------------------------------------------------------------


class TestRecordUsedDiskFull:
    """record_used must swallow OSError from _save so a full disk is non-fatal.

    Regression tests for TASK-449: OSError [Errno 28] No space left on device
    was propagating out of CandidateSelector._save() and crashing the worker.
    """

    def test_record_used_survives_oserror_on_open(self, tmp_path):
        """record_used does not raise when open() fails with OSError."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
            # Must not raise
            sel.record_used("deep", _c("prov-651d553c", "claude-3-opus"))

    def test_record_used_logs_warning_on_oserror(self, tmp_path, caplog):
        """record_used emits a warning log when _save fails with OSError."""
        import logging

        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
            with caplog.at_level(logging.WARNING, logger="oompah.roles"):
                sel.record_used("deep", _c("prov-651d553c", "claude-3-opus"))

        assert any(
            "Failed to persist candidate usage state" in record.message
            for record in caplog.records
        ), f"Expected warning not found in: {[r.message for r in caplog.records]}"

    def test_record_used_updates_in_memory_state_even_if_save_fails(self, tmp_path):
        """In-memory usage state is updated even when disk persistence fails."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("prov-651d553c", "claude-3-opus")

        with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
            sel.record_used("deep", c1)

        # In-memory state should reflect the usage even though the file write failed
        assert "deep" in sel._usage
        assert c1.provider_id in sel._usage["deep"]
        assert c1.model in sel._usage["deep"][c1.provider_id]

    def test_record_used_returns_none_even_when_save_fails(self, tmp_path):
        """record_used returns None (not raises) when the disk write fails."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
            result = sel.record_used("deep", _c("prov-651d553c", "claude-3-opus"))
        assert result is None

    def test_record_used_subsequent_calls_work_after_failed_save(self, tmp_path):
        """After a failed save, subsequent record_used calls with working disk succeed."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("prov-651d553c", "claude-3-opus")
        c2 = _c("prov-2", "gpt-4o")

        # First call: disk is full
        with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
            sel.record_used("deep", c1)

        # Second call: disk is available again
        sel.record_used("deep", c2)

        # The second call should have persisted successfully
        import json as _json
        with open(path) as f:
            data = _json.load(f)
        assert "deep" in data
        assert c2.provider_id in data["deep"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_unknown_strategy_treated_as_priority(self, tmp_path):
        """An unrecognised strategy string falls back to configured order."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        # Construct a Role with a strategy value that isn't priority or round_robin.
        role = Role(
            name="x",
            strategy="waterfall",
            candidates=[c1, c2],
            updated_at=datetime.now(timezone.utc),
        )
        # record c1 as used first → if round-robin were applied c2 would come first;
        # but unknown strategy falls back to priority order
        sel.record_used("x", c1)
        result = sel.ordered_candidates(role)
        assert result == [c1, c2]

    def test_multiple_roles_with_same_candidate_different_state(self, tmp_path):
        """Same candidate appearing in two different roles has independent usage."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("shared-p", "shared-m")
        c2 = _c("p2", "m2")
        role_x = _role("x", "round_robin", [c1, c2])
        role_y = _role("y", "round_robin", [c1, c2])

        sel.record_used("x", c1)  # c1 used in role x, not in role y

        assert sel.ordered_candidates(role_x)[0] == c2  # c2 (never-used in x) first
        assert sel.ordered_candidates(role_y)[0] == c1  # both never-used in y → configured

    def test_ordered_candidates_does_not_persist_anything(self, tmp_path):
        """ordered_candidates is read-only — it does not write to disk."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        role = _role("rr", "round_robin", [_c("p1", "m1")])
        sel.ordered_candidates(role)
        # File should not have been created by a read-only call
        assert not (tmp_path / "usage.json").exists()

    def test_record_used_creates_parent_dirs(self, tmp_path):
        """record_used creates parent directories if they don't exist."""
        path = str(tmp_path / "nested" / "dir" / "usage.json")
        sel = CandidateSelector(path=path)
        sel.record_used("fast", _c("p1", "m1"))
        assert (tmp_path / "nested" / "dir" / "usage.json").exists()


# ===========================================================================
# OOMPAH-346 — reserve_candidate: atomic dispatch-time reservation
# ===========================================================================
#
# These tests cover the new reserve_candidate() method and verify the
# acceptance criteria from OOMPAH-346:
#
#   AC#R1  reserve_candidate() selects the LRU candidate and stamps it
#          atomically so that a concurrent call selects a different candidate.
#   AC#R2  N concurrent reserve_candidate() calls for a two-candidate
#          round-robin role alternate fairly (counts differ by ≤1 for even N).
#   AC#R3  reserve_candidate() for separate roles uses independent state.
#   AC#R4  For non-round-robin roles reserve_candidate() returns the first
#          eligible candidate without stamping usage state.
#   AC#R5  reserve_candidate() with exclude skips named candidates and
#          selects the next eligible one.
#   AC#R6  reserve_candidate() returns None when no eligible candidates remain.
#   AC#R7  Usage state is persisted to disk before the method returns, so
#          a fresh CandidateSelector loaded from that file observes the
#          reservation and selects the next candidate.


class TestReserveCandidateBasics:
    """Unit tests for CandidateSelector.reserve_candidate() — basic contract."""

    def test_returns_candidate_object(self, tmp_path):
        """reserve_candidate() returns a Candidate, not None, when candidates exist."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        role = _role("rr", "round_robin", [c1])
        result = sel.reserve_candidate(role)
        assert isinstance(result, Candidate)
        assert result == c1

    def test_returns_none_for_empty_role(self, tmp_path):
        """reserve_candidate() returns None when the role has no candidates."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role = _role("rr", "round_robin", [])
        assert sel.reserve_candidate(role) is None

    def test_returns_none_when_all_excluded(self, tmp_path):
        """reserve_candidate() returns None when all candidates are in exclude."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])
        assert sel.reserve_candidate(role, exclude=[c1, c2]) is None

    def test_selects_lru_candidate(self, tmp_path):
        """reserve_candidate() selects the least-recently-used candidate."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        # Pre-stamp c1 as more recently used
        with sel._lock:
            sel._usage = {
                "rr": {
                    "p1": {"m1": _ago_iso(10)},   # older
                    "p2": {"m2": _ago_iso(100)},  # more recent
                }
            }

        result = sel.reserve_candidate(role)
        # c2 has the older stamp → it's the LRU → selected
        assert result == c2

    def test_selects_never_used_over_used(self, tmp_path):
        """reserve_candidate() prefers a never-used candidate over a used one."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")  # never used
        role = _role("rr", "round_robin", [c1, c2])
        sel.record_used("rr", c1)  # c1 has been used

        result = sel.reserve_candidate(role)
        assert result == c2

    def test_stamps_selected_candidate_immediately(self, tmp_path):
        """After reserve_candidate(), the selected candidate is stamped in usage state."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        before = datetime.now(timezone.utc)
        selected = sel.reserve_candidate(role)
        after = datetime.now(timezone.utc)

        assert selected is not None
        with sel._lock:
            ts_str = (
                sel._usage
                .get("rr", {})
                .get(selected.provider_id, {})
                .get(selected.model)
            )
        assert ts_str is not None, "Selected candidate must be stamped"
        ts = datetime.fromisoformat(ts_str)
        assert before <= ts <= after, "Stamp must be within the call window"

    def test_stamp_persisted_to_disk(self, tmp_path):
        """reserve_candidate() persists the stamp to disk before returning."""
        import json as _json
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        role = _role("rr", "round_robin", [c1])

        sel.reserve_candidate(role)

        with open(path) as f:
            data = _json.load(f)
        assert "rr" in data
        assert "p1" in data["rr"]
        assert "m1" in data["rr"]["p1"]

    def test_consecutive_reserves_alternate_two_candidates(self, tmp_path):
        """Two consecutive reserve_candidate() calls on a 2-candidate role alternate."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        first = sel.reserve_candidate(role)
        second = sel.reserve_candidate(role)

        assert first != second, "Consecutive reserve_candidate() calls must select different candidates"
        assert {first, second} == {c1, c2}

    def test_three_consecutive_reserves_cycle(self, tmp_path):
        """Three consecutive reserves cycle: C1, C2, C1."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        r1 = sel.reserve_candidate(role)
        r2 = sel.reserve_candidate(role)
        r3 = sel.reserve_candidate(role)

        assert r1 == c1
        assert r2 == c2
        assert r3 == c1

    def test_reserve_creates_parent_dirs(self, tmp_path):
        """reserve_candidate() creates parent directories for the usage file."""
        path = str(tmp_path / "nested" / "dir" / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        role = _role("rr", "round_robin", [c1])
        sel.reserve_candidate(role)
        assert (tmp_path / "nested" / "dir" / "usage.json").exists()


class TestReserveCandidateAtomicity:
    """Concurrency tests — the core correctness guarantee of OOMPAH-346."""

    def test_n_concurrent_reserves_alternate_fairly(self, tmp_path):
        """N concurrent reserve_candidate() calls for a 2-candidate role
        distribute evenly: for even N, counts differ by no more than one,
        and never exhibit the all-first-candidate race (AC#R2).
        """
        N = 20  # even number of concurrent reservations
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        results: list[Candidate] = []
        lock = threading.Lock()
        errors: list[Exception] = []

        def worker():
            try:
                selected = sel.reserve_candidate(role)
                assert selected is not None
                with lock:
                    results.append(selected)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent reserves: {errors}"
        assert len(results) == N

        count_c1 = results.count(c1)
        count_c2 = results.count(c2)

        # Fairness: counts must differ by at most 1
        assert abs(count_c1 - count_c2) <= 1, (
            f"Unfair distribution: c1={count_c1}, c2={count_c2}. "
            f"All-first-candidate race not fixed."
        )
        # Liveness: both candidates must be selected at least once
        assert count_c1 > 0, "c1 must be selected at least once"
        assert count_c2 > 0, "c2 must be selected at least once"

    def test_concurrent_reserves_never_all_select_first_candidate(self, tmp_path):
        """No matter how many concurrent calls happen, never ALL select c1."""
        N = 10
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        results: list[Candidate] = []
        lock = threading.Lock()

        def worker():
            r = sel.reserve_candidate(role)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(c2) > 0, (
            f"Regression: all {N} concurrent reserves selected c1 only. "
            "The all-first-candidate race is NOT fixed."
        )

    def test_concurrent_reserves_for_two_candidate_role_odd_n(self, tmp_path):
        """Odd N: the majority candidate is selected ceil(N/2) times."""
        N = 7
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        results: list[Candidate] = []
        lock = threading.Lock()

        def worker():
            r = sel.reserve_candidate(role)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        count_c1 = results.count(c1)
        count_c2 = results.count(c2)

        # For odd N, counts can differ by at most 1
        assert abs(count_c1 - count_c2) <= 1, (
            f"Unfair distribution for odd N={N}: c1={count_c1}, c2={count_c2}"
        )
        assert count_c1 + count_c2 == N

    def test_concurrent_reserves_no_crash(self, tmp_path):
        """Many concurrent reserve_candidate() calls complete without errors."""
        N = 50
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")
        role = _role("rr", "round_robin", [c1, c2, c3])

        errors: list[Exception] = []
        lock = threading.Lock()
        results: list[Candidate] = []

        def worker():
            try:
                r = sel.reserve_candidate(role)
                with lock:
                    results.append(r)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent reserves: {errors}"
        assert len(results) == N
        # All three candidates should be selected
        assert results.count(c1) > 0
        assert results.count(c2) > 0
        assert results.count(c3) > 0

    def test_concurrent_reserve_usage_file_remains_valid_json(self, tmp_path):
        """After concurrent reserve_candidate() calls, the usage file is valid JSON."""
        import json as _json
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        threads = [
            threading.Thread(target=lambda: [sel.reserve_candidate(role) for _ in range(5)])
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with open(path) as f:
            data = _json.load(f)
        assert isinstance(data, dict)


class TestReserveCandidatePriorityStrategy:
    """AC#R4 — priority strategy: no stamping, configured order preserved."""

    def test_priority_returns_first_candidate(self, tmp_path):
        """reserve_candidate() on a priority role returns the first candidate."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("fast", "priority", [c1, c2])
        assert sel.reserve_candidate(role) == c1

    def test_priority_does_not_stamp_usage(self, tmp_path):
        """reserve_candidate() on a priority role does not write usage state."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        role = _role("fast", "priority", [c1])
        sel.reserve_candidate(role)
        # For priority roles, no file should be created
        assert not (tmp_path / "usage.json").exists(), (
            "reserve_candidate() on priority role must not create usage file"
        )

    def test_priority_repeated_calls_same_result(self, tmp_path):
        """Multiple reserve_candidate() calls on a priority role return the same candidate."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("fast", "priority", [c1, c2])
        for _ in range(5):
            assert sel.reserve_candidate(role) == c1

    def test_priority_exclude_skips_to_next(self, tmp_path):
        """reserve_candidate() on priority role with exclude returns next non-excluded."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        c3 = _c("p3", "m3")
        role = _role("fast", "priority", [c1, c2, c3])
        assert sel.reserve_candidate(role, exclude=[c1]) == c2
        assert sel.reserve_candidate(role, exclude=[c1, c2]) == c3
        assert sel.reserve_candidate(role, exclude=[c1, c2, c3]) is None


class TestReserveCandidateExclude:
    """AC#R5 — exclude parameter skips failed candidates."""

    def test_exclude_single_candidate(self, tmp_path):
        """reserve_candidate() skips the excluded candidate and selects the next."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        # First reserve picks c1, exclude it, second must pick c2
        sel.reserve_candidate(role)  # stamps c1
        result = sel.reserve_candidate(role, exclude=[c1])
        assert result == c2

    def test_exclude_does_not_affect_other_selects(self, tmp_path):
        """Excluding a candidate does not permanently remove it from future calls."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        # Exclude c1 in one call; subsequent call (without exclude) can still get c1
        result_with_exclude = sel.reserve_candidate(role, exclude=[c1])
        assert result_with_exclude == c2  # c2 selected (c1 excluded)

        # Now call without exclude — both are eligible; c1 is never-used (LRU)
        result_no_exclude = sel.reserve_candidate(role)
        assert result_no_exclude == c1  # c1 is LRU (never stamped by reserve)

    def test_exclude_empty_list_treated_as_no_exclusion(self, tmp_path):
        """Passing an empty exclude list is equivalent to no exclusion."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])
        assert sel.reserve_candidate(role, exclude=[]) == c1

    def test_exclude_none_is_same_as_no_exclusion(self, tmp_path):
        """Passing exclude=None is the default (no exclusion)."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        role = _role("rr", "round_robin", [c1])
        assert sel.reserve_candidate(role, exclude=None) == c1


class TestReserveCandidateIndependentRoles:
    """AC#R3 — separate roles retain independent usage state."""

    def test_reserve_on_one_role_does_not_affect_other_role(self, tmp_path):
        """Reserving in role_a does not change ordering in role_b."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role_a = _role("role_a", "round_robin", [c1, c2])
        role_b = _role("role_b", "round_robin", [c1, c2])

        # Reserve c1 in role_a
        selected_a = sel.reserve_candidate(role_a)
        assert selected_a == c1  # c1 is LRU (never used)

        # role_b: c1 has never been reserved there → still gets c1
        selected_b = sel.reserve_candidate(role_b)
        assert selected_b == c1, (
            "Role_b must be independent of role_a's reservation"
        )

    def test_concurrent_reserves_for_different_roles_are_independent(self, tmp_path):
        """Concurrent reserves on different roles do not interfere."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role_a = _role("role_a", "round_robin", [c1, c2])
        role_b = _role("role_b", "round_robin", [c1, c2])

        results_a: list[Candidate] = []
        results_b: list[Candidate] = []
        lock = threading.Lock()

        def worker_a():
            r = sel.reserve_candidate(role_a)
            with lock:
                results_a.append(r)

        def worker_b():
            r = sel.reserve_candidate(role_b)
            with lock:
                results_b.append(r)

        N = 10
        threads = (
            [threading.Thread(target=worker_a) for _ in range(N)]
            + [threading.Thread(target=worker_b) for _ in range(N)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Both roles should have balanced distributions
        assert abs(results_a.count(c1) - results_a.count(c2)) <= 1, (
            "role_a distribution must be fair"
        )
        assert abs(results_b.count(c1) - results_b.count(c2)) <= 1, (
            "role_b distribution must be fair"
        )

    def test_two_roles_usage_stored_under_separate_keys(self, tmp_path):
        """Usage from different roles is stored under separate top-level keys."""
        import json as _json
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        c1 = _c("p1", "m1")
        role_a = _role("role_a", "round_robin", [c1])
        role_b = _role("role_b", "round_robin", [c1])

        sel.reserve_candidate(role_a)
        sel.reserve_candidate(role_b)

        with open(path) as f:
            data = _json.load(f)
        assert "role_a" in data, "role_a must have its own key"
        assert "role_b" in data, "role_b must have its own key"


class TestReserveCandidatePersistence:
    """AC#R7 — reservation persists across selector instances (service restart)."""

    def test_reservation_visible_to_fresh_selector(self, tmp_path):
        """Usage stamped by reserve_candidate() is visible to a fresh selector instance."""
        path = str(tmp_path / "usage.json")
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        sel1 = CandidateSelector(path=path)
        selected1 = sel1.reserve_candidate(role)
        assert selected1 == c1

        # Reload from disk — simulates service restart
        sel2 = CandidateSelector(path=path)
        selected2 = sel2.reserve_candidate(role)
        assert selected2 == c2, (
            "After service restart, the next reserve must get the next candidate"
        )

    def test_reservation_ordering_correct_after_reload(self, tmp_path):
        """The full cycle c1→c2→c1 is maintained across selector reloads."""
        path = str(tmp_path / "usage.json")
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])

        sel1 = CandidateSelector(path=path)
        assert sel1.reserve_candidate(role) == c1  # dispatch 1

        sel2 = CandidateSelector(path=path)
        assert sel2.reserve_candidate(role) == c2  # dispatch 2

        sel3 = CandidateSelector(path=path)
        assert sel3.reserve_candidate(role) == c1  # dispatch 3 → cycles back

    def test_reserve_creates_file_if_not_exists(self, tmp_path):
        """reserve_candidate() creates the usage file if it does not exist yet."""
        path = str(tmp_path / "usage.json")
        sel = CandidateSelector(path=path)
        assert not (tmp_path / "usage.json").exists()

        c1 = _c("p1", "m1")
        role = _role("rr", "round_robin", [c1])
        sel.reserve_candidate(role)

        assert (tmp_path / "usage.json").exists()


class TestReserveCandidateReturnValue:
    """API contract: return type and behaviour."""

    def test_returns_candidate_or_none(self, tmp_path):
        """reserve_candidate() returns a Candidate or None — never raises."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        role_with = _role("rr", "round_robin", [_c("p1", "m1")])
        role_empty = _role("rr", "round_robin", [])

        r1 = sel.reserve_candidate(role_with)
        r2 = sel.reserve_candidate(role_empty)

        assert isinstance(r1, Candidate)
        assert r2 is None

    def test_reserve_does_not_mutate_role_candidates(self, tmp_path):
        """reserve_candidate() does not modify the role's candidate list."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("rr", "round_robin", [c1, c2])
        original_candidates = list(role.candidates)

        sel.reserve_candidate(role)

        assert list(role.candidates) == original_candidates, (
            "reserve_candidate() must not modify role.candidates"
        )

    def test_reserve_candidate_method_exists(self, tmp_path):
        """CandidateSelector must expose a reserve_candidate() public method."""
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        assert callable(getattr(sel, "reserve_candidate", None)), (
            "CandidateSelector must have a reserve_candidate() method"
        )

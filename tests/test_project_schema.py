"""Schema tests for Project dataclass fields beyond the original set.

Currently exercises:
- max_concurrent_agents: round-trip None / positive int, legacy default

The richer max_in_flight_prs tests live in tests/test_submit_queue_concurrency.py;
this module covers the per-project agent cap (bead oompah-zlz_2-okxw)
without depending on the orchestrator or any infrastructure.
"""

from __future__ import annotations

import pytest

from oompah.models import Project


# ---------------------------------------------------------------------------
# max_concurrent_agents
# ---------------------------------------------------------------------------


class TestMaxConcurrentAgentsSchema:
    """Project.max_concurrent_agents field: default, to_dict, from_dict."""

    # --- defaults ---

    def test_default_is_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.max_concurrent_agents is None

    # --- to_dict omits None ---

    def test_to_dict_omits_field_when_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert "max_concurrent_agents" not in d

    def test_to_dict_includes_field_when_set(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            max_concurrent_agents=3,
        )
        d = p.to_dict()
        assert d["max_concurrent_agents"] == 3

    def test_to_safe_dict_includes_field_when_set(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            max_concurrent_agents=5,
        )
        d = p.to_safe_dict()
        assert d["max_concurrent_agents"] == 5

    def test_to_safe_dict_omits_field_when_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_safe_dict()
        assert "max_concurrent_agents" not in d

    # --- round-trip ---

    def test_max_concurrent_agents_serialization_round_trip_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        p2 = Project.from_dict(p.to_dict())
        assert p2.max_concurrent_agents is None

    def test_max_concurrent_agents_serialization_round_trip_positive(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            max_concurrent_agents=4,
        )
        p2 = Project.from_dict(p.to_dict())
        assert p2.max_concurrent_agents == 4

    # --- from_dict back-compat / coercion ---

    def test_legacy_project_without_field_defaults_none(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a"})
        assert p.max_concurrent_agents is None

    def test_from_dict_null_value_yields_none(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a",
                                "max_concurrent_agents": None})
        assert p.max_concurrent_agents is None

    def test_from_dict_positive_int_kept(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a",
                                "max_concurrent_agents": 7})
        assert p.max_concurrent_agents == 7

    def test_from_dict_zero_treated_as_unlimited(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a",
                                "max_concurrent_agents": 0})
        assert p.max_concurrent_agents is None

    def test_from_dict_negative_treated_as_unlimited(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a",
                                "max_concurrent_agents": -2})
        assert p.max_concurrent_agents is None

    def test_from_dict_garbage_string_treated_as_unlimited(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a",
                                "max_concurrent_agents": "bad"})
        assert p.max_concurrent_agents is None

    def test_from_dict_numeric_string_parsed(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a",
                                "max_concurrent_agents": "3"})
        assert p.max_concurrent_agents == 3

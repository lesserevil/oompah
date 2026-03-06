"""Tests for oompah.models."""

from oompah.models import (
    AgentProfile,
    Issue,
    ModelProvider,
    Project,
)


class TestProject:
    def test_to_dict_minimal(self):
        p = Project(id="p1", name="test", repo_url="https://x", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["id"] == "p1"
        assert d["name"] == "test"
        assert "git_user_name" not in d
        assert "git_user_email" not in d

    def test_to_dict_with_git_identity(self):
        p = Project(
            id="p1", name="test", repo_url="https://x", repo_path="/tmp/x",
            git_user_name="Alice", git_user_email="alice@example.com",
        )
        d = p.to_dict()
        assert d["git_user_name"] == "Alice"
        assert d["git_user_email"] == "alice@example.com"

    def test_from_dict_round_trip(self):
        original = Project(
            id="p1", name="myrepo", repo_url="https://github.com/x/y",
            repo_path="/tmp/y", branch="develop",
            git_user_name="Bob", git_user_email="bob@test.com",
        )
        restored = Project.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.branch == original.branch
        assert restored.git_user_name == original.git_user_name
        assert restored.git_user_email == original.git_user_email

    def test_from_dict_defaults(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z", "repo_path": "/a"})
        assert p.branch == "main"
        assert p.git_user_name is None
        assert p.git_user_email is None


class TestModelProvider:
    def test_to_safe_dict_masks_key(self):
        mp = ModelProvider(
            id="prov-1", name="test", base_url="http://localhost",
            api_key="sk-1234567890abcdefghijkl",
        )
        safe = mp.to_safe_dict()
        assert "api_key" not in safe
        assert safe["api_key_masked"].startswith("sk-12345")
        assert safe["api_key_masked"].endswith("jkl")

    def test_to_safe_dict_short_key(self):
        mp = ModelProvider(id="prov-1", name="test", base_url="http://x", api_key="short")
        safe = mp.to_safe_dict()
        assert safe["api_key_masked"] == "***"

    def test_to_safe_dict_empty_key(self):
        mp = ModelProvider(id="prov-1", name="test", base_url="http://x", api_key="")
        safe = mp.to_safe_dict()
        assert safe["api_key_masked"] == ""

    def test_get_model_costs(self):
        mp = ModelProvider(
            id="prov-1", name="test", base_url="http://x",
            model_costs={"gpt-4": {"cost_per_1k_input": 0.03, "cost_per_1k_output": 0.06}},
        )
        assert mp.get_model_costs("gpt-4") == (0.03, 0.06)
        assert mp.get_model_costs("unknown") == (0.0, 0.0)

    def test_from_dict_round_trip(self):
        original = ModelProvider(
            id="prov-1", name="openai", base_url="https://api.openai.com",
            api_key="sk-test", models=["gpt-4"], default_model="gpt-4",
            model_roles={"fast": "gpt-4o-mini"},
        )
        restored = ModelProvider.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.models == original.models
        assert restored.model_roles == original.model_roles


class TestIssue:
    def test_defaults(self):
        i = Issue(id="1", identifier="beads-001", title="Test")
        assert i.state == ""
        assert i.issue_type == "task"
        assert i.labels == []
        assert i.blocked_by == []

    def test_fields(self):
        i = Issue(
            id="1", identifier="beads-001", title="Fix bug",
            priority=1, state="open", issue_type="bug",
            labels=["urgent"], description="Something broke",
        )
        assert i.priority == 1
        assert i.issue_type == "bug"
        assert "urgent" in i.labels


class TestAgentProfile:
    def test_defaults(self):
        ap = AgentProfile(name="quick", command="claude")
        assert ap.keywords == []
        assert ap.issue_types == []
        assert ap.min_priority is None
        assert ap.max_priority is None

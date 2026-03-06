"""Tests for oompah.config."""

import os
import tempfile

import pytest

from oompah.config import (
    ServiceConfig,
    WorkflowError,
    _coerce_int,
    _parse_state_list,
    _resolve_env,
    load_workflow,
    validate_dispatch_config,
)
from oompah.models import WorkflowDefinition


class TestLoadWorkflow:
    def test_plain_markdown(self, tmp_path):
        f = tmp_path / "WORKFLOW.md"
        f.write_text("You are an agent.\n\nDo the work.")
        wf = load_workflow(str(f))
        assert wf.config == {}
        assert "You are an agent." in wf.prompt_template

    def test_with_front_matter(self, tmp_path):
        f = tmp_path / "WORKFLOW.md"
        f.write_text("---\ntracker:\n  kind: beads\npoll_ms: 5000\n---\nHello {{ issue.title }}")
        wf = load_workflow(str(f))
        assert wf.config["tracker"]["kind"] == "beads"
        assert "Hello" in wf.prompt_template

    def test_missing_file(self):
        with pytest.raises(WorkflowError, match="not found"):
            load_workflow("/nonexistent/WORKFLOW.md")

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "WORKFLOW.md"
        f.write_text("---\n: bad: yaml: [unclosed\n---\nBody")
        with pytest.raises(WorkflowError, match="Invalid YAML"):
            load_workflow(str(f))

    def test_non_dict_front_matter(self, tmp_path):
        f = tmp_path / "WORKFLOW.md"
        f.write_text("---\n- list\n- items\n---\nBody")
        with pytest.raises(WorkflowError, match="must be a map"):
            load_workflow(str(f))

    def test_empty_front_matter(self, tmp_path):
        f = tmp_path / "WORKFLOW.md"
        f.write_text("---\n\n---\nBody text")
        wf = load_workflow(str(f))
        assert wf.config == {}
        assert "Body text" in wf.prompt_template


class TestServiceConfig:
    def test_from_workflow_defaults(self):
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.tracker_kind == "beads"
        assert cfg.poll_interval_ms == 30000
        assert cfg.max_concurrent_agents == 10
        assert cfg.budget_limit == 0.0
        assert cfg.workspace_root  # should have a default

    def test_from_workflow_custom(self):
        wf = WorkflowDefinition(
            config={
                "tracker": {"kind": "beads", "active_states": ["open"]},
                "polling": {"interval_ms": 5000},
                "agent": {
                    "max_concurrent_agents": 3,
                    "stall_turns": 10,
                    "budget_limit": 100.0,
                    "profiles": [
                        {"name": "quick", "model_role": "fast", "issue_types": ["chore"]},
                    ],
                },
                "server": {"port": 9090},
            },
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.poll_interval_ms == 5000
        assert cfg.max_concurrent_agents == 3
        assert cfg.stall_turns == 10
        assert cfg.budget_limit == 100.0
        assert cfg.server_port == 9090
        assert len(cfg.agent_profiles) == 1
        assert cfg.agent_profiles[0].name == "quick"
        assert cfg.agent_profiles[0].model_role == "fast"

    def test_tracker_active_states_string(self):
        wf = WorkflowDefinition(
            config={"tracker": {"active_states": "open, in_progress"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.tracker_active_states == ["open", "in_progress"]


class TestHelpers:
    def test_coerce_int(self):
        assert _coerce_int(42, 0) == 42
        assert _coerce_int("100", 0) == 100
        assert _coerce_int(None, 5) == 5
        assert _coerce_int("bad", 5) == 5

    def test_parse_state_list_string(self):
        assert _parse_state_list("open, closed", []) == ["open", "closed"]

    def test_parse_state_list_list(self):
        assert _parse_state_list(["open", "closed"], []) == ["open", "closed"]

    def test_parse_state_list_none(self):
        assert _parse_state_list(None, ["default"]) == ["default"]

    def test_resolve_env(self):
        os.environ["_OOMPAH_TEST_VAR"] = "hello"
        assert _resolve_env("$_OOMPAH_TEST_VAR") == "hello"
        assert _resolve_env("literal") == "literal"
        del os.environ["_OOMPAH_TEST_VAR"]


class TestValidateDispatchConfig:
    def test_valid(self):
        cfg = ServiceConfig()
        errors = validate_dispatch_config(cfg)
        assert errors == []

    def test_invalid_tracker(self):
        cfg = ServiceConfig(tracker_kind="jira")
        errors = validate_dispatch_config(cfg)
        assert any("Unsupported" in e for e in errors)

    def test_empty_command(self):
        cfg = ServiceConfig(agent_command="")
        errors = validate_dispatch_config(cfg)
        assert any("agent_command" in e for e in errors)

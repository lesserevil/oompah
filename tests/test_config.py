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
    load_dotenv,
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


class TestLoadDotenv:
    """Tests for the load_dotenv function."""

    def _make_env(self, tmp_path, content: str) -> str:
        f = tmp_path / ".env"
        f.write_text(content)
        return str(f)

    def test_missing_file_returns_zero(self, tmp_path):
        count = load_dotenv(str(tmp_path / "nonexistent.env"))
        assert count == 0

    def test_basic_key_value(self, tmp_path):
        path = self._make_env(tmp_path, "OOMPAH_TEST_BASIC=hello\n")
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
            assert os.environ["OOMPAH_TEST_BASIC"] == "hello"
        finally:
            os.environ.pop("OOMPAH_TEST_BASIC", None)

    def test_double_quoted_value(self, tmp_path):
        path = self._make_env(tmp_path, 'OOMPAH_TEST_DQ="hello world"\n')
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
            assert os.environ["OOMPAH_TEST_DQ"] == "hello world"
        finally:
            os.environ.pop("OOMPAH_TEST_DQ", None)

    def test_single_quoted_value(self, tmp_path):
        path = self._make_env(tmp_path, "OOMPAH_TEST_SQ='hello world'\n")
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
            assert os.environ["OOMPAH_TEST_SQ"] == "hello world"
        finally:
            os.environ.pop("OOMPAH_TEST_SQ", None)

    def test_comments_ignored(self, tmp_path):
        content = "# this is a comment\nOOMPAH_TEST_CMT=val\n# another comment\n"
        path = self._make_env(tmp_path, content)
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
            assert os.environ["OOMPAH_TEST_CMT"] == "val"
        finally:
            os.environ.pop("OOMPAH_TEST_CMT", None)

    def test_blank_lines_ignored(self, tmp_path):
        content = "\n\nOOMPAH_TEST_BL=val\n\n"
        path = self._make_env(tmp_path, content)
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
        finally:
            os.environ.pop("OOMPAH_TEST_BL", None)

    def test_export_prefix(self, tmp_path):
        path = self._make_env(tmp_path, "export OOMPAH_TEST_EXP=exported\n")
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
            assert os.environ["OOMPAH_TEST_EXP"] == "exported"
        finally:
            os.environ.pop("OOMPAH_TEST_EXP", None)

    def test_no_override_by_default(self, tmp_path):
        os.environ["OOMPAH_TEST_NOOV"] = "original"
        path = self._make_env(tmp_path, "OOMPAH_TEST_NOOV=changed\n")
        try:
            count = load_dotenv(path)  # override=False by default
            # Variable was NOT loaded (already set)
            assert count == 0
            assert os.environ["OOMPAH_TEST_NOOV"] == "original"
        finally:
            os.environ.pop("OOMPAH_TEST_NOOV", None)

    def test_override_flag(self, tmp_path):
        os.environ["OOMPAH_TEST_OV"] = "original"
        path = self._make_env(tmp_path, "OOMPAH_TEST_OV=changed\n")
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
            assert os.environ["OOMPAH_TEST_OV"] == "changed"
        finally:
            os.environ.pop("OOMPAH_TEST_OV", None)

    def test_escape_sequences_in_double_quotes(self, tmp_path):
        path = self._make_env(tmp_path, r'OOMPAH_TEST_ESC="line1\nline2"' + "\n")
        try:
            load_dotenv(path, override=True)
            assert os.environ["OOMPAH_TEST_ESC"] == "line1\nline2"
        finally:
            os.environ.pop("OOMPAH_TEST_ESC", None)

    def test_multiple_vars(self, tmp_path):
        content = "OOMPAH_TEST_A=aaa\nOOMPAH_TEST_B=bbb\nOOMPAH_TEST_C=ccc\n"
        path = self._make_env(tmp_path, content)
        try:
            count = load_dotenv(path, override=True)
            assert count == 3
            assert os.environ["OOMPAH_TEST_A"] == "aaa"
            assert os.environ["OOMPAH_TEST_B"] == "bbb"
            assert os.environ["OOMPAH_TEST_C"] == "ccc"
        finally:
            for k in ("OOMPAH_TEST_A", "OOMPAH_TEST_B", "OOMPAH_TEST_C"):
                os.environ.pop(k, None)

    def test_env_var_available_in_resolve_env(self, tmp_path):
        """Verify that vars loaded from .env are resolved via _resolve_env."""
        path = self._make_env(tmp_path, "OOMPAH_TEST_RESOLVE=resolved_value\n")
        try:
            load_dotenv(path, override=True)
            result = _resolve_env("$OOMPAH_TEST_RESOLVE")
            assert result == "resolved_value"
        finally:
            os.environ.pop("OOMPAH_TEST_RESOLVE", None)

    def test_invalid_key_skipped(self, tmp_path):
        content = "123INVALID=val\nOOMPAH_TEST_VALID=ok\n"
        path = self._make_env(tmp_path, content)
        try:
            count = load_dotenv(path, override=True)
            assert count == 1
            assert os.environ.get("OOMPAH_TEST_VALID") == "ok"
            assert "123INVALID" not in os.environ
        finally:
            os.environ.pop("OOMPAH_TEST_VALID", None)

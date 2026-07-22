"""Tests for oompah.config."""

import os
import tempfile
from pathlib import Path

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
        f.write_text(
            "---\ntracker:\n  kind: oompah_md\npoll_ms: 5000\n---\n"
            "Hello {{ issue.title }}"
        )
        wf = load_workflow(str(f))
        assert wf.config["tracker"]["kind"] == "oompah_md"
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
    def setup_method(self):
        """Clear OOMPAH_* polling env vars so tests run in a clean environment."""
        for key in list(os.environ):
            if key.startswith("OOMPAH_"):
                os.environ.pop(key, None)

    def teardown_method(self):
        """Restore clean environment after each test."""
        for key in list(os.environ):
            if key.startswith("OOMPAH_"):
                os.environ.pop(key, None)

    def test_from_workflow_defaults(self):
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.tracker_kind == "oompah_md"
        assert cfg.poll_interval_ms == 120000
        assert cfg.max_concurrent_agents == 10
        assert cfg.budget_limit == 0.0
        # Default rolling window is "day" — picked because most operators
        # think of $X/day rather than $X/process-lifetime.
        assert cfg.budget_window == "day"
        assert cfg.server_port == 8080
        assert cfg.dispatch_scan_limit == 64
        assert cfg.duplicate_detection_candidate_limit == 64
        assert cfg.auto_archive_batch_size == 25
        assert cfg.worktree_cleanup_batch_size == 25
        assert cfg.release_pick_max_runtime_seconds == 15
        assert cfg.merged_labels_max_runtime_seconds == 15
        assert cfg.close_gate_enabled is True
        assert cfg.gitlab_webhook_public_url is None
        assert cfg.workspace_root  # should have a default

    def test_gitlab_webhook_public_url_comes_from_environment(self, monkeypatch):
        monkeypatch.setenv(
            "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL", "https://oompah.example.com/"
        )
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="test"))
        assert cfg.gitlab_webhook_public_url == "https://oompah.example.com/"


class TestRepoMapEnvironmentConfiguration(TestServiceConfig):
    """Repository-map settings are environment-only operator controls."""

    ENVIRONMENT_VARIABLES = {
        "OOMPAH_REPO_MAP_ENABLED",
        "OOMPAH_REPO_MAP_TOKEN_BUDGET",
        "OOMPAH_REPO_MAP_LANGUAGES",
        "OOMPAH_REPO_MAP_MAX_FILE_SIZE",
        "OOMPAH_REPO_MAP_GENERATION_TIMEOUT",
        "OOMPAH_REPO_MAP_RETAINED_ARTIFACTS",
    }

    def _config(self) -> ServiceConfig:
        return ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )

    def test_safe_defaults_leave_repository_maps_disabled(self):
        cfg = self._config()

        assert cfg.repo_map_enabled is False
        assert cfg.repo_map_token_budget == 2000
        assert set(cfg.repo_map_languages) == {
            "javascript", "markdown", "python", "rust", "typescript", "yaml"
        }
        assert cfg.repo_map_max_file_size == 1_000_000
        assert cfg.repo_map_generation_timeout == 120
        assert cfg.repo_map_retained_artifacts == 5

    def test_valid_environment_overrides_are_applied(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "true")
        monkeypatch.setenv("OOMPAH_REPO_MAP_TOKEN_BUDGET", "4096")
        monkeypatch.setenv("OOMPAH_REPO_MAP_LANGUAGES", "python, typescript")
        monkeypatch.setenv("OOMPAH_REPO_MAP_MAX_FILE_SIZE", "524288")
        monkeypatch.setenv("OOMPAH_REPO_MAP_GENERATION_TIMEOUT", "45")
        monkeypatch.setenv("OOMPAH_REPO_MAP_RETAINED_ARTIFACTS", "3")

        cfg = self._config()

        assert cfg.repo_map_enabled is True
        assert cfg.repo_map_token_budget == 4096
        assert cfg.repo_map_languages == ("python", "typescript")
        assert cfg.repo_map_max_file_size == 524288
        assert cfg.repo_map_generation_timeout == 45
        assert cfg.repo_map_retained_artifacts == 3

    @pytest.mark.parametrize(
        ("env_name", "bad_value", "attribute", "expected"),
        [
            ("OOMPAH_REPO_MAP_TOKEN_BUDGET", "0", "repo_map_token_budget", 2000),
            ("OOMPAH_REPO_MAP_MAX_FILE_SIZE", "-1", "repo_map_max_file_size", 1_000_000),
            ("OOMPAH_REPO_MAP_GENERATION_TIMEOUT", "nope", "repo_map_generation_timeout", 120),
            ("OOMPAH_REPO_MAP_RETAINED_ARTIFACTS", "0", "repo_map_retained_artifacts", 5),
        ],
    )
    def test_invalid_numeric_overrides_fall_back_to_safe_defaults(
        self, monkeypatch, env_name, bad_value, attribute, expected
    ):
        monkeypatch.setenv(env_name, bad_value)

        assert getattr(self._config(), attribute) == expected

    def test_invalid_language_policy_falls_back_to_supported_languages(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_REPO_MAP_LANGUAGES", "python,fortran")

        assert set(self._config().repo_map_languages) == {
            "javascript", "markdown", "python", "rust", "typescript", "yaml"
        }

    def test_explicit_disabled_mode_remains_disabled_with_other_tuning(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "false")
        monkeypatch.setenv("OOMPAH_REPO_MAP_TOKEN_BUDGET", "4096")

        cfg = self._config()

        assert cfg.repo_map_enabled is False
        assert cfg.repo_map_token_budget == 4096

    def test_every_repository_map_setting_is_documented_in_env_example(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        documented = {
            line.split("=", 1)[0].lstrip("#").strip()
            for line in env_example.read_text(encoding="utf-8").splitlines()
            if line.lstrip("#").strip().startswith("OOMPAH_REPO_MAP_")
        }

        assert self.ENVIRONMENT_VARIABLES <= documented

    def test_close_gate_env_can_disable_default(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_CLOSE_GATE_ENABLED", "false")
        wf = WorkflowDefinition(config={}, prompt_template="test")

        cfg = ServiceConfig.from_workflow(wf)

        assert cfg.close_gate_enabled is False

    def test_responsiveness_tuning_from_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_DISPATCH_SCAN_LIMIT", "12")
        monkeypatch.setenv("OOMPAH_DISPATCH_READY_BUFFER", "3")
        monkeypatch.setenv("OOMPAH_DUPLICATE_DETECTION_CANDIDATE_LIMIT", "11")
        monkeypatch.setenv("OOMPAH_AUTO_ARCHIVE_BATCH_SIZE", "7")
        monkeypatch.setenv("OOMPAH_AUTO_ARCHIVE_INTERVAL_SECONDS", "30")
        monkeypatch.setenv("OOMPAH_WORKTREE_CLEANUP_BATCH_SIZE", "5")
        monkeypatch.setenv("OOMPAH_MAINTENANCE_STARTUP_DELAY_SECONDS", "9")
        monkeypatch.setenv("OOMPAH_RELEASE_PICK_MAX_RUNTIME_SECONDS", "4")
        monkeypatch.setenv("OOMPAH_MERGED_LABELS_MAX_RUNTIME_SECONDS", "6")
        wf = WorkflowDefinition(config={}, prompt_template="test")

        cfg = ServiceConfig.from_workflow(wf)

        assert cfg.dispatch_scan_limit == 12
        assert cfg.dispatch_ready_buffer == 3
        assert cfg.duplicate_detection_candidate_limit == 11
        assert cfg.auto_archive_batch_size == 7
        assert cfg.auto_archive_interval_seconds == 30
        assert cfg.worktree_cleanup_batch_size == 5
        assert cfg.maintenance_startup_delay_seconds == 9
        assert cfg.release_pick_max_runtime_seconds == 4
        assert cfg.merged_labels_max_runtime_seconds == 6

    def test_server_port_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_PORT", "8090")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.server_port == 8090

    def test_server_port_env_overrides_workflow(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_PORT", "8090")
        wf = WorkflowDefinition(
            config={"server": {"port": 9090}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.server_port == 8090

    def test_blank_server_port_env_disables_dashboard(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_PORT", "")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.server_port is None

    def test_from_workflow_oompah_md_defaults(self):
        wf = WorkflowDefinition(
            config={"tracker": {"kind": "oompah_md"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.tracker_kind == "oompah_md"
        assert cfg.tracker_active_states == ["Open", "Needs CI Fix", "Needs Rebase"]
        assert cfg.tracker_terminal_states == ["Done", "Merged", "Archived"]

    def test_from_workflow_oompah_md_alias(self):
        wf = WorkflowDefinition(
            config={"tracker": {"kind": "oompah.md"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.tracker_kind == "oompah_md"

    def test_budget_window_explicit_in_workflow(self):
        wf = WorkflowDefinition(
            config={"agent": {"budget_window": "hour"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.budget_window == "hour"

    def test_budget_window_invalid_falls_back_to_day(self):
        # A typo in WORKFLOW.md must not silently disable the windowing.
        wf = WorkflowDefinition(
            config={"agent": {"budget_window": "fortnight"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.budget_window == "day"

    def test_budget_window_env_overrides_workflow(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_BUDGET_WINDOW", "week")
        wf = WorkflowDefinition(
            config={"agent": {"budget_window": "hour"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.budget_window == "week"

    def test_budget_timezone_default_is_empty_for_auto_detect(self):
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        # Empty string means "auto-detect host's local timezone".
        assert cfg.budget_timezone == ""

    def test_budget_timezone_explicit_in_workflow(self):
        wf = WorkflowDefinition(
            config={"agent": {"budget_timezone": "America/Los_Angeles"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.budget_timezone == "America/Los_Angeles"

    def test_budget_timezone_env_overrides_workflow(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_BUDGET_TIMEZONE", "Europe/London")
        wf = WorkflowDefinition(
            config={"agent": {"budget_timezone": "America/Los_Angeles"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.budget_timezone == "Europe/London"

    def test_from_workflow_custom(self, tmp_path, monkeypatch):
        # As of oompah-zlz_2-xaj, ServiceConfig.from_workflow consults
        # .oompah/agent_profiles.json (with WORKFLOW.md as a fallback /
        # migration seed). Point the store path at a tmp_path so this
        # unit test doesn't pick up whatever the live orchestrator wrote
        # to the worktree's real .oompah/agent_profiles.json. Without
        # this, running pytest from a worktree with a different default
        # profile in the JSON store would assert against that name
        # instead of the WORKFLOW.md one.
        monkeypatch.setenv(
            "OOMPAH_AGENT_PROFILES_PATH",
            str(tmp_path / "agent_profiles.json"),
        )
        wf = WorkflowDefinition(
            config={
                "tracker": {"kind": "oompah_md", "active_states": ["open"]},
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

    def test_json_profile_store_overrides_workflow_md(
        self, tmp_path, monkeypatch,
    ):
        """When .oompah/agent_profiles.json exists, its profiles override the
        WORKFLOW.md ones (oompah-zlz_2-mif / oompah-zlz_2-xaj).
        """
        from oompah.agent_profile_store import AgentProfileStore

        store_path = tmp_path / "agent_profiles.json"
        store = AgentProfileStore(path=str(store_path))
        store.create({"name": "from-json", "mode": "cli", "command": "claude"})

        # Point ServiceConfig.from_workflow at this store
        monkeypatch.setenv("OOMPAH_AGENT_PROFILES_PATH", str(store_path))

        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "from-workflow-md", "command": "x"},
                    ],
                },
            },
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf)
        names = [p.name for p in cfg.agent_profiles]
        # JSON wins; WORKFLOW.md profile is NOT in the result.
        assert names == ["from-json"]

    def test_workflow_md_used_when_json_absent(self, tmp_path, monkeypatch):
        """Without the JSON store, WORKFLOW.md profiles are used (back-compat)."""
        # Point at a non-existent store file
        monkeypatch.setenv(
            "OOMPAH_AGENT_PROFILES_PATH", str(tmp_path / "not-here.json"),
        )
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "quick", "command": "x"},
                    ],
                },
            },
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert [p.name for p in cfg.agent_profiles] == ["quick"]


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

    def test_valid_oompah_md(self):
        cfg = ServiceConfig(tracker_kind="oompah_md")
        errors = validate_dispatch_config(cfg)
        assert errors == []

    def test_manual_oompah_md_alias_normalizes(self):
        cfg = ServiceConfig(tracker_kind="oompah.md")
        assert cfg.tracker_kind == "oompah_md"
        assert validate_dispatch_config(cfg) == []

    def test_invalid_tracker(self):
        cfg = ServiceConfig(tracker_kind="jira")
        errors = validate_dispatch_config(cfg)
        assert any("Unsupported" in e for e in errors)

    def test_beans_is_not_supported(self):
        cfg = ServiceConfig(tracker_kind="beans")
        errors = validate_dispatch_config(cfg)
        assert any("Unsupported" in e and "beans" in e for e in errors)

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

    def test_startup_env_overrides_inherited_oompah_config(
        self, tmp_path, monkeypatch
    ):
        from oompah.__main__ import _load_startup_env

        monkeypatch.setenv("OOMPAH_MAX_CONCURRENT_AGENTS", "5")
        path = self._make_env(tmp_path, "OOMPAH_MAX_CONCURRENT_AGENTS=16\n")

        count = _load_startup_env(path)

        assert count == 1
        assert os.environ["OOMPAH_MAX_CONCURRENT_AGENTS"] == "16"

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

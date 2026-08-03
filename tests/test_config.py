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
    warn_deprecated_verify_completion_vars,
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
        assert cfg.duplicate_preflight_max_agents == 1
        assert cfg.auto_archive_batch_size == 25
        assert cfg.worktree_cleanup_interval_seconds == 60
        assert cfg.worktree_cleanup_batch_size == 100
        assert cfg.storage_cleanup_interval_seconds == 86400
        assert cfg.storage_cleanup_pressure_min_free_bytes == 5 * 1024**3
        assert cfg.storage_cleanup_pressure_min_free_percent == 5.0
        assert cfg.storage_cleanup_min_age_seconds == 86400
        assert cfg.storage_cleanup_batch_size == 50
        assert cfg.storage_cleanup_max_bytes == 50 * 1024**3
        assert cfg.storage_cleanup_log_retention_seconds == 604800
        assert cfg.coordination_retention_seconds == 2592000
        assert cfg.restart_drain_timeout_seconds == 3600
        assert cfg.quality_gate_timeout_seconds == 3600
        assert cfg.parallel_epic_children_enabled is False
        assert cfg.terminal_lifecycle_reconciliation_batch_size == 4
        assert cfg.prompt_max_comments == 20
        assert cfg.prompt_max_comment_bytes == 32 * 1024
        assert cfg.release_pick_max_runtime_seconds == 15
        assert cfg.merged_labels_max_runtime_seconds == 15
        assert cfg.close_gate_enabled is True
        assert cfg.container_cycle_repair_enabled is True
        assert cfg.gitlab_webhook_public_url is None
        assert cfg.workspace_root  # should have a default

    def test_direct_construction_keeps_duplicate_preflight_inert(self):
        cfg = ServiceConfig()
        assert cfg.duplicate_preflight_max_agents == 0

    def test_parallel_epic_children_comes_from_environment(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_PARALLEL_EPIC_CHILDREN_ENABLED", "true")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        assert ServiceConfig.from_workflow(wf).parallel_epic_children_enabled

    def test_container_cycle_repair_policy_comes_from_environment(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_CONTAINER_CYCLE_REPAIR_ENABLED", "false")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        assert ServiceConfig.from_workflow(wf).container_cycle_repair_enabled is False

    def test_gitlab_webhook_public_url_comes_from_environment(self, monkeypatch):
        monkeypatch.setenv(
            "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL", "https://oompah.example.com/"
        )
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="test"))
        assert cfg.gitlab_webhook_public_url == "https://oompah.example.com/"

    def test_prompt_history_budgets_come_from_environment(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_PROMPT_MAX_COMMENTS", "12")
        monkeypatch.setenv("OOMPAH_PROMPT_MAX_COMMENT_BYTES", "8192")

        cfg = ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )

        assert cfg.prompt_max_comments == 12
        assert cfg.prompt_max_comment_bytes == 8192

    @pytest.mark.parametrize(
        ("name", "value", "attribute", "minimum"),
        [
            ("OOMPAH_PROMPT_MAX_COMMENTS", "1", "prompt_max_comments", 5),
            (
                "OOMPAH_PROMPT_MAX_COMMENT_BYTES",
                "12",
                "prompt_max_comment_bytes",
                1024,
            ),
        ],
    )
    def test_prompt_history_budgets_enforce_retention_minimums(
        self, monkeypatch, name, value, attribute, minimum
    ):
        monkeypatch.setenv(name, value)

        cfg = ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )

        assert getattr(cfg, attribute) == minimum

    def test_prompt_history_settings_are_documented_in_env_example(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        content = env_example.read_text(encoding="utf-8")

        assert "OOMPAH_PROMPT_MAX_COMMENTS=" in content
        assert "OOMPAH_PROMPT_MAX_COMMENT_BYTES=" in content

    def test_terminal_lifecycle_batch_size_is_documented(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        assert "OOMPAH_TERMINAL_LIFECYCLE_RECONCILIATION_BATCH_SIZE=" in (
            env_example.read_text(encoding="utf-8")
        )

    def test_storage_cleanup_settings_come_from_environment(self, monkeypatch):
        values = {
            "OOMPAH_STORAGE_CLEANUP_INTERVAL_SECONDS": "7200",
            "OOMPAH_STORAGE_CLEANUP_PRESSURE_MIN_FREE_BYTES": "123456",
            "OOMPAH_STORAGE_CLEANUP_PRESSURE_MIN_FREE_PERCENT": "7.5",
            "OOMPAH_STORAGE_CLEANUP_MIN_AGE_SECONDS": "3600",
            "OOMPAH_STORAGE_CLEANUP_BATCH_SIZE": "9",
            "OOMPAH_STORAGE_CLEANUP_MAX_BYTES": "987654",
            "OOMPAH_STORAGE_CLEANUP_LOG_RETENTION_SECONDS": "172800",
            "OOMPAH_COORDINATION_RETENTION_SECONDS": "345600",
        }
        for name, value in values.items():
            monkeypatch.setenv(name, value)

        cfg = ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )

        assert cfg.storage_cleanup_interval_seconds == 7200
        assert cfg.storage_cleanup_pressure_min_free_bytes == 123456
        assert cfg.storage_cleanup_pressure_min_free_percent == 7.5
        assert cfg.storage_cleanup_min_age_seconds == 3600
        assert cfg.storage_cleanup_batch_size == 9
        assert cfg.storage_cleanup_max_bytes == 987654
        assert cfg.storage_cleanup_log_retention_seconds == 172800
        assert cfg.coordination_retention_seconds == 345600

    def test_storage_cleanup_settings_are_documented_in_env_example(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        for name in (
            "OOMPAH_STORAGE_CLEANUP_INTERVAL_SECONDS",
            "OOMPAH_STORAGE_CLEANUP_PRESSURE_MIN_FREE_BYTES",
            "OOMPAH_STORAGE_CLEANUP_PRESSURE_MIN_FREE_PERCENT",
            "OOMPAH_STORAGE_CLEANUP_MIN_AGE_SECONDS",
            "OOMPAH_STORAGE_CLEANUP_BATCH_SIZE",
            "OOMPAH_STORAGE_CLEANUP_MAX_BYTES",
            "OOMPAH_STORAGE_CLEANUP_LOG_RETENTION_SECONDS",
            "OOMPAH_COORDINATION_RETENTION_SECONDS",
        ):
            assert f"{name}=" in content

    def test_restart_drain_timeout_comes_from_environment(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_RESTART_DRAIN_TIMEOUT_SECONDS", "5400")

        cfg = ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )

        assert cfg.restart_drain_timeout_seconds == 5400

    def test_restart_drain_timeout_is_documented(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        assert "OOMPAH_RESTART_DRAIN_TIMEOUT_SECONDS=" in env_example.read_text(
            encoding="utf-8"
        )

    def test_quality_gate_timeout_comes_from_environment(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_QUALITY_GATE_TIMEOUT_SECONDS", "5400")

        cfg = ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )

        assert cfg.quality_gate_timeout_seconds == 5400

    def test_quality_gate_timeout_is_documented(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        assert "OOMPAH_QUALITY_GATE_TIMEOUT_SECONDS=" in env_example.read_text(
            encoding="utf-8"
        )

    def test_quality_gate_safety_head_comes_from_environment(self, monkeypatch):
        safety_head = "a" * 40
        monkeypatch.setenv("OOMPAH_QUALITY_GATE_SAFETY_HEAD", safety_head)

        cfg = ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )

        assert cfg.quality_gate_safety_head == safety_head

    def test_quality_gate_safety_head_is_documented(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        assert "OOMPAH_QUALITY_GATE_SAFETY_HEAD=" in env_example.read_text(
            encoding="utf-8"
        )


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
        monkeypatch.setenv("OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS", "3")
        monkeypatch.setenv("OOMPAH_AUTO_ARCHIVE_BATCH_SIZE", "7")
        monkeypatch.setenv("OOMPAH_AUTO_ARCHIVE_INTERVAL_SECONDS", "30")
        monkeypatch.setenv("OOMPAH_WORKTREE_CLEANUP_INTERVAL_SECONDS", "11")
        monkeypatch.setenv("OOMPAH_WORKTREE_CLEANUP_BATCH_SIZE", "5")
        monkeypatch.setenv("OOMPAH_MAINTENANCE_STARTUP_DELAY_SECONDS", "9")
        monkeypatch.setenv("OOMPAH_TERMINAL_LIFECYCLE_RECONCILIATION_BATCH_SIZE", "8")
        monkeypatch.setenv("OOMPAH_RELEASE_PICK_MAX_RUNTIME_SECONDS", "4")
        monkeypatch.setenv("OOMPAH_MERGED_LABELS_MAX_RUNTIME_SECONDS", "6")
        wf = WorkflowDefinition(config={}, prompt_template="test")

        cfg = ServiceConfig.from_workflow(wf)

        assert cfg.dispatch_scan_limit == 12
        assert cfg.dispatch_ready_buffer == 3
        assert cfg.duplicate_detection_candidate_limit == 11
        assert cfg.duplicate_preflight_max_agents == 3
        assert cfg.auto_archive_batch_size == 7
        assert cfg.auto_archive_interval_seconds == 30
        assert cfg.worktree_cleanup_interval_seconds == 11
        assert cfg.worktree_cleanup_batch_size == 5
        assert cfg.maintenance_startup_delay_seconds == 9
        assert cfg.terminal_lifecycle_reconciliation_batch_size == 8
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


class TestAuditDispatchConfiguration:
    """Tests for independent auditor dispatch config (OOMPAH-487)."""

    def setup_method(self):
        """Clear OOMPAH_AUDIT_* env vars so tests run in a clean environment."""
        for key in list(os.environ):
            if key.startswith("OOMPAH_AUDIT_") or key.startswith("OOMPAH_VERIFY_COMPLETION"):
                os.environ.pop(key, None)

    def teardown_method(self):
        """Restore clean environment after each test."""
        for key in list(os.environ):
            if key.startswith("OOMPAH_AUDIT_") or key.startswith("OOMPAH_VERIFY_COMPLETION"):
                os.environ.pop(key, None)

    def test_audit_max_attempts_default(self):
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_max_attempts == 3

    def test_audit_max_attempts_from_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AUDIT_MAX_ATTEMPTS", "5")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_max_attempts == 5

    def test_audit_max_attempts_invalid_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AUDIT_MAX_ATTEMPTS", "notanumber")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_max_attempts == 3

    def test_audit_max_attempts_zero_clamped_to_one(self, monkeypatch):
        # _parse_positive_env_int falls back to default for non-positive, then __post_init__ clamps
        monkeypatch.setenv("OOMPAH_AUDIT_MAX_ATTEMPTS", "0")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_max_attempts >= 1

    def test_audit_attempt_ttl_default(self):
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_attempt_ttl == 3600

    def test_audit_attempt_ttl_from_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AUDIT_ATTEMPT_TTL", "7200")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_attempt_ttl == 7200

    def test_audit_priority_default(self):
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_priority == 100

    def test_audit_priority_from_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AUDIT_PRIORITY", "150")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_priority == 150

    def test_audit_lane_scan_limit_default(self):
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_lane_scan_limit == 32

    def test_audit_lane_scan_limit_from_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AUDIT_LANE_SCAN_LIMIT", "64")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_lane_scan_limit == 64

    def test_audit_lane_scan_limit_zero_allowed(self, monkeypatch):
        # 0 means no cap — should be allowed
        monkeypatch.setenv("OOMPAH_AUDIT_LANE_SCAN_LIMIT", "0")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.audit_lane_scan_limit == 0

    def test_audit_settings_documented_in_env_example(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        assert "OOMPAH_AUDIT_MAX_ATTEMPTS" in content
        assert "OOMPAH_AUDIT_ATTEMPT_TTL" in content
        assert "OOMPAH_AUDIT_PRIORITY" in content
        assert "OOMPAH_AUDIT_LANE_SCAN_LIMIT" in content

    def test_auditor_dispatch_doc_exists(self):
        doc_path = Path(__file__).parents[1] / "docs" / "auditor-dispatch-operations.md"
        assert doc_path.exists(), "docs/auditor-dispatch-operations.md must exist"
        content = doc_path.read_text(encoding="utf-8")
        assert "OOMPAH_AUDIT_MAX_ATTEMPTS" in content
        assert "Needs Human" in content
        assert "override" in content.lower()

    def test_verify_completion_deprecation_warning_when_set(self, monkeypatch, caplog):
        import logging
        from oompah.config import warn_deprecated_verify_completion_vars
        monkeypatch.setenv("OOMPAH_VERIFY_COMPLETION", "true")
        monkeypatch.delenv("OOMPAH_VERIFY_COMPLETION_LLM", raising=False)
        with caplog.at_level(logging.WARNING, logger="oompah.config"):
            warn_deprecated_verify_completion_vars()
        assert "OOMPAH_VERIFY_COMPLETION" in caplog.text
        assert "deprecated" in caplog.text.lower()

    def test_verify_completion_llm_deprecation_warning_when_set(self, monkeypatch, caplog):
        import logging
        from oompah.config import warn_deprecated_verify_completion_vars
        monkeypatch.delenv("OOMPAH_VERIFY_COMPLETION", raising=False)
        monkeypatch.setenv("OOMPAH_VERIFY_COMPLETION_LLM", "false")
        with caplog.at_level(logging.WARNING, logger="oompah.config"):
            warn_deprecated_verify_completion_vars()
        assert "OOMPAH_VERIFY_COMPLETION_LLM" in caplog.text
        assert "deprecated" in caplog.text.lower()

    def test_no_deprecation_warning_when_vars_not_set(self, monkeypatch, caplog):
        import logging
        from oompah.config import warn_deprecated_verify_completion_vars
        monkeypatch.delenv("OOMPAH_VERIFY_COMPLETION", raising=False)
        monkeypatch.delenv("OOMPAH_VERIFY_COMPLETION_LLM", raising=False)
        with caplog.at_level(logging.WARNING, logger="oompah.config"):
            warn_deprecated_verify_completion_vars()
        assert "VERIFY_COMPLETION" not in caplog.text

    def test_from_workflow_emits_deprecation_warning_when_var_set(self, monkeypatch, caplog):
        import logging
        monkeypatch.setenv("OOMPAH_VERIFY_COMPLETION", "false")
        wf = WorkflowDefinition(config={}, prompt_template="test")
        with caplog.at_level(logging.WARNING, logger="oompah.config"):
            ServiceConfig.from_workflow(wf)
        assert "deprecated" in caplog.text.lower()

    def test_verify_completion_vars_documented_in_env_example_as_deprecated(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        # Both variables should be present and marked as deprecated
        assert "OOMPAH_VERIFY_COMPLETION" in content
        assert "OOMPAH_VERIFY_COMPLETION_LLM" in content
        assert "DEPRECATED" in content

    def test_task_epic_workflow_doc_includes_in_validation(self):
        doc_path = Path(__file__).parents[1] / "docs" / "task-epic-workflow.md"
        content = doc_path.read_text(encoding="utf-8")
        assert "In Validation" in content
        # Status table should include In Validation row
        assert "auditor" in content.lower()


class TestHTTPAuthConfiguration:
    """Tests for HTTP Basic auth configuration (OOMPAH-522)."""

    def setup_method(self):
        """Clear OOMPAH_* auth env vars so tests run in a clean environment."""
        for key in list(os.environ):
            if key.startswith("OOMPAH_HTPASSWD"):
                os.environ.pop(key, None)

    def teardown_method(self):
        """Restore clean environment after each test."""
        for key in list(os.environ):
            if key.startswith("OOMPAH_HTPASSWD"):
                os.environ.pop(key, None)

    def test_htpasswd_file_defaults_to_none(self):
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="test"))
        assert cfg.htpasswd_file is None

    def test_htpasswd_file_from_environment(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_HTPASSWD_FILE", "/etc/oompah/.htpasswd")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="test"))
        assert cfg.htpasswd_file == "/etc/oompah/.htpasswd"

    def test_htpasswd_file_from_environment_relative_path(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_HTPASSWD_FILE", "creds.htpasswd")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="test"))
        assert cfg.htpasswd_file == "creds.htpasswd"

    def test_env_file_dir_defaults_to_empty(self):
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="test"))
        # env_file_dir is set by __main__.py, not from workflow
        assert cfg.env_file_dir == ""

    def test_htpasswd_file_documented_in_env_example(self):
        env_example = Path(__file__).parents[1] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        # Verify OOMPAH_HTPASSWD_FILE is documented
        assert "OOMPAH_HTPASSWD_FILE" in content
        # Verify it appears in the HTTP Basic Authentication section
        assert "HTTP Basic" in content and "OOMPAH_HTPASSWD_FILE" in content


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

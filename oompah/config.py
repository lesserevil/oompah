"""Workflow loader and config layer for oompah."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any

import yaml

from oompah.models import AgentProfile, WorkflowDefinition
from oompah.statuses import (
    ARCHIVED,
    DONE,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    OPEN,
)

logger = logging.getLogger(__name__)

DEFAULT_SERVER_PORT = 8080


class WorkflowError(Exception):
    """Raised on workflow file or config errors."""

    def __init__(self, message: str, error_class: str = "workflow_parse_error"):
        super().__init__(message)
        self.error_class = error_class


def load_dotenv(path: str = ".env", override: bool = False) -> int:
    """Load environment variables from a .env file.

    Parses a .env file and sets variables in os.environ. This is a
    zero-dependency implementation that handles the common .env format:

    - Lines starting with # are comments
    - Blank lines are ignored
    - KEY=value (with optional surrounding whitespace)
    - Quoted values: KEY="value with spaces" or KEY='value'
    - Inline comments are NOT stripped (values are taken as-is after the =)
    - $VAR references in values are NOT expanded (values are literal)

    Args:
        path: Path to the .env file. Defaults to ".env" in the current dir.
        override: If True, override existing environment variables.
                  If False (default), skip variables already set.

    Returns:
        Number of variables loaded.
    """
    if not os.path.exists(path):
        return 0

    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.rstrip("\n").rstrip("\r")

                # Skip blank lines and comments
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                # Optional export keyword
                if stripped.startswith("export "):
                    stripped = stripped[7:].lstrip()

                # Split on first =
                if "=" not in stripped:
                    continue

                key, _, raw_value = stripped.partition("=")
                key = key.strip()

                if not key or not _is_valid_env_key(key):
                    logger.debug(".env line %d: skipping invalid key %r", lineno, key)
                    continue

                value = _parse_env_value(raw_value)

                if override or key not in os.environ:
                    os.environ[key] = value
                    count += 1

    except OSError as exc:
        logger.warning("Failed to read .env file %s: %s", path, exc)

    return count


def _is_valid_env_key(key: str) -> bool:
    """Return True if key is a valid environment variable name."""
    return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key))


def _parse_env_value(raw: str) -> str:
    """Parse the value portion of a KEY=value .env line.

    Handles:
    - Double-quoted strings: "value" -> value (with escape sequences)
    - Single-quoted strings: 'value' -> value (literal, no escapes)
    - Unquoted values: value (stripped of leading/trailing whitespace)
    """
    raw = raw.strip()

    # Double-quoted value
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        inner = raw[1:-1]
        # Process basic escape sequences
        inner = inner.replace('\\"', '"')
        inner = inner.replace('\\n', '\n')
        inner = inner.replace('\\r', '\r')
        inner = inner.replace('\\t', '\t')
        inner = inner.replace('\\\\', '\\')
        return inner

    # Single-quoted value (literal, no escapes)
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]

    # Unquoted: strip whitespace
    return raw.strip()


def load_workflow(path: str) -> WorkflowDefinition:
    """Load and parse a WORKFLOW.md file.

    Returns a WorkflowDefinition with config dict and prompt_template string.
    """
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        raise WorkflowError(
            f"Workflow file not found: {path}",
            error_class="missing_workflow_file",
        )
    except OSError as exc:
        raise WorkflowError(
            f"Cannot read workflow file: {exc}",
            error_class="missing_workflow_file",
        )

    config: dict[str, Any] = {}
    prompt_template = content

    if content.startswith("---"):
        lines = content.split("\n")
        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break

        if end_idx is not None:
            front_matter = "\n".join(lines[1:end_idx])
            prompt_template = "\n".join(lines[end_idx + 1 :])

            try:
                parsed = yaml.safe_load(front_matter)
            except yaml.YAMLError as exc:
                raise WorkflowError(
                    f"Invalid YAML front matter: {exc}",
                    error_class="workflow_parse_error",
                )

            if parsed is None:
                config = {}
            elif not isinstance(parsed, dict):
                raise WorkflowError(
                    "YAML front matter must be a map/object",
                    error_class="workflow_front_matter_not_a_map",
                )
            else:
                config = parsed

    return WorkflowDefinition(config=config, prompt_template=prompt_template.strip())


def _resolve_env(value: str) -> str:
    """Resolve $VAR_NAME references in a string value."""
    if isinstance(value, str) and value.startswith("$"):
        var_name = value[1:]
        resolved = os.environ.get(var_name, "")
        return resolved
    return value


def _expand_path(value: str) -> str:
    """Expand ~ and env vars in a path string."""
    if not isinstance(value, str):
        return value
    value = _resolve_env(value)
    if value.startswith("~"):
        value = os.path.expanduser(value)
    if os.sep in value or "/" in value:
        value = os.path.abspath(value)
    return value


def _coerce_int(value: Any, default: int) -> int:
    """Coerce a value to int, falling back to default."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


_BUDGET_WINDOW_VALUES = ("hour", "day", "week")
_PROFILE_MODE_VALUES = ("auto", "api", "cli", "acp")
_TRACKER_KIND_ALIASES = {
    "oompah_md": "oompah_md",
    "oompah.md": "oompah_md",
    "oompah": "oompah_md",
    "github_issues": "github_issues",
    "github-issues": "github_issues",
}
_STRICT_PROFILE_SOURCE_VALUES = ("warn", "strict")
DEFAULT_TRACKER_KIND = "oompah_md"


def _parse_strict_profile_source(value: Any) -> str:
    """Normalize the strict_profile_source flag to one of {warn, strict}.

    Default is "warn" — log a warning and continue if WORKFLOW.md's
    agent.profiles block drifts from the persisted store. "strict"
    refuses to start when the block is present at all (used by
    operators who have completed the migration and want to lock the
    block out from being edited again). Falls back to "warn" on typos.
    """
    if value is None:
        return "warn"
    s = str(value).strip().lower()
    if s in _STRICT_PROFILE_SOURCE_VALUES:
        return s
    logger.warning(
        "Unknown strict_profile_source=%r; falling back to 'warn'. Valid: %s",
        value, ", ".join(_STRICT_PROFILE_SOURCE_VALUES),
    )
    return "warn"


def _profiles_to_canonical(profiles: list[AgentProfile]) -> list[dict]:
    """Render a list of AgentProfile as JSON-shaped dicts sorted by name.

    Used by drift detection to compare WORKFLOW.md's profile block to
    the persisted JSON store regardless of source-order. Two lists are
    "equal" iff they produce the same canonical representation.
    """
    return sorted((p.to_dict() for p in profiles), key=lambda d: d.get("name", ""))


def _profiles_differ(
    workflow_profiles: list[AgentProfile],
    store_profiles: list[AgentProfile],
) -> bool:
    """Return True iff WORKFLOW.md profiles differ from the persisted store.

    Comparison is order-independent and uses the same JSON dict shape
    that gets persisted to .oompah/agent_profiles.json so semantically
    equivalent inputs from either source compare equal.
    """
    return _profiles_to_canonical(workflow_profiles) != _profiles_to_canonical(store_profiles)


def _parse_profile_mode(value: Any) -> str:
    """Normalize an AgentProfile.mode string to one of {auto,api,cli,acp}.
    Falls back to "auto" on anything unrecognized so a typo doesn't
    silently change dispatch routing."""
    if value is None:
        return "auto"
    s = str(value).strip().lower()
    if s in _PROFILE_MODE_VALUES:
        return s
    logger.warning(
        "Unknown agent profile mode=%r; falling back to 'auto'. Valid: %s",
        value, ", ".join(_PROFILE_MODE_VALUES),
    )
    return "auto"


def _parse_budget_window(value: Any) -> str:
    """Normalize a budget-window string to one of {hour, day, week}.
    Falls back to "day" on anything unrecognized so a typo in WORKFLOW.md
    doesn't silently disable the windowing."""
    if value is None:
        return "day"
    s = str(value).strip().lower()
    if s in _BUDGET_WINDOW_VALUES:
        return s
    logger.warning(
        "Unknown budget_window=%r; falling back to 'day'. Valid: %s",
        value, ", ".join(_BUDGET_WINDOW_VALUES),
    )
    return "day"


def _parse_state_list(value: Any, default: list[str]) -> list[str]:
    """Parse a state list from string (comma-separated) or list."""
    if value is None:
        return default
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    return default


def _parse_tracker_kind(value: Any) -> str:
    """Normalize tracker.kind while preserving unsupported values."""
    raw = str(value or DEFAULT_TRACKER_KIND).strip().lower()
    return _TRACKER_KIND_ALIASES.get(raw, raw)


@dataclass
class ServiceConfig:
    """Typed runtime configuration derived from workflow front matter."""

    tracker_kind: str = DEFAULT_TRACKER_KIND
    tracker_active_states: list[str] = field(
        default_factory=lambda: [OPEN, NEEDS_CI_FIX, NEEDS_REBASE]
    )
    tracker_terminal_states: list[str] = field(
        default_factory=lambda: [DONE, MERGED, ARCHIVED]
    )
    poll_interval_ms: int = 120000
    full_sync_interval_ms: int = 300000  # 5 minutes — safety-net full sync
    workspace_root: str = ""
    hooks_after_create: str | None = None
    hooks_before_run: str | None = None
    hooks_after_run: str | None = None
    hooks_before_remove: str | None = None
    hooks_timeout_ms: int = 60000
    max_concurrent_agents: int = 10
    max_turns: int = 20
    max_retry_backoff_ms: int = 300000
    max_concurrent_agents_by_state: dict[str, int] = field(default_factory=dict)
    agent_command: str = "claude --dangerously-skip-permissions"
    turn_timeout_ms: int = 3_600_000
    read_timeout_ms: int = 5000
    stall_timeout_ms: int = 300_000
    stall_turns: int = 10
    escalate_after_attempts: int = 1  # escalate profile after N failed attempts (stall or max_turns)
    decompose_after_attempts: int = 2
    server_port: int | None = DEFAULT_SERVER_PORT
    agent_profiles: list[AgentProfile] = field(default_factory=list)
    # Resolved source for the effective agent_profiles list:
    # - "json" (default): .oompah/agent_profiles.json wins; one-shot
    #   migration from WORKFLOW.md happens on first boot if needed.
    # - "workflow": OOMPAH_AGENT_PROFILES_SOURCE=workflow pins authority
    #   to WORKFLOW.md; the dashboard / future CRUD API treat profiles
    #   as read-only. See docs/agent-profiles.md.
    agent_profiles_source: str = "json"
    budget_limit: float = 0.0
    # Rolling window over which budget_limit is enforced. Once the window
    # elapses (counted from budget_window_start in service_state.json),
    # estimated_cost is reset to zero. Default is "day" so a $50/day cap
    # actually means $50/day, not $50/process-lifetime.
    budget_window: str = "day"  # one of: "hour", "day", "week"
    # IANA timezone name used to align budget window rolls to calendar
    # boundaries (top-of-hour, local midnight, Sunday 00:00). Empty string
    # means "auto-detect host's local zone" (TZ env or /etc/localtime).
    # Set via OOMPAH_BUDGET_TIMEZONE or workflow.agent.budget_timezone.
    # Invalid IANA names fall back to UTC with a logger.warning.
    budget_timezone: str = ""
    # When True, every issue's FIRST dispatch uses the catch-all "default"
    # profile (no issue_type/keyword/priority constraints) and the
    # provider's default_model, regardless of issue type/priority/keywords.
    # On the first retry after a failure the issue escalates directly to the
    # profile that _match_agent_profile() would have originally chosen, then
    # continues up the hierarchy on subsequent failures.
    # Default False: current behaviour (best-match profile on first dispatch).
    default_first_dispatch: bool = False
    # Completion verifier (oompah-zlz_2-y0ns). When True, after a worker
    # exits with reason="normal" AND has moved the issue to a terminal
    # state, the orchestrator runs a two-stage check (regex + LLM)
    # against the issue's "# Acceptance criteria" section. If the diff
    # doesn't satisfy the criteria, the close is rejected: the issue is
    # reopened, a diagnostic comment is posted, and the issue is
    # rescheduled. Default False during initial rollout — flip via
    # OOMPAH_VERIFY_COMPLETION=true after a soak window.
    verify_completion: bool = False
    # When False, the LLM (stage 2) leg of the verifier is skipped.
    # Stage 1 still runs and only rejects close on missing FILE
    # references (not bare symbol misses). Useful for offline /
    # provider-less testing. Default True.
    verify_completion_llm: bool = True
    # Close gate (oompah-zlz_2-gz8w). When True, agent-driven closes
    # are refused when the branch has commits not on the base branch
    # AND no open or merged PR exists. Enabled by default; set
    # OOMPAH_CLOSE_GATE_ENABLED=false to disable explicitly.
    close_gate_enabled: bool = True
    # Strictness for the WORKFLOW.md → AgentProfileStore migration
    # (oompah-zlz_2-hye). One of:
    #   "warn"   — log a warning and surface a dashboard alert when
    #              WORKFLOW.md's agent.profiles block drifts from the
    #              persisted JSON store. Continue with the store as the
    #              source of truth. (Default.)
    #   "strict" — refuse to start when WORKFLOW.md still contains an
    #              agent.profiles block at all. Use this only after the
    #              migration is complete and the block has been deleted
    #              from WORKFLOW.md.
    # Configurable via OOMPAH_STRICT_PROFILE_SOURCE or
    # agent.strict_profile_source in WORKFLOW.md.
    strict_profile_source: str = "warn"
    # True iff WORKFLOW.md's YAML front matter contained an
    # agent.profiles list (even an empty one). Surfaced to __main__.py
    # for strict-mode failure and to the orchestrator for the drift
    # alert. Computed in from_workflow() — never hand-set by callers.
    workflow_has_profiles_block: bool = False
    # True iff WORKFLOW.md's profile block content differs from the
    # JSON store after seed/migration. Computed in from_workflow() —
    # signals to the orchestrator that it should raise a startup
    # alert telling the operator to delete the block.
    agent_profiles_drift: bool = False
    # Staleness threshold for epic branches. When an epic branch's
    # merge-base with its target branch (usually main) is behind by
    # this many commits OR any of those intervening commits touch
    # files the epic also modifies, the branch is considered stale.
    # A staleness alert is surfaced via the dashboard and the
    # orchestrator can dispatch a rebase agent. Set to 0 to disable.
    # Configurable via OOMPAH_EPIC_STALENESS_THRESHOLD_COMMITS or
    # agent.epic_staleness_threshold_commits in WORKFLOW.md.
    epic_staleness_threshold_commits: int = 5
    # Responsiveness controls. These are intentionally environment-only
    # tunables so WORKFLOW.md stays focused on project workflow structure.
    dispatch_scan_limit: int = 64
    dispatch_ready_buffer: int = 8
    duplicate_detection_candidate_limit: int = 64
    auto_archive_batch_size: int = 25
    auto_archive_interval_seconds: int = 300
    worktree_cleanup_batch_size: int = 25
    maintenance_startup_delay_seconds: int = 60
    release_pick_max_runtime_seconds: int = 15
    merged_labels_max_runtime_seconds: int = 15
    # Multi-process service split (TASK-469.5.1).
    # When set, the scheduler process publishes state/issues snapshots to this
    # SQLite database and the API process reads from it.  An empty string means
    # single-process combined mode (default, backward-compatible).
    # Overridden by the OOMPAH_IPC_DB_PATH environment variable.
    ipc_db_path: str = ""

    # Per-project refresh timeout in milliseconds. When fetching
    # candidates, reviews, merged branches, or running states from a
    # project, if the operation takes longer than this, it is
    # cancelled and stale cached data is used instead. 0 disables
    # the timeout (wait indefinitely). Configurable via
    # OOMPAH_PROJECT_REFRESH_TIMEOUT_MS or
    # agent.project_refresh_timeout_ms in WORKFLOW.md.
    project_refresh_timeout_ms: int = 10000

    # Maximum concurrent per-project refresh operations. Limits how
    # many projects can be refreshed simultaneously to avoid
    # overwhelming the system or hitting forge API rate limits.
    # Configurable via OOMPAH_PROJECT_REFRESH_MAX_CONCURRENT or
    # agent.project_refresh_max_concurrent in WORKFLOW.md.
    project_refresh_max_concurrent: int = 4

    # Time-to-live for stale cached data in milliseconds. If cached
    # data is older than this, it will not be used as a fallback and
    # the operation will return empty results instead. 0 disables
    # the TTL (stale cache never expires). Configurable via
    # OOMPAH_PROJECT_STALE_CACHE_TTL_MS or
    # agent.project_stale_cache_ttl_ms in WORKFLOW.md.
    project_stale_cache_ttl_ms: int = 300000

    # Dispatch-loop heartbeat staleness detection (lesserevil/oompah#305).
    # If the dispatch loop has not completed a tick for longer than
    # (full_sync_interval_ms × dispatch_loop_stale_factor) milliseconds,
    # it is considered stale: a dashboard alert is raised and automatic
    # recovery is attempted. A factor of 3.0 means the loop is flagged
    # stale after 3 missed full-sync intervals (15 minutes by default).
    # Set to 0 to disable stale-loop detection entirely.
    # Configurable via OOMPAH_DISPATCH_LOOP_STALE_FACTOR.
    dispatch_loop_stale_factor: float = 3.0

    def __post_init__(self):
        self.tracker_kind = _parse_tracker_kind(self.tracker_kind)
        self.dispatch_scan_limit = max(int(self.dispatch_scan_limit), 0)
        self.dispatch_ready_buffer = max(int(self.dispatch_ready_buffer), 0)
        self.duplicate_detection_candidate_limit = max(
            int(self.duplicate_detection_candidate_limit), 0
        )
        self.auto_archive_batch_size = max(int(self.auto_archive_batch_size), 0)
        self.auto_archive_interval_seconds = max(
            int(self.auto_archive_interval_seconds), 1
        )
        self.worktree_cleanup_batch_size = max(
            int(self.worktree_cleanup_batch_size), 0
        )
        self.maintenance_startup_delay_seconds = max(
            int(self.maintenance_startup_delay_seconds), 0
        )
        self.release_pick_max_runtime_seconds = max(
            int(self.release_pick_max_runtime_seconds), 0
        )
        self.merged_labels_max_runtime_seconds = max(
            int(self.merged_labels_max_runtime_seconds), 0
        )
        if not self.workspace_root:
            self.workspace_root = os.path.join(
                tempfile.gettempdir(), "oompah_workspaces"
            )

    @classmethod
    def from_workflow(
        cls,
        wf: WorkflowDefinition,
        *,
        agent_profiles_path: str | None = None,
    ) -> ServiceConfig:
        """Build ServiceConfig from a parsed WorkflowDefinition.

        ``agent_profiles_path`` overrides the default
        ``.oompah/agent_profiles.json`` location used for the
        WORKFLOW.md → JSON one-shot migration. Tests pass tmp paths
        here so they don't touch the real ``.oompah/`` directory.
        """
        c = wf.config

        tracker = c.get("tracker", {}) or {}
        tracker_kind = _parse_tracker_kind(tracker.get("kind", DEFAULT_TRACKER_KIND))
        active_default = [OPEN, NEEDS_CI_FIX, NEEDS_REBASE]
        terminal_default = [DONE, MERGED, ARCHIVED]
        polling = c.get("polling", {}) or {}
        workspace = c.get("workspace", {}) or {}
        hooks = c.get("hooks", {}) or {}
        agent = c.get("agent", {}) or {}
        codex = c.get("codex", {}) or {}
        server = c.get("server", {}) or {}

        # Parse per-state concurrency map
        raw_by_state = agent.get("max_concurrent_agents_by_state", {}) or {}
        by_state: dict[str, int] = {}
        for state_name, val in raw_by_state.items():
            try:
                n = int(val)
                if n > 0:
                    by_state[str(state_name).strip().lower()] = n
            except (ValueError, TypeError):
                pass

        # Workspace root
        ws_root = workspace.get("root", "")
        if ws_root:
            ws_root = _expand_path(str(ws_root))
        else:
            ws_root = os.path.join(tempfile.gettempdir(), "oompah_workspaces")

       # Parse agent profiles from WORKFLOW.md YAML.
        # These are the *YAML-authored* profiles. Source precedence:
        # .oompah/agent_profiles.json (UI-editable store) wins by default.
        # WORKFLOW.md profiles are the migration seed when the JSON file
        # does not yet exist, and remain authoritative when
        # OOMPAH_AGENT_PROFILES_SOURCE=workflow. See oompah-zlz_2-xaj for
        # the AgentProfileStore design, oompah-zlz_2-mif for the live-reload
        # wiring, and oompah-zlz_2-2y7 for the source-precedence + one-shot
        # migration rules.
        #
        # The "profiles" key being PRESENT in YAML — even as an empty
        # list — is the operator-visible signal that they're still
        # using the legacy block; we surface that as
        # workflow_has_profiles_block so __main__ can fail-loud under
        # strict mode and the orchestrator can show a drift alert.
        # (oompah-zlz_2-hye)
        workflow_has_profiles_block = "profiles" in agent
        raw_profiles = agent.get("profiles", []) or []
        workflow_profiles: list[AgentProfile] = []
        for p in raw_profiles:
            if not isinstance(p, dict):
                continue
            workflow_profiles.append(AgentProfile(
                name=str(p.get("name", "default")),
                command=str(p.get("command", "claude --dangerously-skip-permissions")),
                provider_id=p.get("provider_id"),
                model=p.get("model"),
                model_role=p.get("model_role"),
                cost_per_1k_input=float(p.get("cost_per_1k_input", 0)),  # optional; prefer provider model_costs
                cost_per_1k_output=float(p.get("cost_per_1k_output", 0)),  # optional; prefer provider model_costs
                max_turns=_coerce_int(p.get("max_turns"), None) if p.get("max_turns") is not None else None,
                keywords=[str(k) for k in (p.get("keywords", []) or [])],
                issue_types=[str(t) for t in (p.get("issue_types", []) or [])],
                min_priority=_coerce_int(p.get("min_priority"), None) if p.get("min_priority") is not None else None,
                max_priority=_coerce_int(p.get("max_priority"), None) if p.get("max_priority") is not None else None,
                mode=_parse_profile_mode(p.get("mode")),
            ))

       # Resolve effective profiles. Source precedence + opt-out env var
        # live in oompah.agent_profile_store.resolve_agent_profiles; lazy
        # import avoids any chance of a circular import at module load.
        from oompah.agent_profile_store import (
            DEFAULT_AGENT_PROFILES_PATH,
            resolve_agent_profiles,
        )
        effective_store_path = (
            agent_profiles_path
            or os.environ.get("OOMPAH_AGENT_PROFILES_PATH")
            or DEFAULT_AGENT_PROFILES_PATH
        )
        profiles, profiles_source, migrated = resolve_agent_profiles(
            workflow_profiles,
            store_path=effective_store_path,
        )
        # Re-normalize mode through the parser so values that were
        # written to JSON via a prior version of the code still get
        # the same fallback-on-typo behaviour as WORKFLOW.md profiles.
        for p in profiles:
            p.mode = _parse_profile_mode(p.mode)
        # Drift detection (oompah-zlz_2-hye). Compare the parsed
        # WORKFLOW.md block (workflow_profiles) against the effective
        # profiles resolved by the store. They will be identical
        # immediately after migration; they diverge once the operator
        # edits either side. The store wins regardless; this flag
        # lets __main__ / orchestrator surface a warning telling the
        # operator to delete the stale block.
        agent_profiles_drift = False
        if (
            workflow_has_profiles_block
            and workflow_profiles
            and not migrated
            and profiles_source == "json"
            and _profiles_differ(workflow_profiles, profiles)
        ):
            agent_profiles_drift = True
        if profiles_source == "workflow":
            if profiles:
                logger.info(
                    "AgentProfile source: WORKFLOW.md (pinned via "
                    "OOMPAH_AGENT_PROFILES_SOURCE=workflow; %d profile(s))",
                    len(profiles),
                )
        elif migrated:
            logger.info(
                "AgentProfile source: %s (just migrated from WORKFLOW.md; "
                "%d profile(s))",
                effective_store_path, len(profiles),
            )
        elif profiles:
            logger.info(
                "AgentProfile source: %s (%d profile(s))",
                effective_store_path, len(profiles),
            )

        budget_limit = float(agent.get("budget_limit", 0) or 0)

        # Environment variables take precedence over WORKFLOW.md values.
        # Helper: env var > workflow yaml > default
        def _env_bool(env_key: str, yaml_val: Any, default: bool) -> bool:
            """Resolve a boolean config value: env var > YAML > default.

            Env var strings "1", "true", "yes" (case-insensitive) are True;
            "0", "false", "no" are False; other values fall back to yaml_val.
            """
            raw = os.environ.get(env_key)
            if raw is not None:
                return raw.strip().lower() in ("1", "true", "yes")
            if yaml_val is None:
                return default
            if isinstance(yaml_val, bool):
                return yaml_val
            return str(yaml_val).strip().lower() in ("1", "true", "yes")

        def _env_int(env_key: str, yaml_val: Any, default: int) -> int:
            return _coerce_int(os.environ.get(env_key, yaml_val), default)

        def _env_float(env_key: str, yaml_val: Any, default: float) -> float:
            raw = os.environ.get(env_key, yaml_val)
            if raw is None:
                return default
            try:
                return float(raw)
            except (ValueError, TypeError):
                return default

        def _env_str(env_key: str, yaml_val: Any, default: str) -> str:
            return os.environ.get(env_key) or (str(yaml_val) if yaml_val is not None else default)

        # Server port: env > yaml > default. An explicit empty env value or
        # YAML null disables the HTTP dashboard.
        raw_port = os.environ.get(
            "OOMPAH_SERVER_PORT",
            server.get("port", DEFAULT_SERVER_PORT),
        )
        server_port = _coerce_int(raw_port, None) if raw_port is not None else None

        # Workspace root: env > yaml > tempdir
        env_ws = os.environ.get("OOMPAH_WORKSPACE_ROOT")
        if env_ws:
            ws_root = _expand_path(env_ws)

        return cls(
            tracker_kind=tracker_kind,
            tracker_active_states=_parse_state_list(
                tracker.get("active_states"), active_default
            ),
            tracker_terminal_states=_parse_state_list(
                tracker.get("terminal_states"), terminal_default
            ),
            poll_interval_ms=_env_int("OOMPAH_POLL_INTERVAL_MS", polling.get("interval_ms"), 120000),
            full_sync_interval_ms=_env_int("OOMPAH_FULL_SYNC_INTERVAL_MS", polling.get("full_sync_interval_ms"), 300000),
            workspace_root=ws_root,
            hooks_after_create=hooks.get("after_create"),
            hooks_before_run=hooks.get("before_run"),
            hooks_after_run=hooks.get("after_run"),
            hooks_before_remove=hooks.get("before_remove"),
            hooks_timeout_ms=_env_int("OOMPAH_HOOKS_TIMEOUT_MS", hooks.get("timeout_ms"), 60000),
            max_concurrent_agents=_env_int("OOMPAH_MAX_CONCURRENT_AGENTS", agent.get("max_concurrent_agents"), 10),
            max_turns=_env_int("OOMPAH_MAX_TURNS", agent.get("max_turns"), 200),
            max_retry_backoff_ms=_env_int("OOMPAH_MAX_RETRY_BACKOFF_MS", agent.get("max_retry_backoff_ms"), 300000),
            max_concurrent_agents_by_state=by_state,
            agent_command=_env_str("OOMPAH_AGENT_COMMAND", codex.get("command"), "claude --dangerously-skip-permissions"),
            turn_timeout_ms=_env_int("OOMPAH_TURN_TIMEOUT_MS", codex.get("turn_timeout_ms"), 3_600_000),
            read_timeout_ms=_env_int("OOMPAH_READ_TIMEOUT_MS", codex.get("read_timeout_ms"), 5000),
            stall_timeout_ms=_env_int("OOMPAH_STALL_TIMEOUT_MS", codex.get("stall_timeout_ms"), 300_000),
            stall_turns=_env_int("OOMPAH_STALL_TURNS", agent.get("stall_turns"), 10),
            escalate_after_attempts=_env_int("OOMPAH_ESCALATE_AFTER_ATTEMPTS", agent.get("escalate_after_attempts"), 1),
            decompose_after_attempts=_env_int("OOMPAH_DECOMPOSE_AFTER_ATTEMPTS", agent.get("decompose_after_attempts"), 2),
            server_port=server_port,
            agent_profiles=profiles,
            agent_profiles_source=profiles_source,
            budget_limit=_env_float("OOMPAH_BUDGET_LIMIT", agent.get("budget_limit"), 0.0),
            budget_window=_parse_budget_window(
                _env_str("OOMPAH_BUDGET_WINDOW", agent.get("budget_window"), "day"),
            ),
            budget_timezone=_env_str(
                "OOMPAH_BUDGET_TIMEZONE", agent.get("budget_timezone"), "",
            ),
            default_first_dispatch=_env_bool(
                "OOMPAH_DEFAULT_FIRST_DISPATCH",
                agent.get("default_first_dispatch"),
                False,
            ),
          verify_completion=_env_bool(
                "OOMPAH_VERIFY_COMPLETION",
                agent.get("verify_completion"),
                False,
            ),
            verify_completion_llm=_env_bool(
                "OOMPAH_VERIFY_COMPLETION_LLM",
                agent.get("verify_completion_llm"),
                True,
            ),
            close_gate_enabled=_env_bool(
                "OOMPAH_CLOSE_GATE_ENABLED",
                agent.get("close_gate_enabled"),
                True,
            ),
            strict_profile_source=_parse_strict_profile_source(
                _env_str(
                    "OOMPAH_STRICT_PROFILE_SOURCE",
                    agent.get("strict_profile_source"),
                    "warn",
                ),
            ),
            workflow_has_profiles_block=workflow_has_profiles_block,
            agent_profiles_drift=agent_profiles_drift,
            epic_staleness_threshold_commits=_env_int(
                "OOMPAH_EPIC_STALENESS_THRESHOLD_COMMITS",
                agent.get("epic_staleness_threshold_commits"),
                5,
            ),
            dispatch_scan_limit=_env_int("OOMPAH_DISPATCH_SCAN_LIMIT", None, 64),
            dispatch_ready_buffer=_env_int("OOMPAH_DISPATCH_READY_BUFFER", None, 8),
            duplicate_detection_candidate_limit=_env_int(
                "OOMPAH_DUPLICATE_DETECTION_CANDIDATE_LIMIT", None, 64
            ),
            auto_archive_batch_size=_env_int(
                "OOMPAH_AUTO_ARCHIVE_BATCH_SIZE", None, 25
            ),
            auto_archive_interval_seconds=_env_int(
                "OOMPAH_AUTO_ARCHIVE_INTERVAL_SECONDS", None, 300
            ),
            worktree_cleanup_batch_size=_env_int(
                "OOMPAH_WORKTREE_CLEANUP_BATCH_SIZE", None, 25
            ),
            maintenance_startup_delay_seconds=_env_int(
                "OOMPAH_MAINTENANCE_STARTUP_DELAY_SECONDS", None, 60
            ),
            release_pick_max_runtime_seconds=_env_int(
                "OOMPAH_RELEASE_PICK_MAX_RUNTIME_SECONDS", None, 15
            ),
            merged_labels_max_runtime_seconds=_env_int(
                "OOMPAH_MERGED_LABELS_MAX_RUNTIME_SECONDS", None, 15
            ),
            ipc_db_path=_env_str("OOMPAH_IPC_DB_PATH", None, ""),
            project_refresh_timeout_ms=_env_int(
                "OOMPAH_PROJECT_REFRESH_TIMEOUT_MS",
                agent.get("project_refresh_timeout_ms"),
                10000,
            ),
            project_refresh_max_concurrent=_env_int(
                "OOMPAH_PROJECT_REFRESH_MAX_CONCURRENT",
                agent.get("project_refresh_max_concurrent"),
                4,
            ),
            project_stale_cache_ttl_ms=_env_int(
                "OOMPAH_PROJECT_STALE_CACHE_TTL_MS",
                agent.get("project_stale_cache_ttl_ms"),
                300000,
            ),
            dispatch_loop_stale_factor=_env_float(
                "OOMPAH_DISPATCH_LOOP_STALE_FACTOR",
                agent.get("dispatch_loop_stale_factor"),
                3.0,
            ),
        )


def validate_dispatch_config(config: ServiceConfig) -> list[str]:
    """Validate config for dispatch readiness. Returns list of error strings."""
    from oompah.tracker import ADAPTER_REGISTRY

    errors: list[str] = []

    if not config.tracker_kind:
        errors.append("tracker.kind is required")
    elif _parse_tracker_kind(config.tracker_kind) not in ADAPTER_REGISTRY:
        registered = sorted(ADAPTER_REGISTRY)
        errors.append(
            f"Unsupported tracker.kind: {config.tracker_kind!r}."
            f" Registered adapters: {registered}"
        )

    if not config.agent_command:
        errors.append("codex.command (agent_command) must be non-empty")

    return errors

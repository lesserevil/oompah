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

logger = logging.getLogger(__name__)


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


def _parse_state_list(value: Any, default: list[str]) -> list[str]:
    """Parse a state list from string (comma-separated) or list."""
    if value is None:
        return default
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    return default


@dataclass
class ServiceConfig:
    """Typed runtime configuration derived from workflow front matter."""

    tracker_kind: str = "beads"
    tracker_active_states: list[str] = field(
        default_factory=lambda: ["open", "in_progress"]
    )
    tracker_terminal_states: list[str] = field(
        default_factory=lambda: ["closed"]
    )
    poll_interval_ms: int = 30000
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
    stall_turns: int = 5
    decompose_after_attempts: int = 3
    server_port: int | None = None
    agent_profiles: list[AgentProfile] = field(default_factory=list)
    budget_limit: float = 0.0

    def __post_init__(self):
        if not self.workspace_root:
            self.workspace_root = os.path.join(
                tempfile.gettempdir(), "oompah_workspaces"
            )

    @classmethod
    def from_workflow(cls, wf: WorkflowDefinition) -> ServiceConfig:
        """Build ServiceConfig from a parsed WorkflowDefinition."""
        c = wf.config

        tracker = c.get("tracker", {}) or {}
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

        # Parse agent profiles
        raw_profiles = agent.get("profiles", []) or []
        profiles: list[AgentProfile] = []
        for p in raw_profiles:
            if not isinstance(p, dict):
                continue
            profiles.append(AgentProfile(
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
            ))

        budget_limit = float(agent.get("budget_limit", 0) or 0)

        return cls(
            tracker_kind=str(tracker.get("kind", "beads")),
            tracker_active_states=_parse_state_list(
                tracker.get("active_states"), ["open", "in_progress"]
            ),
            tracker_terminal_states=_parse_state_list(
                tracker.get("terminal_states"), ["closed"]
            ),
            poll_interval_ms=_coerce_int(polling.get("interval_ms"), 30000),
            full_sync_interval_ms=_coerce_int(polling.get("full_sync_interval_ms"), 300000),
            workspace_root=ws_root,
            hooks_after_create=hooks.get("after_create"),
            hooks_before_run=hooks.get("before_run"),
            hooks_after_run=hooks.get("after_run"),
            hooks_before_remove=hooks.get("before_remove"),
            hooks_timeout_ms=_coerce_int(hooks.get("timeout_ms"), 60000),
            max_concurrent_agents=_coerce_int(
                agent.get("max_concurrent_agents"), 10
            ),
            max_turns=_coerce_int(agent.get("max_turns"), 200),
            max_retry_backoff_ms=_coerce_int(
                agent.get("max_retry_backoff_ms"), 300000
            ),
            max_concurrent_agents_by_state=by_state,
            agent_command=str(
                codex.get("command", "claude --dangerously-skip-permissions")
            ),
            turn_timeout_ms=_coerce_int(codex.get("turn_timeout_ms"), 3_600_000),
            read_timeout_ms=_coerce_int(codex.get("read_timeout_ms"), 5000),
            stall_timeout_ms=_coerce_int(codex.get("stall_timeout_ms"), 300_000),
            stall_turns=_coerce_int(agent.get("stall_turns"), 5),
            decompose_after_attempts=_coerce_int(agent.get("decompose_after_attempts"), 3),
            server_port=_coerce_int(server.get("port"), None) if server.get("port") is not None else None,
            agent_profiles=profiles,
            budget_limit=budget_limit,
        )


def validate_dispatch_config(config: ServiceConfig) -> list[str]:
    """Validate config for dispatch readiness. Returns list of error strings."""
    errors: list[str] = []

    if not config.tracker_kind:
        errors.append("tracker.kind is required")
    elif config.tracker_kind not in ("beads",):
        errors.append(f"Unsupported tracker.kind: {config.tracker_kind}")

    if not config.agent_command:
        errors.append("codex.command (agent_command) must be non-empty")

    return errors

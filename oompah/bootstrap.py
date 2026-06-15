"""Service bootstrap for oompah.

Provides :func:`setup_services` which validates configuration and creates
all long-lived service objects.  Both the uvicorn path
(``oompah/__main__._run``) and the Granian ASGI lifespan
(``oompah/server._lifespan``) call this so validation logic lives in one
place.

The key difference between the two startup paths is how they handle
failure:

* **uvicorn path** — catches :class:`StartupError` and calls
  ``sys.exit(1)``.  This is the same behaviour as before: the
  ``SystemExit`` propagates cleanly through ``asyncio.run()`` to
  ``main()``.

* **Granian lifespan path** — catches :class:`StartupError` and calls
  ``os._exit(1)``.  ``sys.exit(1)`` inside an asyncio ``Task`` raises
  ``SystemExit`` which escapes the coroutine and triggers Python's
  "Task exception was never retrieved" warning.  Granian may then
  respawn the worker.  ``os._exit(1)`` terminates the process immediately
  without unwinding the Python stack, so the exception never escapes the
  task and the Granian supervisor sees a clean (non-respawn) exit.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from oompah.agent_profile_store import AgentProfileStore
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore
    from oompah.providers import ProviderStore
    from oompah.roles import RoleStore
    from oompah.webhooks import WebhookForwarder

logger = logging.getLogger(__name__)


class StartupError(RuntimeError):
    """Raised by :func:`setup_services` on config/backlog/profile validation
    failure.

    Replaces direct ``sys.exit(1)`` calls so callers can choose the
    appropriate termination strategy:

    * uvicorn path → ``sys.exit(1)`` (propagates through asyncio.run)
    * Granian lifespan → ``os._exit(1)`` (bypasses asyncio task exception
      machinery entirely)
    """


@dataclass
class Services:
    """Container for all long-lived service objects created by
    :func:`setup_services`.

    Callers are responsible for *starting* the services (e.g. scheduling
    orchestrator.run(), calling webhook_forwarder.start(), etc.) after
    this function returns.
    """

    config: "ServiceConfig"
    orchestrator: "Orchestrator"
    provider_store: "ProviderStore"
    project_store: "ProjectStore"
    agent_profile_store: "AgentProfileStore"
    role_store: "RoleStore"
    webhook_forwarder: "WebhookForwarder"
    port: int | None
    workflow_path: str
    workflow: object  # oompah.config.WorkflowDefinition, typed loosely


def attach_webhook_forwarder_alerts(
    orchestrator: "Orchestrator",
    webhook_forwarder: "WebhookForwarder",
) -> None:
    """Route webhook-forwarder health updates into orchestrator alerts."""
    from oompah.webhooks import build_webhook_forwarder_alerts

    def _on_forwarder_status(status: dict[str, Any]) -> None:
        orchestrator._alerts = [
            alert
            for alert in orchestrator._alerts
            if not (
                str(alert.get("source", "")) == "webhook_forwarder"
                or str(alert.get("source", "")).startswith("webhook_forwarder:")
            )
        ]
        orchestrator._alerts.extend(build_webhook_forwarder_alerts(status))

    webhook_forwarder._status_callback = _on_forwarder_status


async def setup_services(
    workflow_path: str,
    cli_port: int | None = None,
    start_paused: bool = False,
) -> "Services":
    """Load config, validate, and create all service objects.

    All config/backlog/profile validation errors raise
    :class:`StartupError` with a descriptive message (and the original
    exception chained via ``__cause__``).  Error details are also emitted
    via ``logger.error`` before raising so they appear in the log
    regardless of how the caller handles the exception.

    Does **not** start or run the services — that is the caller's
    responsibility.

    Parameters
    ----------
    workflow_path:
        Absolute path to ``WORKFLOW.md``.
    cli_port:
        HTTP port override from ``--port`` CLI argument (``None`` means
        fall back to config).
    start_paused:
        When ``True`` force the orchestrator to boot in paused state,
        overriding any persisted state.

    Returns
    -------
    Services
        All initialised service objects, ready to be started.

    Raises
    ------
    StartupError
        On any validation failure.  The exception message is human-readable
        and suitable for direct use in a log line.
    """
    # Keep imports local so this module can be imported cheaply (e.g. from
    # tests) without pulling in the whole app immediately.
    from oompah.backlog_compat import (
        BacklogCompatibilityError,
        ensure_backlog_compatible,
    )
    from oompah.agent_profile_store import AgentProfileStore
    from oompah.config import (
        ServiceConfig,
        WorkflowError,
        load_workflow,
        validate_dispatch_config,
    )
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore
    from oompah.providers import ProviderStore
    from oompah.roles import RoleStore, migrate_agent_profiles_to_roles
    from oompah.webhooks import WebhookForwarder

    # ------------------------------------------------------------------
    # 1. Load and parse WORKFLOW.md
    # ------------------------------------------------------------------
    try:
        workflow = load_workflow(workflow_path)
    except WorkflowError as exc:
        logger.error("Failed to load workflow: %s", exc)
        raise StartupError(f"Failed to load workflow: {exc}") from exc

    config = ServiceConfig.from_workflow(workflow)

    # ------------------------------------------------------------------
    # 2. Validate dispatch config
    # ------------------------------------------------------------------
    errors = validate_dispatch_config(config)
    if errors:
        for err in errors:
            logger.error("Config validation error: %s", err)
        raise StartupError("Config validation failed: " + "; ".join(errors))

    # ------------------------------------------------------------------
    # 3. Backlog.md compatibility check
    # ------------------------------------------------------------------
    try:
        compat = ensure_backlog_compatible(os.path.dirname(workflow_path))
        if compat.changed:
            logger.info(
                "Updated Backlog.md config at %s (%s)",
                compat.config_path,
                ", ".join(compat.migrations),
            )
    except BacklogCompatibilityError as exc:
        logger.error("Backlog.md compatibility error: %s", exc)
        raise StartupError(f"Backlog.md compatibility error: {exc}") from exc

    # ------------------------------------------------------------------
    # 4. Strict profile-source mode check
    # ------------------------------------------------------------------
    if (
        config.strict_profile_source == "strict"
        and config.workflow_has_profiles_block
    ):
        logger.error(
            "Strict profile-source mode is enabled and WORKFLOW.md still "
            "contains an agent.profiles block. This section is no longer "
            "authoritative; profiles are managed via the dashboard "
            "(/api/v1/agent-profiles) and stored in "
            ".oompah/agent_profiles.json. Delete the agent.profiles "
            "block from %s to start. To disable this strict check, set "
            "OOMPAH_STRICT_PROFILE_SOURCE=warn (the default).",
            workflow_path,
        )
        raise StartupError(
            "Strict profile-source mode: WORKFLOW.md agent.profiles block "
            f"must be removed from {workflow_path}"
        )

    # ------------------------------------------------------------------
    # 5. Non-fatal drift warning
    # ------------------------------------------------------------------
    if config.agent_profiles_drift:
        logger.warning(
            "WORKFLOW.md agent.profiles block detected and differs from "
            "persisted profile store — using the persisted store. Delete "
            "the agent.profiles section from %s to clear this warning.",
            workflow_path,
        )

    # ------------------------------------------------------------------
    # 6. Resolve port
    # ------------------------------------------------------------------
    port = cli_port or config.server_port

    # ------------------------------------------------------------------
    # 7. Create shared stores
    # ------------------------------------------------------------------
    provider_store = ProviderStore()
    project_store = ProjectStore()
    # AgentProfileStore: ServiceConfig.from_workflow already created / migrated
    # the JSON file when it parsed the workflow above.  Re-open the same path
    # here so the orchestrator and the HTTP API share a single in-memory store.
    agent_profile_store = AgentProfileStore()
    # RoleStore: first-run migration copies existing AgentProfile provider/model
    # into RoleStore slots — idempotent on subsequent boots.
    role_store = RoleStore(provider_store=provider_store)
    if role_store.is_empty:
        migrate_agent_profiles_to_roles(
            role_store,
            agent_profile_store.list_all(),
            provider_store=provider_store,
        )

    webhook_forwarder = WebhookForwarder(
        project_store=project_store,
        server_port=port,
    )

    # ------------------------------------------------------------------
    # 8. Sync managed-project sources before dispatch
    # ------------------------------------------------------------------
    projects = project_store.list_all()
    if projects:
        logger.info(
            "Syncing sources for %d project(s) before dispatch...",
            len(projects),
        )
        sync_results = project_store.sync_all_sources()
        for pid, st in sync_results.items():
            name = next((p.name for p in projects if p.id == pid), pid)
            logger.info(
                "Startup sync %s: git=%s backlog=%s",
                name,
                st.get("git", "?"),
                st.get("backlog", "?"),
            )

    # ------------------------------------------------------------------
    # 9. Ensure required GitHub tracker labels per project
    # ------------------------------------------------------------------
    label_bootstrap_results: dict[str, Any] = {}
    if projects:
        from oompah.label_bootstrap import ensure_github_labels

        label_bootstrap_results = ensure_github_labels(projects)
        for pid, result in label_bootstrap_results.items():
            name = next((p.name for p in projects if p.id == pid), pid)
            status_summary = result.status_summary()
            if result.success:
                logger.info("GitHub label bootstrap %s: %s", name, status_summary)
            else:
                logger.warning("GitHub label bootstrap %s: %s", name, status_summary)

    # ------------------------------------------------------------------
    # 10. Ensure Backlog task-change webhook hooks per project
    # ------------------------------------------------------------------
    if projects:
        from oompah.backlog_webhooks import ensure_backlog_webhooks

        server_base_url = (
            os.environ.get("OOMPAH_SERVER_URL") or f"http://localhost:{port}"
        )
        webhook_results = ensure_backlog_webhooks(project_store, server_base_url)
        for pid, status in webhook_results.items():
            name = next((p.name for p in projects if p.id == pid), pid)
            if status.startswith("ok") or status.startswith("skipped"):
                logger.info("Backlog webhook hook %s: %s", name, status)
            else:
                logger.warning("Backlog webhook hook %s: %s", name, status)

    # ------------------------------------------------------------------
    # 11. Create orchestrator
    # ------------------------------------------------------------------
    orchestrator = Orchestrator(
        config,
        workflow_path,
        provider_store=provider_store,
        project_store=project_store,
        agent_profile_store=agent_profile_store,
        role_store=role_store,
    )
    orchestrator.set_prompt_template(workflow.prompt_template)
    attach_webhook_forwarder_alerts(orchestrator, webhook_forwarder)
    if label_bootstrap_results:
        from oompah.label_bootstrap import build_label_bootstrap_alerts

        orchestrator._alerts = [
            alert
            for alert in orchestrator._alerts
            if not str(alert.get("source", "")).startswith("label_bootstrap:")
        ]
        orchestrator._alerts.extend(
            build_label_bootstrap_alerts(label_bootstrap_results)
        )

    # Apply --paused flag
    if start_paused and not orchestrator.is_paused:
        orchestrator._paused = True
        orchestrator._save_paused_state()
        logger.info("Booting paused (--paused flag)")
    elif orchestrator.is_paused:
        logger.info("Booting paused (persisted state)")

    return Services(
        config=config,
        orchestrator=orchestrator,
        provider_store=provider_store,
        project_store=project_store,
        agent_profile_store=agent_profile_store,
        role_store=role_store,
        webhook_forwarder=webhook_forwarder,
        port=port,
        workflow_path=workflow_path,
        workflow=workflow,
    )

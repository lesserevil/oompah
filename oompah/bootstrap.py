"""Service bootstrap — shared between the uvicorn and Granian startup paths.

Extracts the service-wiring from ``oompah.__main__._run`` so both the
uvicorn coroutine path and the Granian ASGI-lifespan path can set up
services in an identical, tested way.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from oompah.agent_profile_store import AgentProfileStore
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore
    from oompah.providers import ProviderStore
    from oompah.roles import RoleStore
    from oompah.webhooks import WebhookForwarder

logger = logging.getLogger("oompah")


@dataclasses.dataclass
class Services:
    """Bundle of all wired service instances, ready to be started."""

    config: "ServiceConfig"
    workflow_path: str
    port: Optional[int]
    orchestrator: "Orchestrator"
    provider_store: "ProviderStore"
    project_store: "ProjectStore"
    agent_profile_store: "AgentProfileStore"
    role_store: "RoleStore"
    webhook_forwarder: "WebhookForwarder"


def setup_services(
    workflow_path: str,
    cli_port: Optional[int] = None,
    start_paused: bool = False,
) -> Services:
    """Load workflow and wire all services.

    Returns a :class:`Services` bundle ready to be started (orchestrator not
    yet running, webhook forwarder not yet started).  On invalid configuration
    calls :func:`sys.exit` — same behaviour as the original
    ``__main__._run``.

    This function is **synchronous** because all of the underlying I/O (file
    reads, store construction, Backlog compat checks, project sync) is
    performed synchronously; no awaits are needed in the setup phase.
    """
    from oompah.backlog_compat import BacklogCompatibilityError, ensure_backlog_compatible
    from oompah.agent_profile_store import AgentProfileStore
    from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore
    from oompah.providers import ProviderStore
    from oompah.roles import RoleStore, migrate_agent_profiles_to_roles
    from oompah.webhooks import WebhookForwarder

    # ------------------------------------------------------------------
    # Load and validate workflow
    # ------------------------------------------------------------------
    try:
        workflow = load_workflow(workflow_path)
    except WorkflowError as exc:
        logger.error("Failed to load workflow: %s", exc)
        sys.exit(1)

    config = ServiceConfig.from_workflow(workflow)

    errors = validate_dispatch_config(config)
    if errors:
        for err in errors:
            logger.error("Config validation error: %s", err)
        sys.exit(1)

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
        sys.exit(1)

    # Strict-mode profile source check (oompah-zlz_2-hye).
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
        sys.exit(1)

    # Drift warning (oompah-zlz_2-hye).
    if config.agent_profiles_drift:
        logger.warning(
            "WORKFLOW.md agent.profiles block detected and differs from "
            "persisted profile store — using the persisted store. Delete "
            "the agent.profiles section from %s to clear this warning.",
            workflow_path,
        )

    # ------------------------------------------------------------------
    # Determine port
    # ------------------------------------------------------------------
    port = cli_port or config.server_port

    # ------------------------------------------------------------------
    # Create service instances
    # ------------------------------------------------------------------
    provider_store = ProviderStore()
    project_store = ProjectStore()
    agent_profile_store = AgentProfileStore()
    role_store = RoleStore(provider_store=provider_store)
    if role_store.is_empty:
        migrate_agent_profiles_to_roles(
            role_store, agent_profile_store.list_all(),
            provider_store=provider_store,
        )

    webhook_forwarder = WebhookForwarder(project_store=project_store)

    # ------------------------------------------------------------------
    # Startup sync and Backlog webhook hooks (best-effort)
    # ------------------------------------------------------------------
    projects = project_store.list_all()
    if projects:
        logger.info("Syncing sources for %d project(s) before dispatch...", len(projects))
        sync_results = project_store.sync_all_sources()
        for pid, st in sync_results.items():
            name = next((p.name for p in projects if p.id == pid), pid)
            logger.info(
                "Startup sync %s: git=%s backlog=%s",
                name, st.get("git", "?"), st.get("backlog", "?"),
            )

    if projects:
        from oompah.backlog_webhooks import ensure_backlog_webhooks

        server_base_url = (
            os.environ.get("OOMPAH_SERVER_URL")
            or f"http://localhost:{port}"
        )
        webhook_results = ensure_backlog_webhooks(project_store, server_base_url)
        for pid, status in webhook_results.items():
            name = next((p.name for p in projects if p.id == pid), pid)
            if status.startswith("ok") or status.startswith("skipped"):
                logger.info("Backlog webhook hook %s: %s", name, status)
            else:
                logger.warning("Backlog webhook hook %s: %s", name, status)

    # ------------------------------------------------------------------
    # Create orchestrator
    # ------------------------------------------------------------------
    orchestrator = Orchestrator(
        config, workflow_path,
        provider_store=provider_store,
        project_store=project_store,
        agent_profile_store=agent_profile_store,
        role_store=role_store,
    )
    orchestrator.set_prompt_template(workflow.prompt_template)

    if start_paused and not orchestrator.is_paused:
        orchestrator._paused = True
        orchestrator._save_paused_state()
        logger.info("Booting paused (--paused flag)")
    elif orchestrator.is_paused:
        logger.info("Booting paused (persisted state)")

    # ------------------------------------------------------------------
    # Wire forwarder health into orchestrator alerts
    # ------------------------------------------------------------------
    def _on_forwarder_status(status: dict) -> None:
        orchestrator._alerts = [
            a for a in orchestrator._alerts
            if a.get("source") != "webhook_forwarder"
        ]
        if not status.get("available"):
            detail = status.get("detail") or "gh-webhook extension unavailable"
            orchestrator._alerts.append({
                "level": "warning",
                "source": "webhook_forwarder",
                "message": (
                    f"Webhooks degraded: {detail}. "
                    "Install with `make install-gh-extensions`. "
                    "Falling back to periodic full-sync (slower)."
                ),
            })

    webhook_forwarder._status_callback = _on_forwarder_status

    return Services(
        config=config,
        workflow_path=workflow_path,
        port=port,
        orchestrator=orchestrator,
        provider_store=provider_store,
        project_store=project_store,
        agent_profile_store=agent_profile_store,
        role_store=role_store,
        webhook_forwarder=webhook_forwarder,
    )

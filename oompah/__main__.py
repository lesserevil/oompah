"""CLI entry point for oompah."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from watchfiles import awatch

logger = logging.getLogger("oompah")


def _load_startup_env(env_file: str) -> int:
    """Load the startup .env file as the authoritative config source."""
    from oompah.config import load_dotenv

    return load_dotenv(os.path.abspath(env_file), override=True)


_VALID_SERVER_BACKENDS = ("uvicorn", "granian")


def _resolve_server_backend(cli_value: str | None) -> str:
    """Return the effective server backend, respecting CLI > env > default."""
    if cli_value is not None:
        return cli_value
    env_val = os.environ.get("OOMPAH_SERVER_BACKEND", "").strip().lower()
    return env_val if env_val in _VALID_SERVER_BACKENDS else "uvicorn"


def _resolve_workers(cli_value: int | None) -> int:
    """Return the effective worker count, respecting CLI > env > default."""
    if cli_value is not None:
        return cli_value
    env_val = os.environ.get("OOMPAH_SERVER_WORKERS", "").strip()
    try:
        return int(env_val) if env_val else 1
    except ValueError:
        return 1


def _check_granian_workers_constraint(server: str, workers: int) -> None:
    """Exit with an error if granian is asked to run with workers > 1.

    Granian spawns a separate OS process per worker.  Each worker
    re-imports the FastAPI ``app``, so the in-process state that oompah
    relies on — the orchestrator singleton and the ``_ws_clients`` WebSocket
    set in ``oompah.server`` — is **not shared** between workers.  Running
    more than one worker would therefore break WebSocket broadcast and cause
    the orchestrator to run as multiple independent, competing instances.

    The constraint is enforced here (at startup, before any async work) so
    the operator gets a clear, actionable error message rather than silent
    misbehaviour at runtime.
    """
    if server == "granian" and workers > 1:
        logger.error(
            "granian workers must be 1, got %d. "
            "oompah uses shared in-process state (orchestrator singleton and "
            "_ws_clients WebSocket set) that is not safe to share across "
            "multiple Granian worker processes. "
            "Remove --workers / unset OOMPAH_SERVER_WORKERS, or set it to 1.",
            workers,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="oompah",
        description="Orchestrate coding agents to execute project work",
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        default="./WORKFLOW.md",
        help="Path to WORKFLOW.md (default: ./WORKFLOW.md)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="HTTP server port (overrides config and OOMPAH_SERVER_PORT)",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        metavar="PATH",
        help="Path to .env file to load (default: .env)",
    )
    parser.add_argument(
        "--paused",
        action="store_true",
        help="Start the orchestrator in the paused state. Overrides any "
             "persisted paused=False from the previous run. Pause is then "
             "persisted, so subsequent restarts (without the flag) stay "
             "paused until you call /api/v1/orchestrator/resume.",
    )
    parser.add_argument(
        "--server",
        choices=list(_VALID_SERVER_BACKENDS),
        default=None,
        metavar="BACKEND",
        help=(
            "HTTP server backend to use: 'uvicorn' (default) or 'granian'. "
            "Can also be set via OOMPAH_SERVER_BACKEND in .env. "
            "NOTE: granian requires --workers 1 (the default) because oompah "
            "uses shared in-process state (orchestrator singleton and WebSocket "
            "_ws_clients) that is not safe across multiple worker processes."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Number of server worker processes (default: 1). "
            "Can also be set via OOMPAH_SERVER_WORKERS in .env. "
            "Must be 1 when --server granian is used."
        ),
    )
    args = parser.parse_args()

    # Load .env file before anything else so $VAR references in WORKFLOW.md resolve.
    env_path = os.path.abspath(args.env_file)
    n = _load_startup_env(env_path)
    if n > 0:
        # Use basic print here — logging not yet configured
        print(f"Loaded {n} variable(s) from {env_path}", file=sys.stderr)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )

    # Resolve effective server backend and worker count (CLI > env > default).
    # The .env file was loaded above, so OOMPAH_SERVER_BACKEND / OOMPAH_SERVER_WORKERS
    # are now available in os.environ.
    server_backend = _resolve_server_backend(args.server)
    workers = _resolve_workers(args.workers)

    # Hard constraint: granian does not support workers > 1 for this app.
    _check_granian_workers_constraint(server_backend, workers)

    workflow_path = os.path.abspath(args.workflow)

    # Validate workflow file exists
    if not os.path.isfile(workflow_path):
        logger.error("Workflow file not found: %s", workflow_path)
        sys.exit(1)

    while True:
        restart = False
        try:
            restart = asyncio.run(
                _run(workflow_path, args.port, start_paused=args.paused,
                     server_backend=server_backend, workers=workers)
            )
        except KeyboardInterrupt:
            logger.info("Shutting down")
        except Exception as exc:
            logger.exception("Fatal error: %s", exc)
            sys.exit(1)

        if restart:
            # Drop --paused from the re-exec argv so an in-process restart
            # doesn't keep forcing pause when the user had already resumed.
            execv_args = [a for a in sys.argv[1:] if a != "--paused"]
            logger.info("Restarting via os.execv: %s %s", sys.executable, execv_args)
            os.execv(sys.executable, [sys.executable, "-m", "oompah"] + execv_args)
        break


async def _run(
    workflow_path: str,
    cli_port: int | None,
    start_paused: bool = False,
    server_backend: str = "uvicorn",
    workers: int = 1,
) -> bool:
    from oompah.backlog_compat import BacklogCompatibilityError, ensure_backlog_compatible
    from oompah.agent_profile_store import AgentProfileStore
    from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore
    from oompah.providers import ProviderStore
    from oompah.roles import RoleStore, migrate_agent_profiles_to_roles
    from oompah.server import app, set_orchestrator
    from oompah.webhooks import WebhookForwarder

    # Load initial workflow
    try:
        workflow = load_workflow(workflow_path)
    except WorkflowError as exc:
        logger.error("Failed to load workflow: %s", exc)
        sys.exit(1)

    config = ServiceConfig.from_workflow(workflow)

    # Validate config
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

    # Strict-mode profile source check (oompah-zlz_2-hye). When the
    # operator has set strict mode, refuse to start if WORKFLOW.md
    # still has an agent.profiles block at all — the dashboard /
    # AgentProfileStore is the only authoritative source. Default
    # mode is "warn", which lets startup proceed and surfaces the
    # drift through the orchestrator alert mechanism below.
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

    # Drift warning (oompah-zlz_2-hye). When the persisted JSON store
    # disagrees with WORKFLOW.md's profile block, log a warning here
    # so the operator sees it during startup. The orchestrator below
    # also raises a dashboard alert (same source) so the operator
    # sees it without scrolling logs.
    if config.agent_profiles_drift:
        logger.warning(
            "WORKFLOW.md agent.profiles block detected and differs from "
            "persisted profile store — using the persisted store. Delete "
            "the agent.profiles section from %s to clear this warning.",
            workflow_path,
        )

    # Determine port
    port = cli_port or config.server_port

    # Create orchestrator with shared stores
    provider_store = ProviderStore()
    project_store = ProjectStore()
    # Agent profile store: ServiceConfig.from_workflow already created
    # the JSON file (or migrated WORKFLOW.md profiles into it) when it
    # parsed the workflow above. Re-open the same path here so the
    # orchestrator and the HTTP API share a single in-memory store.
    agent_profile_store = AgentProfileStore()
    # Role store (epic oompah-zlz_2-xau7): maps role_name → (provider, model).
    # First-run migration copies existing AgentProfile.provider_id/model into
    # RoleStore[profile.model_role] for empty slots — idempotent, so
    # subsequent boots are no-ops.
    role_store = RoleStore(provider_store=provider_store)
    if role_store.is_empty:
        migrate_agent_profiles_to_roles(
            role_store, agent_profile_store.list_all(),
            provider_store=provider_store,
        )

    # Start gh webhook forwarder for each project (subprocess lifecycle
    # managed by WebhookForwarder; independent of orchestrator).
    # The status_callback is wired below once the orchestrator exists so
    # forwarder-down state surfaces as a dashboard banner.
    webhook_forwarder = WebhookForwarder(project_store=project_store)

    # Pull latest code and ensure Backlog.md config compatibility
    # for every configured project BEFORE the orchestrator starts dispatching.
    # Without this, agents work against stale local state.
    # Best-effort, parallel, with per-call timeouts; failures are logged but
    # never block boot.
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

    # Ensure every managed project has a Backlog task-change webhook hook
    # installed so oompah is notified promptly when task files change.
    # Best-effort: failures are logged but never block boot.
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

    orchestrator = Orchestrator(config, workflow_path,
                                provider_store=provider_store,
                                project_store=project_store,
                                agent_profile_store=agent_profile_store,
                                role_store=role_store)
    orchestrator.set_prompt_template(workflow.prompt_template)

    # --paused CLI flag forces the orchestrator to boot paused regardless
    # of what's in the persisted state file. Persist it so subsequent
    # restarts stay paused until /resume is called.
    if start_paused and not orchestrator.is_paused:
        orchestrator._paused = True
        orchestrator._save_paused_state()
        logger.info("Booting paused (--paused flag)")
    elif orchestrator.is_paused:
        logger.info("Booting paused (persisted state)")

    set_orchestrator(orchestrator)

    # Wire forwarder health into the orchestrator's alerts list so the
    # dashboard surfaces a degraded-mode banner whenever the gh-webhook
    # extension is missing. Without this, an operator would only notice
    # webhooks were silently failing after agents started missing work.
    def _on_forwarder_status(status: dict) -> None:
        # Drop any prior webhook_forwarder alert (idempotent re-arming)
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

    # Start webhook forwarder (runs gh webhook forward per project)
    await webhook_forwarder.start()

    # Start workflow file watcher
    async def _watch_workflow():
        try:
            async for changes in awatch(workflow_path):
                logger.info("Workflow file changed, reloading")
                try:
                    new_wf = load_workflow(workflow_path)
                    new_config = ServiceConfig.from_workflow(new_wf)
                    errs = validate_dispatch_config(new_config)
                    if errs:
                        logger.error("Invalid workflow reload: %s", "; ".join(errs))
                        continue
                    orchestrator.reload_config(new_config, new_wf.prompt_template)
                except WorkflowError as exc:
                    logger.error("Workflow reload failed: %s", exc)
        except asyncio.CancelledError:
            pass

    watch_task = asyncio.create_task(_watch_workflow())

    # Start orchestrator
    orch_task = asyncio.create_task(orchestrator.run())

    # Start HTTP server if port configured
    server = None
    server_task = None
    if port is not None:
        logger.info(
            "HTTP server starting on http://0.0.0.0:%d (backend=%s, workers=%d)",
            port, server_backend, workers,
        )
        if server_backend == "granian":
            # Granian path: run as an asyncio task using the ASGI interface.
            # workers is always 1 here (enforced by _check_granian_workers_constraint).
            # NOTE: Full granian integration (bootstrap.py, lifespan orchestrator
            # embedding) is implemented in TASK-472.1–472.6. This branch logs
            # the intent and falls back to uvicorn until that work lands.
            logger.warning(
                "granian backend selected but full integration is not yet "
                "enabled; falling back to uvicorn for this run. "
                "See TASK-472 for the granian integration roadmap."
            )
            import uvicorn as _uvicorn

            uvi_config = _uvicorn.Config(
                app,
                host="0.0.0.0",
                port=port,
                log_level="info",
                access_log=False,
            )
            server = _uvicorn.Server(uvi_config)
            server_task = asyncio.create_task(server.serve())
        else:
            import uvicorn

            uvi_config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=port,
                log_level="info",
                access_log=False,
            )
            server = uvicorn.Server(uvi_config)
            server_task = asyncio.create_task(server.serve())

    try:
        # Wait for orchestrator to finish (normal stop or restart)
        await orch_task
    except asyncio.CancelledError:
        pass
    finally:
        wants_restart = orchestrator.wants_restart
        await orchestrator.stop()
        await webhook_forwarder.stop()
        watch_task.cancel()
        if server:
            server.should_exit = True
        if server_task:
            server_task.cancel()
        return wants_restart


if __name__ == "__main__":
    main()

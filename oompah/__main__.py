"""CLI entry point for oompah."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from watchfiles import awatch

logger = logging.getLogger("oompah")


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
        help="HTTP server port (overrides server.port in WORKFLOW.md)",
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
    args = parser.parse_args()

    # Load .env file before anything else so $VAR references in WORKFLOW.md resolve.
    # Import here to avoid circular imports at module load time.
    from oompah.config import load_dotenv

    env_path = os.path.abspath(args.env_file)
    n = load_dotenv(env_path)
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

    workflow_path = os.path.abspath(args.workflow)

    # Validate workflow file exists
    if not os.path.isfile(workflow_path):
        logger.error("Workflow file not found: %s", workflow_path)
        sys.exit(1)

    while True:
        restart = False
        try:
            restart = asyncio.run(_run(workflow_path, args.port, start_paused=args.paused))
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
    workflow_path: str, cli_port: int | None, start_paused: bool = False,
) -> bool:
    from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore
    from oompah.providers import ProviderStore
    from oompah.server import app, set_orchestrator

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

    # Determine port
    port = cli_port or config.server_port

    # Create orchestrator with shared stores
    provider_store = ProviderStore()
    project_store = ProjectStore()

    # Pull latest code (git pull --ff-only) and beads state (bd dolt pull)
    # for every configured project BEFORE the orchestrator starts dispatching.
    # Without this, agents work against stale local state — both stale code
    # in the worktree base and stale beads (e.g. tasks marked deferred on
    # another machine still appear as open locally and get auto-dispatched).
    # Best-effort, parallel, with per-call timeouts; failures are logged but
    # never block boot.
    projects = project_store.list_all()
    if projects:
        logger.info("Syncing sources for %d project(s) before dispatch...", len(projects))
        sync_results = project_store.sync_all_sources()
        for pid, st in sync_results.items():
            name = next((p.name for p in projects if p.id == pid), pid)
            logger.info(
                "Startup sync %s: git=%s beads=%s",
                name, st.get("git", "?"), st.get("beads", "?"),
            )

    orchestrator = Orchestrator(config, workflow_path,
                                provider_store=provider_store,
                                project_store=project_store)
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
        logger.info("HTTP server starting on http://0.0.0.0:%d", port)

    try:
        # Wait for orchestrator to finish (normal stop or restart)
        await orch_task
    except asyncio.CancelledError:
        pass
    finally:
        wants_restart = orchestrator.wants_restart
        await orchestrator.stop()
        watch_task.cancel()
        if server:
            server.should_exit = True
        if server_task:
            server_task.cancel()
        return wants_restart


if __name__ == "__main__":
    main()

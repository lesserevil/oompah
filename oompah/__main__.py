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
        choices=["uvicorn", "granian"],
        default="uvicorn",
        help=(
            "HTTP server backend (default: uvicorn). "
            "Use --server granian to opt into the Granian ASGI server "
            "(requires the granian package: pip install granian). "
            "Granian runs workers=1 with the orchestrator inside the "
            "ASGI lifespan so the WebSocket broadcast path keeps working."
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

    workflow_path = os.path.abspath(args.workflow)

    # Validate workflow file exists (early exit before async setup)
    if not os.path.isfile(workflow_path):
        logger.error("Workflow file not found: %s", workflow_path)
        sys.exit(1)

    if args.server == "granian":
        _run_granian(workflow_path, args.port, start_paused=args.paused)
        return

    # --- uvicorn path ---
    while True:
        restart = False
        try:
            restart = asyncio.run(
                _run(workflow_path, args.port, start_paused=args.paused),
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
            logger.info(
                "Restarting via os.execv: %s %s", sys.executable, execv_args,
            )
            os.execv(
                sys.executable,
                [sys.executable, "-m", "oompah"] + execv_args,
            )
        break


def _run_granian(
    workflow_path: str,
    cli_port: int | None,
    start_paused: bool = False,
) -> None:
    """Launch oompah under the Granian ASGI server.

    Granian owns the process (``Granian.serve()`` blocks).  The orchestrator
    and all services run inside the ASGI lifespan on the single worker loop
    (``OOMPAH_EMBED_ORCHESTRATOR=1``), which keeps the WebSocket
    ``_broadcast`` path working.

    On restart (orchestrator sets ``wants_restart``), the lifespan writes a
    sentinel file and sends SIGTERM to the Granian supervisor (PPID).  This
    function detects the sentinel after Granian exits and re-execs.

    Startup validation failures are handled by the lifespan: it calls
    ``os._exit(1)`` so the exception never escapes the asyncio task (avoids
    "Task exception was never retrieved" and worker respawn loops).
    """
    try:
        from granian import Granian  # type: ignore[import-untyped]
    except ImportError:
        logger.error(
            "granian is not installed. Install it with: pip install granian "
            "(or add it to your dependencies and run: uv sync)",
        )
        sys.exit(1)

    from oompah.config import ServiceConfig, load_workflow
    from oompah.server import app

    # Determine port: prefer CLI flag, then env, then workflow default.
    port = cli_port
    if port is None:
        try:
            wf = load_workflow(workflow_path)
            cfg = ServiceConfig.from_workflow(wf)
            port = cfg.server_port
        except Exception:
            port = 7777  # last-resort default

    # Pass startup parameters to the lifespan via env vars (the lifespan
    # runs in the worker process, which inherits the environment).
    os.environ["OOMPAH_EMBED_ORCHESTRATOR"] = "1"
    os.environ["OOMPAH_WORKFLOW_PATH"] = workflow_path
    if cli_port is not None:
        os.environ["OOMPAH_SERVER_PORT_OVERRIDE"] = str(cli_port)
    if start_paused:
        os.environ["OOMPAH_START_PAUSED"] = "1"

    _RESTART_SENTINEL = os.path.join(
        os.path.dirname(workflow_path), ".oompah", "granian_restart",
    )

    while True:
        # Remove any stale sentinel before starting.
        try:
            os.remove(_RESTART_SENTINEL)
        except FileNotFoundError:
            pass

        logger.info(
            "Starting Granian ASGI server on http://0.0.0.0:%d", port,
        )
        granian = Granian(
            "oompah.server:app",
            address="0.0.0.0",
            port=port,
            workers=1,  # required: shared in-process state (orchestrator, WS)
            respawn_failed_workers=False,  # don't respawn on startup failure
        )
        granian.serve()

        # Granian.serve() returned — check whether the lifespan requested
        # a restart via the sentinel file.
        if os.path.exists(_RESTART_SENTINEL):
            try:
                os.remove(_RESTART_SENTINEL)
            except FileNotFoundError:
                pass
            execv_args = [a for a in sys.argv[1:] if a != "--paused"]
            logger.info(
                "Restarting via os.execv: %s %s", sys.executable, execv_args,
            )
            os.execv(
                sys.executable,
                [sys.executable, "-m", "oompah"] + execv_args,
            )
        break


async def _run(
    workflow_path: str, cli_port: int | None, start_paused: bool = False,
) -> bool:
    """Uvicorn path: validate config, set up services, run until stopped.

    Uses :func:`oompah.bootstrap.setup_services` for all validation and
    service creation.  :class:`~oompah.bootstrap.StartupError` is caught
    here and converted to ``sys.exit(1)`` so the uvicorn path behaviour is
    unchanged.
    """
    from oompah.bootstrap import StartupError, setup_services
    from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
    from oompah.server import app, set_orchestrator

    # ------------------------------------------------------------------
    # Validate config and create all service objects.
    # StartupError → sys.exit(1) (uvicorn path: SystemExit propagates
    # cleanly through asyncio.run → main()).
    # ------------------------------------------------------------------
    try:
        services = await setup_services(
            workflow_path, cli_port=cli_port, start_paused=start_paused,
        )
    except StartupError:
        # Error already logged by setup_services(); exit without traceback.
        sys.exit(1)

    orchestrator = services.orchestrator
    webhook_forwarder = services.webhook_forwarder
    port = services.port

    set_orchestrator(orchestrator)

    # Wire forwarder health into the orchestrator's alerts list so the
    # dashboard surfaces a degraded-mode banner whenever the gh-webhook
    # extension is missing.
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
                        logger.error(
                            "Invalid workflow reload: %s", "; ".join(errs),
                        )
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
        await webhook_forwarder.stop()
        watch_task.cancel()
        if server:
            server.should_exit = True
        if server_task:
            server_task.cancel()
        return wants_restart


if __name__ == "__main__":
    main()

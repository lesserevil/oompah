"""CLI entry point for oompah."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

logger = logging.getLogger("oompah")

# Sentinel file written by the Granian lifespan _supervise() task to signal
# that _run_granian() should re-exec after Granian exits.
_GRANIAN_RESTART_SENTINEL = ".oompah-granian-restart"


def _load_startup_env(env_file: str) -> int:
    """Load the startup .env file as the authoritative config source."""
    from oompah.config import load_dotenv

    return load_dotenv(os.path.abspath(env_file), override=True)


_VALID_SERVER_BACKENDS = ("uvicorn", "granian")
_SERVER_SUBCOMMANDS = {"server", "serve", "run"}


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


def _restart_execv_args(argv: list[str]) -> list[str]:
    """Return CLI args to preserve service mode across in-process restarts."""
    execv_args = [arg for arg in argv if arg != "--paused"]
    if not execv_args:
        return ["server"]
    return execv_args


def _build_server_parser(
    *, prog: str = "oompah", include_subcommands: bool = True
) -> argparse.ArgumentParser:
    if include_subcommands:
        usage = "\n".join(
            [
                "oompah [--help]",
                "       oompah server [WORKFLOW.md] [server options]",
                "       oompah [WORKFLOW.md] [server options]",
                "       oompah task ...",
                "       oompah project-bootstrap ...",
            ]
        )
        epilog = """\
Common commands:
  oompah                         Show this help.
  oompah server                  Start the web server with ./WORKFLOW.md.
  oompah server WORKFLOW.md      Start the web server with an explicit workflow.
  oompah task --help             Manage native oompah tasks through a running server.
  oompah project-bootstrap --help
                                 Inspect or install project AGENTS.md integration.

Examples:
  oompah server --port 8090
  oompah server --paused
  oompah server --server granian WORKFLOW.md
  OOMPAH_SERVER_URL=http://127.0.0.1:8090 oompah task view TASK-1

Legacy server form is still supported:
  oompah WORKFLOW.md --port 8090
  oompah --server granian WORKFLOW.md
"""
    else:
        usage = f"{prog} [WORKFLOW.md] [server options]"
        epilog = """\
Examples:
  oompah server --port 8090
  oompah server --paused
  oompah server --server granian WORKFLOW.md
"""

    parser = argparse.ArgumentParser(
        prog=prog,
        usage=usage,
        description=(
            "Oompah runs the local orchestration service and provides "
            "task-management helper commands."
        ),
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    return parser


def main() -> None:
    # Dispatch 'oompah task ...' to the task CLI module before touching the
    # server argparse so help text and error messages are clean.
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "task":
        from oompah.task_cli import main as _task_main
        _task_main(raw_args[1:])
        return

    if raw_args and raw_args[0] == "project-bootstrap":
        from oompah.project_bootstrap_cli import main as _project_bootstrap_main
        _project_bootstrap_main(raw_args[1:])
        return

    if not raw_args:
        parser = _build_server_parser()
        parser.print_help()
        return

    explicit_server = raw_args[0] in _SERVER_SUBCOMMANDS
    if explicit_server:
        prog = f"oompah {raw_args[0]}"
        parse_args = raw_args[1:]
    else:
        prog = "oompah"
        parse_args = raw_args
    parser = _build_server_parser(
        prog=prog,
        include_subcommands=not explicit_server,
    )
    args = parser.parse_args(parse_args)

    try:
        import watchfiles  # noqa: F401
    except ImportError:
        sys.exit(
            "ERROR: oompah server dependencies are not installed.\n"
            "The default GitHub install provides the standalone task CLI only.\n"
            "Install the service runtime from a clone with: uv pip install -e '.[server]'\n"
            "For task operations, use: oompah task --help"
        )

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

    if server_backend == "granian":
        _run_granian(workflow_path, args.port, start_paused=args.paused)
        return

    # --- uvicorn path (default) ---
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
            execv_args = _restart_execv_args(sys.argv[1:])
            logger.info("Restarting via os.execv: %s %s", sys.executable, execv_args)
            os.execv(sys.executable, [sys.executable, "-m", "oompah"] + execv_args)
        break


def _run_granian(
    workflow_path: str,
    cli_port: int | None,
    start_paused: bool = False,
) -> None:
    """Launch oompah under the Granian ASGI server.

    Granian is started with ``workers=1`` because oompah holds shared
    in-process state (orchestrator, WebSocket clients).  The orchestrator
    runs inside the worker's ASGI lifespan (see ``oompah.server._lifespan``)
    so ``_broadcast`` keeps working on the same event loop.

    On restart: the lifespan's ``_supervise`` task writes a sentinel file and
    SIGTERMs the Granian supervisor, causing ``serve()`` to return.  This
    function then detects the sentinel, removes it, and re-execs.

    Requires the ``server`` and ``granian`` extras:
    ``uv pip install -e '.[server,granian]'``
    """
    try:
        from granian import Granian
        from granian.server.common import Interfaces, Loops
    except ImportError:
        logger.error(
            "granian is not installed. Install it with: "
            "uv pip install -e '.[server,granian]'"
        )
        sys.exit(1)

    # Pass configuration to the ASGI lifespan via environment variables so
    # the Granian worker process (which re-imports the app) can read them.
    os.environ["OOMPAH_EMBED_ORCHESTRATOR"] = "1"
    os.environ["OOMPAH_WORKFLOW_PATH"] = workflow_path
    if start_paused:
        os.environ["OOMPAH_START_PAUSED"] = "1"
    elif "OOMPAH_START_PAUSED" in os.environ:
        del os.environ["OOMPAH_START_PAUSED"]

    # Resolve port: CLI flag > OOMPAH_SERVER_PORT env > workflow config > 8080.
    port = cli_port
    if port is None:
        env_port = os.environ.get("OOMPAH_SERVER_PORT")
        if env_port:
            try:
                port = int(env_port)
            except ValueError:
                pass
    if port is None:
        try:
            from oompah.config import ServiceConfig, WorkflowError, load_workflow

            wf = load_workflow(workflow_path)
            port = ServiceConfig.from_workflow(wf).server_port
        except Exception:  # noqa: BLE001
            pass
    if port is None:
        port = 8080

    server = Granian(
        target="oompah.server:app",
        address="0.0.0.0",
        port=port,
        interface=Interfaces.ASGI,
        workers=1,
        loop=Loops.uvloop,
        respawn_failed_workers=False,
    )
    logger.info("Starting Granian ASGI server on http://0.0.0.0:%d", port)
    server.serve()  # blocks until the supervisor exits

    # Check for restart sentinel written by the lifespan _supervise task.
    if os.path.exists(_GRANIAN_RESTART_SENTINEL):
        os.remove(_GRANIAN_RESTART_SENTINEL)
        execv_args = _restart_execv_args(sys.argv[1:])
        logger.info(
            "Restart sentinel found; re-executing: %s %s",
            sys.executable, execv_args,
        )
        os.execv(sys.executable, [sys.executable, "-m", "oompah"] + execv_args)


async def _run(
    workflow_path: str,
    cli_port: int | None,
    start_paused: bool = False,
    server_backend: str = "uvicorn",
    workers: int = 1,
) -> bool:
    """Run oompah under uvicorn (the default server path).

    Uses :func:`oompah.bootstrap.setup_services` for service wiring so both
    the uvicorn and Granian paths share identical startup logic.
    """
    from oompah.bootstrap import StartupError, setup_services
    from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
    from oompah.server import app, set_orchestrator
    from watchfiles import awatch

    try:
        services = await setup_services(workflow_path, cli_port, start_paused)
    except StartupError:
        sys.exit(1)
    port = services.port
    orchestrator = services.orchestrator
    webhook_forwarder = services.webhook_forwarder

    set_orchestrator(orchestrator)

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

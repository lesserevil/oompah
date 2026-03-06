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

    try:
        asyncio.run(_run(workflow_path, args.port))
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        sys.exit(1)


async def _run(workflow_path: str, cli_port: int | None) -> None:
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
    orchestrator = Orchestrator(config, workflow_path,
                                provider_store=provider_store,
                                project_store=project_store)
    orchestrator.set_prompt_template(workflow.prompt_template)
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
    server_task = None
    if port is not None:
        import uvicorn

        uvi_config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(uvi_config)
        server_task = asyncio.create_task(server.serve())
        logger.info("HTTP server starting on http://127.0.0.1:%d", port)

    try:
        tasks = [orch_task, watch_task]
        if server_task:
            tasks.append(server_task)
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await orchestrator.stop()
        watch_task.cancel()
        if server_task:
            server_task.cancel()


if __name__ == "__main__":
    main()

---
id: doc-1
title: Granian HTTP server migration plan
type: specification
created_date: '2026-06-09 04:17'
---

## Summary

We evaluated migrating oompah's HTTP layer off FastAPI/uvicorn for performance.
A full framework rewrite (e.g. Robyn) is high-cost and a poor fit. The
high-value, low-risk move is to **keep the FastAPI/Starlette app and swap the
ASGI *server* from uvicorn to Granian** (a Rust/Tokio ASGI server). A working
prototype is in the tree and proven end-to-end. This plan tracks the work to
make it production-ready, plus a complementary track to attack the real
bottleneck (orchestrator/blocking work on the request loop).

## Background and findings

- `oompah/server.py` is the single FastAPI app: ~75 HTTP routes + 1 WebSocket,
  3 multipart upload routes, a `/static` mount and Jinja HTML routes. It uses
  **no Pydantic-in-signature models and no `Depends()`** — every route does
  manual `await request.json()` -> `JSONResponse`. So FastAPI's main overhead
  (validation, DI) is already bypassed; swapping the *framework* buys little.
- The app is tightly coupled to a long-running asyncio orchestrator that runs
  in the **same process and event loop**. The orchestrator and console sessions
  push live updates to browsers by scheduling `_broadcast(...)` onto that shared
  loop (`server.py` `_ws_clients`, `_on_orchestrator_change`). Preserving this
  cross-task WebSocket push is the central migration risk.
- Today uvicorn runs as one `asyncio` task on that shared loop
  (`__main__._run`). `Granian.serve()` is **not** a coroutine: it blocks and
  spawns its own worker process(es), each re-importing the app with its own
  loop. So Granian cannot be slotted in as a task the way uvicorn is.

### Benchmark (prototype, single worker, multi-process load client)

`scripts/bench_server.py`, route `/` (cached in-memory HTML, isolates HTTP
overhead):

- Granian vs uvicorn throughput: **+22–25%**, repeatable across runs.
- Tail latency tighter under Granian (e.g. p99 ~58ms vs ~116ms).
- Caveat: oompah's real workload is LLM/subprocess/orchestrator-bound, so a
  ~23% HTTP gain may not change perceived performance. Benchmark in a
  representative environment before making Granian the default.

## Chosen approach: Path B (orchestrator inside the ASGI lifespan)

Granian owns the process; the orchestrator runs as a background task started
from the FastAPI **lifespan**, inside Granian's single worker — the *same* loop
the WebSocket handlers run on — so `_broadcast` works. `workers=1` is mandatory
because the app holds shared in-process state (`_orchestrator`, `_ws_clients`).

### Prototype already in the tree (uncommitted)

- `oompah/bootstrap.py` (new): `setup_services()` + `Services` dataclass —
  all service wiring extracted from `__main__._run`, shared by both paths.
- `oompah/server.py`: guarded ASGI `lifespan`. When
  `OOMPAH_EMBED_ORCHESTRATOR=1` it runs `setup_services()` + starts the
  orchestrator on the worker loop, plus a `_supervise()` task that relays an
  orchestrator-requested restart to the Granian supervisor (sentinel file +
  SIGTERM to PPID). Unset (uvicorn path / tests) -> no-op.
- `oompah/__main__.py`: `--server {uvicorn,granian}` flag + `_run_granian()`
  launcher (resolves port, sets embed env vars, runs Granian, re-execs on the
  restart sentinel). uvicorn remains the default.

### Prototype verification

- e2e (`/tmp/granian_e2e/test_path_b.py`): HTTP serves; `/api/v1/state` served
  by worker-loop orchestrator; WS initial push; and the decisive
  **orchestrator -> observer -> `_broadcast` -> connected WS client** path —
  all pass.
- Regression: 315 server/console/webhook/pause/roles/providers/release-pick
  tests pass with the no-op lifespan. Granian worker runs on uvloop by default
  (matches `uvicorn[standard]`).

## Known prototype-grade gaps (to harden — see Epic A)

1. Startup validation uses `sys.exit(1)` inside the lifespan -> Granian logs
   "Task exception was never retrieved" and may respawn the worker. Needs a
   clean lifespan-abort that stops the supervisor.
2. Restart relies on SIGTERM-to-parent + sentinel; verify against Granian's
   `respawn_failed_workers` and confirm `/api/v1/orchestrator/restart` +
   workflow-reload restart still work.
3. WebSocket lifecycle at scale (fan-out, disconnect cleanup, `console_input`,
   throttled state/issues broadcasts) needs validation under Granian.
4. Multipart upload, `/static` mount, and Jinja routes need validation under
   Granian.
5. No automated test coverage for the Granian path (only the throwaway e2e
   harness).
6. `granian` is not in `pyproject.toml`/lockfile; no `make` target; docs not
   updated.
7. Go/no-go: benchmark in a representative environment before flipping the
   default.

## Complementary track: event-loop contention (Epic B)

Independent of server choice and the bigger lever:

- Route handlers contain ~11 `subprocess`/`run_in_executor`/sync-I/O sites;
  some hot paths do synchronous file reads in async handlers (the favicon
  `read_bytes()` found during benchmarking). Move blocking work off the loop.
- Profile real request latency under load to confirm the true bottleneck
  before deeper work.
- Evaluate splitting the orchestrator into its own process behind a queue/IPC,
  with the web layer subscribing for WS push. This removes the shared-loop
  coupling entirely and would unlock Granian multi-worker.

## Decision gate

Adopt Granian as the default only after Epic A hardening + a representative
benchmark. Until then it ships behind `--server granian` (opt-in) with uvicorn
as the default.

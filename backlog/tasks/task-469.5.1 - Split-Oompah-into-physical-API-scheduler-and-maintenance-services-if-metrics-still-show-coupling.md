---
id: TASK-469.5.1
title: >-
  Split Oompah into physical API, scheduler, and maintenance services if metrics
  still show coupling
status: In Progress
assignee: []
created_date: '2026-06-08 23:02'
updated_date: '2026-06-09 00:56'
labels: []
dependencies: []
parent_task_id: TASK-469.5
priority: high
ordinal: 175000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-469.5. TASK-469 delivered the immediate responsiveness isolation with nonblocking issue snapshots, dedicated API execution, dispatch coalescing, bounded candidate scans, and incremental maintenance. If the new orchestrator_metrics/api_metrics still show API stalls caused by scheduler, tracker parsing, or maintenance work after deployment, design and implement a durable local service boundary: oompah-api serving cached state/issues and accepting commands, oompah-scheduler owning dispatch/reconcile/review ticks, and oompah-maintenance owning archive/worktree cleanup/repo heal. Coordinate through SQLite or another local durable queue/cache before considering Redis.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 00:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:13
---
Understanding + Plan: TASK-469.5 delivered dedicated thread pools, issues snapshot caching, and per-endpoint latency metrics. The remaining GIL contention problem: oompah-api, oompah-scheduler, and tracker YAML parsing all run in the same Python process; heavy tick operations (yaml.safe_load across many task files) hold the GIL and stall API thread pool operations regardless of having separate ThreadPoolExecutors. The task is to implement a physical service boundary with SQLite coordination. Plan: (1) Implement oompah/ipc.py — a SQLite-backed IPC layer with tables for state_snapshot, issues_snapshot, and command_queue; (2) Add a StatePublisher to Orchestrator that writes to SQLite after each tick; (3) Add a CommandConsumer loop to Orchestrator that polls the command_queue table; (4) Add a MaintenancePublisher that writes maintenance status; (5) Modify server.py to read state/issues from SQLite when a scheduler process is configured (OOMPAH_SCHEDULER_SOCKET env var); (6) Write tests for the IPC layer; (7) Write design doc in plans/service-split.md. The implementation keeps backward compat — single-process mode continues to work, multi-process mode becomes opt-in via config.
---

author: oompah
created: 2026-06-09 00:16
---
Discovery: The root coupling is GIL contention between oompah-api and oompah-scheduler threads sharing the same Python process. tracker.py uses yaml.safe_load() which holds the GIL during YAML frontmatter parsing — with many task files this blocks API thread pool operations even though separate ThreadPoolExecutors exist (TASK-469.5 fix). The critical read paths (/api/v1/state calls get_snapshot() inline, /api/v1/issues uses the existing issues snapshot with dedicated pool). The fix: (1) oompah/ipc.py — SQLite WAL-mode coordination layer with tables kv (snapshots) and commands (FIFO queue); (2) orchestrator publishes state+issues to SQLite via _notify_observers() hook; (3) server reads from SQLite in api-only mode (OOMPAH_IPC_DB_PATH set); (4) commands from API enqueue to SQLite, scheduler polls and processes; (5) config option OOMPAH_IPC_DB_PATH enables multi-process mode.
---

author: oompah
created: 2026-06-09 00:44
---
Implementation complete. Delivered: (1) oompah/ipc.py — SQLite WAL-mode coordination layer (OrchestratorIPC class) with kv snapshot table and commands FIFO queue; (2) orchestrator.py — accepts optional ipc param, _notify_observers publishes state to SQLite, _tick calls _process_ipc_commands, get_snapshot includes ipc diagnostics; (3) server.py — module-level _ipc singleton, api_state reads from SQLite in API-only mode, pause/resume/dispatch endpoints enqueue IPC commands; (4) config.py — ServiceConfig.ipc_db_path field from OOMPAH_IPC_DB_PATH env; (5) .env.example — documents OOMPAH_IPC_DB_PATH; (6) plans/service-split.md — full architecture design doc with Mermaid diagrams; (7) tests/test_ipc.py — 40 tests covering all IPC operations, thread safety, Orchestrator integration, and Server API integration. Backward compatible: single-process combined mode unchanged when OOMPAH_IPC_DB_PATH is unset.
---

author: oompah
created: 2026-06-09 00:56
---
Verification: 40/40 tests pass in tests/test_ipc.py. 341/341 tests pass across the full relevant test suite (test_ipc, test_orchestrator_handlers, test_orchestrator_pause, test_submit_queue_concurrency, test_server_issue_snapshot, test_event_driven_loop, test_config). No regressions. Post-simplify fixes applied: removed redundant import, fixed dispatch_issue to use asyncio.ensure_future directly (we are always on the event loop), replaced getattr guard with direct attribute access, inlined _get_updated_at helper.
---
<!-- COMMENTS:END -->

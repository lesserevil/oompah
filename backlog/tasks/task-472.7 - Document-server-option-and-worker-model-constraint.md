---
id: TASK-472.7
title: Document --server option and worker-model constraint
status: In Progress
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 15:58'
labels:
  - 'needs:backend'
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 196000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update README/AGENTS.md/.env.example for the --server {uvicorn,granian} option. Document why granian must run workers=1 (shared in-process orchestrator + _ws_clients state) and guard against misconfiguration (reject workers>1 or warn).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Docs describe --server and the workers=1 constraint
- [ ] #2 workers>1 under granian is rejected or clearly warned
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 15:44
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 15:45
---
UNDERSTANDING: No duplicate found. This is a legitimate subtask of TASK-472 (Epic: Adopt Granian HTTP server). Task requires: (1) Update docs (README/AGENTS.md/.env.example) for --server {uvicorn,granian} option, (2) Document why granian must use workers=1 (shared in-process orchestrator + _ws_clients state), (3) Add a guard that rejects workers>1 when using granian. Exploring codebase now.
---

author: oompah
created: 2026-06-09 15:50
---
DISCOVERY: Confirmed no duplicate. Codebase state: __main__.py has no --server flag yet; granian is not in pyproject.toml; bootstrap.py doesn't exist. This task needs to add: (1) --server {uvicorn,granian} and --workers N flags to __main__.py with env var support, (2) guard that exits with error when --server granian --workers > 1, (3) .env.example entries for OOMPAH_SERVER_BACKEND + OOMPAH_SERVER_WORKERS, (4) README.md section on server backend and workers=1 constraint, (5) tests for the guard.
---

author: oompah
created: 2026-06-09 15:58
---
IMPLEMENTATION: Added --server {uvicorn,granian} and --workers N flags to oompah/__main__.py. Key changes: (1) _resolve_server_backend() and _resolve_workers() helpers honour CLI > OOMPAH_SERVER_BACKEND/OOMPAH_SERVER_WORKERS env > default. (2) _check_granian_workers_constraint() rejects workers>1 with granian via sys.exit(1) with clear error explaining _ws_clients and orchestrator singleton constraint. (3) _run() updated to log selected backend+workers and includes a fallback-to-uvicorn note for when full granian integration lands (TASK-472.1-6). (4) .env.example has OOMPAH_SERVER_BACKEND and OOMPAH_SERVER_WORKERS entries with full inline rationale. (5) README.md has new 'HTTP server backend' subsection with table, code examples, and workers=1 constraint explanation. (6) 18 unit tests in tests/test_granian_guard.py, all passing.
---

author: oompah
created: 2026-06-09 15:58
---
VERIFICATION: 18/18 tests pass in tests/test_granian_guard.py. Also verified tests/test_config.py (49 tests) and tests/test_server_json_validation.py (17 tests) all still pass — no regressions.
---
<!-- COMMENTS:END -->

---
id: TASK-472.7
title: Document --server option and worker-model constraint
status: In Progress
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 20:29'
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
created: 2026-06-09 20:26
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 20:26
---
UNDERSTANDING: This task is not a duplicate - it's a unique subtask in the TASK-472 Granian HTTP server epic. The task requires: (1) documenting --server {uvicorn,granian} in README/AGENTS.md/.env.example, (2) documenting the workers=1 constraint for granian (shared in-process orchestrator + _ws_clients state), and (3) adding a guard that rejects or warns when workers>1 is used with granian. Plan: explore existing code in oompah/__main__.py and oompah/server.py, check README/AGENTS.md/.env.example, then implement docs + guard.
---

author: oompah
created: 2026-06-09 20:27
---
DISCOVERY: The code and documentation are already largely in place. oompah/__main__.py has _check_granian_workers_constraint() (sys.exit(1) when granian + workers > 1), _resolve_server_backend(), and _resolve_workers() helper functions. README.md has a 'HTTP server backend' section documenting --server and the workers=1 constraint. .env.example documents OOMPAH_SERVER_BACKEND and OOMPAH_SERVER_WORKERS with constraint notes. The configuration table in README.md lists server.backend and server.workers. What is MISSING: unit tests for _resolve_server_backend, _resolve_workers, and _check_granian_workers_constraint in oompah/__main__.py. Creating tests/test_main_server_config.py to cover these functions.
---

author: oompah
created: 2026-06-09 20:29
---
IMPLEMENTATION: The code guard (reject workers>1 with granian via sys.exit) and documentation (README.md, .env.example, --server/--workers argparse help) were already in place from prior work on the TASK-472 epic. What was missing and is now added: tests/test_main_server_config.py with 23 unit tests covering _resolve_server_backend (CLI > env > default precedence), _resolve_workers (same), and _check_granian_workers_constraint (no-exit for uvicorn/granian+1, sys.exit(1) for granian+>1, error log mentions 'granian' and '1'). All 23 tests pass.
---
<!-- COMMENTS:END -->

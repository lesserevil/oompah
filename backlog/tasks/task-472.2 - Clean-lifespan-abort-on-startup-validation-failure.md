---
id: TASK-472.2
title: Clean lifespan abort on startup-validation failure
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 21:02'
labels: []
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 191000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
setup_services() calls sys.exit(1) on config/backlog/profile validation errors. Inside the Granian worker lifespan this surfaces as 'Task exception was never retrieved' and can trigger worker respawn loops. Replace with a clean failure that aborts the Granian supervisor (no respawn), while preserving the uvicorn path behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Validation failure under granian stops the process cleanly with a clear log and non-zero exit
- [ ] #2 No 'Task exception was never retrieved'; no respawn loop
- [ ] #3 uvicorn path behavior unchanged
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 14:32
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 14:32
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 15:42
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:43
---
UNDERSTANDING: No duplicate found. This task is a standalone subtask of the Granian migration epic (TASK-472). The problem: setup_services() uses sys.exit(1) for validation errors, which inside a Granian worker's async lifespan causes 'Task exception was never retrieved' and possible respawn loops. Plan: find setup_services() and the lifespan code, replace sys.exit(1) with a custom exception that the Granian lifespan catches to abort cleanly, while keeping the uvicorn code path unchanged.
---

author: oompah
created: 2026-06-09 15:53
---
DISCOVERY: No duplicate found. The prototype code referenced in the design doc (bootstrap.py, lifespan in server.py) is NOT in the tree — the df80546 commit was 'plan-only'. I need to implement from scratch: (1) oompah/bootstrap.py with StartupError exception and setup_services() that raises StartupError instead of sys.exit(1); (2) Add a guarded lifespan to server.py that catches StartupError and calls os._exit(1) instead of leaking it as a task exception; (3) Modify __main__.py to use setup_services() and catch StartupError → sys.exit(1) for uvicorn path; (4) Tests.
---

author: oompah
created: 2026-06-09 16:16
---
IMPLEMENTATION: Created oompah/bootstrap.py with StartupError exception and setup_services() async function that extracts all startup validation from __main__._run() and raises StartupError instead of sys.exit(1). Modified oompah/server.py to add _lifespan() asynccontextmanager (guarded by OOMPAH_EMBED_ORCHESTRATOR=1): catches StartupError, sends SIGTERM to parent (Granian supervisor), then calls os._exit(1) — the exception never escapes the coroutine so 'Task exception was never retrieved' is impossible. Modified oompah/__main__.py to use setup_services() in _run() (uvicorn path catches StartupError → sys.exit(1), preserving prior behavior), added --server granian flag and _run_granian() launcher with respawn_failed_workers=False. FastAPI app now uses lifespan=_lifespan (no-op unless embed env is set). Tests in tests/test_lifespan_abort.py: 11 tests covering all 3 acceptance criteria.
---
<!-- COMMENTS:END -->

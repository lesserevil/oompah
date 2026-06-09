---
id: TASK-472.1
title: Add granian dependency and run target
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 21:02'
labels: []
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 190000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add granian to pyproject.toml dependencies and refresh uv.lock. Add a make target (e.g. 'make run-granian') and/or document the invocation. Currently granian is only installed ad hoc in the venv.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 granian pinned in pyproject.toml and present in uv.lock
- [ ] #2 Documented/Make target to launch with --server granian
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 14:31
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 14:31
---
Focus: Maintenance Engineer
---

author: oompah
created: 2026-06-09 15:42
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:45
---
Understanding: TASK-472.1 is NOT a duplicate — it is a unique foundational subtask of the TASK-472 epic. The plan (doc-1) describes a Granian ASGI server prototype ('already in tree, uncommitted') that includes: bootstrap.py (service wiring), server.py lifespan (OOMPAH_EMBED_ORCHESTRATOR=1 path), and __main__.py --server granian flag. None of these are committed. My approach: (1) add granian>=1.0 as an optional pyproject.toml dependency + to dev, (2) implement bootstrap.py + server.py lifespan + __main__.py --server granian as the prototype commit, (3) add make run-granian target, (4) run uv lock to refresh lockfile. TASK-472.2/3 will then harden the lifespan abort and restart relay.
---

author: oompah
created: 2026-06-09 15:50
---
Discovery: Confirmed no duplicate. Granian 2.7.5 is ad hoc installed in .venv but not in pyproject.toml or uv.lock. The --server granian flag does NOT exist in __main__.py — the prototype described in doc-1 was never committed. Implementation plan: (1) bootstrap.py with setup_services() extracting service wiring from __main__._run; (2) server.py lifespan (OOMPAH_EMBED_ORCHESTRATOR=1 path); (3) __main__.py --server {uvicorn,granian} + _run_granian(); (4) granian as optional pyproject.toml dep; (5) make run-granian target; (6) uv lock refresh; (7) tests for bootstrap.py + --server arg parsing.
---

author: oompah
created: 2026-06-09 16:14
---
Implementation: Added 5 changes: (1) oompah/bootstrap.py — new module with Services dataclass and setup_services() that extracts service wiring from __main__._run, used by both uvicorn and Granian paths. (2) oompah/server.py — added asynccontextmanager import and _lifespan() ASGI lifespan that, when OOMPAH_EMBED_ORCHESTRATOR=1, calls setup_services() to start orchestrator inside Granian worker's event loop, plus _supervise() task for restart signalling. (3) oompah/__main__.py — added --server {uvicorn,granian} argument; refactored _run() to use setup_services(); added _run_granian() launcher that sets env vars and starts Granian with workers=1/interface=ASGI/loop=uvloop, re-execs on sentinel. (4) pyproject.toml — added granian>=1.0 as optional dep [granian] and to dev extras. (5) Makefile — added run-granian target with granian install guard and help text. uv.lock refreshed (granian v2.7.5 added).
---
<!-- COMMENTS:END -->

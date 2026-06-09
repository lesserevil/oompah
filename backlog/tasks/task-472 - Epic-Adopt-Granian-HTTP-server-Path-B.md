---
id: TASK-472
title: 'Epic: Adopt Granian HTTP server (Path B)'
status: Backlog
assignee: []
created_date: '2026-06-09 04:18'
labels:
  - feature
  - epic
  - 'needs:backend'
  - 'needs:test'
dependencies: []
documentation:
  - backlog/docs/doc-1 - Granian-HTTP-server-migration-plan.md
priority: high
ordinal: 189000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make the prototype Granian ASGI server production-ready and ship it behind --server granian (uvicorn stays default until a go/no-go benchmark). Granian keeps the existing FastAPI app (no route rewrites) and runs the orchestrator inside the ASGI lifespan on the worker loop so the WebSocket _broadcast path keeps working (workers=1, shared in-process state). Prototype already in tree: oompah/bootstrap.py, lifespan in oompah/server.py, --server flag in oompah/__main__.py. See doc-1 for full plan, findings, and benchmark (~+23% HTTP throughput single-worker).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Granian path passes automated tests (HTTP, WebSocket broadcast, restart)
- [ ] #2 No 'Task exception was never retrieved' on startup-validation failure
- [ ] #3 uvicorn remains the default; --server granian is opt-in and documented
<!-- AC:END -->

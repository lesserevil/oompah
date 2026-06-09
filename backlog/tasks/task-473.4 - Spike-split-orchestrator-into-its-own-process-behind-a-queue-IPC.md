---
id: TASK-473.4
title: 'Spike: split orchestrator into its own process behind a queue/IPC'
status: Done
assignee: []
created_date: '2026-06-09 04:20'
updated_date: '2026-06-09 15:58'
labels:
  - performance
  - spike
dependencies: []
parent_task_id: TASK-473
priority: high
ordinal: 202000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Evaluate decoupling the orchestrator from the web process: orchestrator runs standalone and the web layer subscribes (queue/IPC/pubsub) for WebSocket push. This removes the shared-loop coupling entirely and would unlock Granian multi-worker (workers>1). Produce a design recommendation and rough effort estimate; do not implement here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Written design + tradeoffs + effort estimate for orchestrator/web process split
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 15:33
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 15:33
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 15:40
---
Agent failed: opencode serve exited with code -15. stderr: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 15:40
---
Run #1 [attempt=1, profile=standard, role=standard -> Opencode/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 6m 35s
- Log: TASK-473.4__20260609T153410Z.jsonl
---

author: oompah
created: 2026-06-09 15:48
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:51
---
Understanding: This task asks for a design recommendation + effort estimate for decoupling the orchestrator from the web process (to enable Granian multi-worker). Key finding: TASK-469.5.1 already designed and implemented a SQLite-backed IPC layer (oompah/ipc.py) for the API/scheduler split, and plans/service-split.md documents that architecture. However, the specific concern here — WebSocket push across process boundaries for Granian workers>1 — is only listed as future work (#5 in that doc). Plan: confirm the existing design covers the acceptance criteria, and if not, extend plans/service-split.md with the WebSocket broadcasting analysis, tradeoffs, and effort estimate specific to unlocking Granian multi-worker.
---

author: oompah
created: 2026-06-09 15:56
---
Discovery: TASK-469.5.1 already designed and implemented the SQLite IPC layer (oompah/ipc.py) for the API/scheduler split — plans/service-split.md is the design doc. However the specific deliverable for TASK-473.4 (written design + tradeoffs + effort estimate for unlocking Granian workers>1) is NOT covered: WebSocket broadcasting across the process boundary is only a roadmap note in service-split.md, and no explicit tradeoffs/effort breakdown exists for the Granian-specific angle. Proceeding to produce the required spike document.
---

author: oompah
created: 2026-06-09 15:58
---
Implementation: Produced plans/orchestrator-process-split.md — the required spike design. Not a duplicate: TASK-469.5.1 implemented SQLite IPC for API/scheduler split but never produced a Granian-multi-worker-focused design or explicit tradeoffs/effort estimate. The new doc covers: problem statement, prior work, gap analysis (WebSocket broadcasting), 4 design options evaluated, recommendation (SQLite ws_events polling — zero new deps), explicit tradeoffs table, 7.5 person-day effort estimate with work breakdown, and sequencing recommendation. Committed to epic-TASK-473 branch.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Produced plans/orchestrator-process-split.md: spike design + tradeoffs table + 7.5-day effort estimate for decoupling the orchestrator into its own process to unlock Granian workers>1. Not a duplicate of TASK-469.5.1 — that task implemented SQLite IPC for GIL contention but never addressed WebSocket broadcasting across processes or the Granian-multi-worker angle. Recommendation: extend existing IPC layer with a ws_events relay table polled at 200 ms by API workers (zero new dependencies). Full breakdown: fix CI (0.5d), ws_events schema+methods (1d), orchestrator wiring (0.5d), relay loop (0.5d), CLI modes (1.5d), Granian workers=2 validation (1d), integration tests (2d), docs (0.5d).
<!-- SECTION:FINAL_SUMMARY:END -->

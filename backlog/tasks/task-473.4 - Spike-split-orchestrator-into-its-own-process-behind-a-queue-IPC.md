---
id: TASK-473.4
title: 'Spike: split orchestrator into its own process behind a queue/IPC'
status: Open
assignee: []
created_date: '2026-06-09 04:20'
updated_date: '2026-06-09 15:56'
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
<!-- COMMENTS:END -->

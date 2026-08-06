---
id: OOMPAH-763
type: epic
status: In Progress
priority: 1
title: Build a unified, durable, live workflow engine
parent: null
children:
- OOMPAH-764
- OOMPAH-765
- OOMPAH-766
- OOMPAH-767
- OOMPAH-768
- OOMPAH-769
- OOMPAH-770
- OOMPAH-771
- OOMPAH-806
- OOMPAH-807
- OOMPAH-808
- OOMPAH-809
- OOMPAH-810
- OOMPAH-811
- OOMPAH-814
- OOMPAH-815
- OOMPAH-816
- OOMPAH-817
- OOMPAH-822
- OOMPAH-831
- OOMPAH-840
- OOMPAH-841
- OOMPAH-846
- OOMPAH-847
- OOMPAH-848
- OOMPAH-849
- OOMPAH-850
- OOMPAH-851
- OOMPAH-852
blocked_by: []
start_blocked_by: []
labels:
- human-only
- architecture
assignee: null
created_at: '2026-08-04T13:54:42.220415Z'
updated_at: '2026-08-06T04:51:39.645755Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Problem: Oompah task progression is currently implemented by multiple local reconcilers, status writers, process-local authority maps, SQLite ledgers, Git/forge probes, watchdogs, and UI-specific eligibility summaries. Safety is generally fail-closed, but no single machine enforces transition legality or guarantees bounded progress, so operators repeatedly file bugs and manually recover stranded nonterminal work. Scope: implement the complete workflow-engine migration: formal lifecycle contract and liveness invariants; a single task-transition service and journal; unified versioned facts and pure WorkDecision evaluator; durable leased workflow jobs with restart-safe sagas; domain cutovers for integration, terminal audit, review, implementation ownership, and epic landing; a universal liveness controller and truthful alerts; model-based/fault-injection/100-task qualification; and final removal of legacy reconcilers plus orchestrator modularization. Preserve the native Markdown tracker as authoritative for user-visible task status, existing terminal safety guarantees, actor authorization, exact-head fencing, project scoping, and restart recovery throughout staged shadow/enforce rollout. Configuration flags must be OOMPAH_* values in .env/.env.example, not WORKFLOW.md. Required verification: focused tests for every child, complete make test at review-ready heads, state-machine safety and eventual-progress properties, kill/restart injection at every persistence boundary, historical incident replays for OOMPAH-562/731/732/739/748/749/751, and a multi-project 100-task soak. Acceptance: one transition writer, one shared decision for scheduler/UI/watchdogs, every nonterminal task has exactly one durable disposition and bounded reassessment, normal automatic recovery is not an operator warning, all historical incidents recover without manual mutation, legacy paths are deleted, and production workflow code is materially reduced after migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:07
---
Implementation ownership: this entire hierarchy is reserved for direct project-owner execution, not Oompah agent dispatch. Child tasks remain Backlog until their hard-start dependencies are complete; the active leaf will be owner-claimed in sequence so board state stays truthful. Foundation begins with OOMPAH-772. Accidental duplicate creations OOMPAH-799 through OOMPAH-802 were owner-archived; canonical children are OOMPAH-773, OOMPAH-774, OOMPAH-776, and OOMPAH-778.
---
author: oompah
created: 2026-08-04 21:31
---
Program graph repair: OOMPAH-775 now hard-starts after overlapping watchdog fix OOMPAH-806; OOMPAH-792 now hard-starts after production wiring OOMPAH-804; final retirement epic OOMPAH-771 waits for OOMPAH-769 and OOMPAH-806; qualification soak OOMPAH-797 waits for standalone gate-stability bug OOMPAH-805; obsolete historical OOMPAH-766 -> OOMPAH-769 start blocker removed. Independent audit found no cycles or missing refs after these changes.
---
author: oompah
created: 2026-08-05 06:05
---
Reconciled current main exact-head/cross-loop delivery fencing (OOMPAH-818/820) into the systemic workflow parent at ceafd8e14100964ee84821c4fbe75cf0ac772f43. The semantic merge keeps queue-generation/action-time CAS as the outer fence and routes the actual stalled-task reopen through OOMPAH-806 TaskTransitionService before posting the watchdog sentinel. Verification so far: 1,665 focused checks pass across watchdog/gate/transition authority, workflow shadow/durability, exact review-generation delivery, server/webhook/tracker behavior; terminal mutation scan 8/8 and secret scan pass. Branch is clean and pushed. A full exact-head gate will run after the currently active independent auditors release the four-worker resource lane.
---
author: oompah
created: 2026-08-05 14:48
---
Operator checkpoint boundary (2026-08-05): finish only the already-active OOMPAH-815 CI repair and the bounded in-flight batch OOMPAH-505/OOMPAH-523/OOMPAH-807/OOMPAH-821. Keep project dispatch paused; do not start the next systemic-program stage (including OOMPAH-781/OOMPAH-791/OOMPAH-804) in this work session. Once the active batch reaches safe terminal or clearly handed-off states, publish a concise clean-state handoff covering exact heads, tracker states, validation/alert health, remaining dependency order, and cleanup status, then stop.
---
author: oompah
created: 2026-08-05 14:53
---
Operator direction supersedes the prior checkpoint-only boundary: continue the systemic workflow program through completion, using child agents for safe independent work and allowing the Oompah server to implement dispatchable tasks where current capabilities permit. The project remains paused only while the bounded OOMPAH-505/523/807/821 validation batch and OOMPAH-815 repair drain; resume staged dispatch after that safe boundary.
---
<!-- COMMENTS:END -->

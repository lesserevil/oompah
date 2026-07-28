---
id: OOMPAH-530
type: task
status: In Progress
priority: 2
title: Add atomic duplicate-preflight claims and recovery
parent: OOMPAH-528
children: []
blocked_by:
- OOMPAH-529
labels:
- focus-complete:duplicate_detector
- 'focus-complete:'
assignee: null
created_at: '2026-07-28T21:18:51.634942Z'
updated_at: '2026-07-28T21:33:13.186295Z'
work_branch: epic-OOMPAH-528
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 075e8330-d160-4439-8f15-689e3252bfd8
oompah.work_branch: epic-OOMPAH-528
---
## Summary

Build the claim lifecycle that lets a duplicate-screening agent run while the task remains Open. This task depends on the revision-aware metadata record from OOMPAH-529.

Implementation scope:
- Add claim, renew, release, and expire operations for duplicate preflight. A claim must have an opaque claim ID, owner/run identity, claimed/expiry timestamps, detector version, and the task fingerprint observed at claim time.
- Serialize claim mutations with the existing per-project tracker write-lock mechanism or an equivalent tracker-scoped critical section. Re-read the issue and metadata inside the lock before deciding.
- Claim only an Open, non-terminal task whose current fingerprint lacks a current pass and which has no live implementation claim/agent.
- Make duplicate preflight and implementation dispatch mutually exclusive. The implementation eligibility check must reject an unchecked, stale, or actively-screened task when model-backed screening is required.
- Release must be compare-and-set by claim ID so a late worker cannot clear a newer claim.
- Expired/orphaned claims must become eligible for retry after restart; do not change the task status and do not require manual repair.
- If the task changes during a run, completion must not record a current pass for the new revision. Release the old claim and leave the task stale/unchecked for another screening pass.

Relevant context/files:
- oompah/orchestrator.py owns dispatch claims and active-agent state.
- oompah/terminal_transition_coordinator.py demonstrates project write locking and fingerprint-aware compare-and-set behavior.
- oompah/state.py or the current persisted orchestrator state owns restart recovery data.
- Use the metadata helpers introduced by OOMPAH-529 instead of duplicating parsing.

Required tests:
- Two concurrent claim attempts result in exactly one winner.
- A live preflight claim blocks implementation dispatch and a live implementation agent blocks preflight.
- Wrong/old claim IDs cannot renew, release, or complete a newer claim.
- Expired claims retry after restart.
- Editing a task during screening prevents a stale pass from being recorded.
- Terminal/non-Open tasks cannot be claimed.

Acceptance criteria:
1. The claim lifecycle is atomic at the tracker/project boundary and safe across scheduler ticks.
2. No execution path can run duplicate preflight and implementation concurrently for the same task.
3. Restart and timeout recovery are automatic and observable in logs/metrics.
4. The task stays Open throughout a successful no-duplicate preflight.
5. Focused concurrency and recovery tests pass through the appropriate Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:26
---
Claimed by the current interactive Codex session before OOMPAH-529 completion. Work continues on epic-OOMPAH-528; do not dispatch another agent.
---
author: oompah
created: 2026-07-28 21:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 21:31
---
Understanding: I will first perform the mandated duplicate screening by searching related task/docs history and reviewing each plausible candidate in full. If no duplicate is confirmed, I will record the evidence and hand off for implementation without changing code.
---
author: oompah
created: 2026-07-28 21:32
---
Discovery: No clear duplicate confirmed. Full task views reviewed for OOMPAH-528 (parent), OOMPAH-529 (revision-aware evidence prerequisite), OOMPAH-531 (capacity scheduling), OOMPAH-532 (verdict completion), OOMPAH-533 (API/dashboard), and OOMPAH-534 (end-to-end/docs). Historical candidates OOMPAH-217 (duplicate-focus handoff), OOMPAH-156 (error_watcher event deduplication), and OOMPAH-160 (atomic native-task writes/corrupt intake recovery) do not implement task-scoped preflight claims, implementation mutual exclusion, or restart-safe claim recovery. No code changed and no tests were run in this screening-only focus.
---
author: oompah
created: 2026-07-28 21:32
---
Focus handoff: duplicate_detector

1. Outcome: Duplicate screening found no confirmed duplicate; OOMPAH-530 is a distinct implementation child of OOMPAH-528.
2. Evidence/decisions: Reviewed full task descriptions and comments for OOMPAH-528 through OOMPAH-534, plus OOMPAH-217, OOMPAH-156, and OOMPAH-160 using oompah task view. Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for duplicate preflight, screening, detector, fingerprint, claim, lease, dispatch, recovery, and lock terms. The closest records cover revision-aware metadata (529), scheduler capacity (531), verdict CAS/completion (532), operator surfaces (533/534), generic focus handoff (217), error-event deduplication (156), or atomic task-file/intake recovery (160); none covers this task’s claim lifecycle.
3. Remaining work/risks: Implement claim/renew/release/expire with tracker-scoped locking, re-read fingerprint and metadata inside the lock, mutual exclusion with implementation agents, CAS by opaque claim ID, restart/timeout recovery, and stale-revision completion protection. Add the required concurrency, recovery, terminal/Open eligibility, and edit-during-screening tests. Relevant implementation areas are oompah/orchestrator.py, oompah/state.py, oompah/terminal_transition_coordinator.py, the OOMPAH-529 metadata helpers, and their focused tests.
4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-28 21:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 21
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 32s
- Log: OOMPAH-530__20260728T213109Z.jsonl
---
author: oompah
created: 2026-07-28 21:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:32
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 21:32
---
Agent completed successfully in 1s
---
author: oompah
created: 2026-07-28 21:32
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: normal, Duration: 1s
---
author: oompah
created: 2026-07-28 21:32
---
Focus handoff from `` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 21:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:33
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 21:33
---
Understanding: implement revision-aware duplicate-preflight claims (claim/renew/release/expire) under the project tracker lock, with mutual exclusion against implementation agents, restart/timeout recovery, claim-ID CAS, and stale-revision protection. I will inspect the OOMPAH-529 metadata work plus dispatch/state locking, then add focused race, recovery, CAS, revision-change, and eligibility tests.
---
<!-- COMMENTS:END -->

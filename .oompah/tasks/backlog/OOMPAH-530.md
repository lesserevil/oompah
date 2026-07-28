---
id: OOMPAH-530
type: task
status: Backlog
priority: 2
title: Add atomic duplicate-preflight claims and recovery
parent: OOMPAH-528
children: []
blocked_by:
- OOMPAH-529
labels: []
assignee: null
created_at: '2026-07-28T21:18:51.634942Z'
updated_at: '2026-07-28T21:20:14.262810Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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


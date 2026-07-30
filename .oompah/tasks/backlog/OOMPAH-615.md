---
id: OOMPAH-615
type: bug
status: Backlog
priority: 1
title: Fence implementation retries when terminal audits take ownership
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:22:18.934506Z'
updated_at: '2026-07-30T20:22:18.934506Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-591

Implementation scope: Fix the reproduced ownership races between ordinary worker retries and terminal-audit dispatch. A supported Done request that stages a task in In Validation must request an immediate scheduler refresh. The same transition must atomically invalidate every pending, delayed, or callback-owned implementation retry before auditor ownership becomes visible, and a retry callback must re-read canonical task state immediately before dispatch so it cannot reopen or reclaim In Validation, Done, Merged, Archived, or Needs Human work. Preserve ordinary retry behavior for genuinely In Progress/Open work and keep auditor retry rotation independent. Relevant files include oompah/server.py terminal transition handling, oompah/orchestrator.py retry scheduling/callback and dispatch events, and related state snapshots. Tests: deterministically reproduce (1) terminal audit staged between worker exit and delayed retry callback, (2) callback already awakened while the terminal transition cancels ownership, (3) In Validation staging wakes the audit lane without waiting for the safety-net poll, and (4) normal retries still dispatch. Assert there is never simultaneous implementation/auditor ownership and task state cannot regress from In Validation to In Progress/Open. Run focused server/orchestrator/auditor tests and make test. Acceptance criteria: staged audits wake immediately; terminal transition wins every implementation-retry race; no stale implementation agent can launch after audit staging; live OOMPAH-591 can be requeued and receive exactly one auditor; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


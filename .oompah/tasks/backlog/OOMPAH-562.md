---
id: OOMPAH-562
type: bug
status: Backlog
priority: 1
title: Recover integration queues blocked by stale epic ancestry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:08:21.827812Z'
updated_at: '2026-07-29T21:11:10.483646Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-561

Parallel epic integration can deadlock with every submission in Ready to Integrate and attempts=0 when a parent epic branch predates already-Merged finish dependencies. Current claim_next correctly requires dependency code to be reachable from the epic branch, but epic staleness maintenance is observation-only, so no executor or repair agent can make the required base reachable. Live reproduction: OOMPAH-459 is 26 commits behind main/5 ahead and all eight queued children wait on merged OOMPAH-475/467/464/466 ancestry; OOMPAH-460 is 34 behind and all six children wait behind OOMPAH-459. Scope: classify this as the existing synchronization policy's required-base condition; schedule one safe epic rebase/reconciliation action (never direct epic-to-epic sync), prevent duplicate repair dispatch, expose actionable queue/maintenance state, and resume integration after the repaired epic head is published. Preserve explicit finish-order and terminal-audit gates. Relevant files: oompah/orchestrator.py integration queue processing and epic synchronization policy, queue/API status summaries, and focused integration/staleness tests. Acceptance criteria: a Ready queue whose first task depends on merged code absent from its epic branch automatically enters a bounded repair path; after repair, eligible items are claimed in dependency order; no permanent attempts=0 queue remains; failures surface an actionable error without losing private heads; make test passes.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

---
id: OOMPAH-861
type: task
status: Backlog
priority: null
title: Keep accepted branch identity immutable after owner-submit gate failure
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T13:27:20.466495Z'
updated_at: '2026-08-06T13:27:20.466495Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live OOMPAH-860 regression on 2026-08-06 after OOMPAH-815 reached Done. OOMPAH-860 is a child of OOMPAH-763 with null work_branch. Direct-owner work was prepared on epic-OOMPAH-763--task-OOMPAH-860, but the authenticated submit validator rejected it and required plain OOMPAH-860. The exact same validated head was then pushed/submitted from OOMPAH-860; integration authority recorded task_branch=OOMPAH-860 and the exact full gate ran that branch. When the gate failed, CI repair dispatch recomputed epic-OOMPAH-763--task-OOMPAH-860, found the registered worktree still correctly checked out on the accepted OOMPAH-860 branch, and refused to reset it. This recreates the precise split identity that OOMPAH-815 promised to eliminate. Implementation scope: trace owner-claim submit validation, accepted IntegrationRecord persistence/projection, transition to Needs CI Fix/In Progress, and repair workspace creation; once a branch+head is accepted, persist and reuse that immutable branch for every repair/retry/audit path, including null/stale work_branch and parent status changes. Eliminate any post-accept fallback that recomputes hierarchy; make submit validation and repair resolution use the same canonical resolver/generation. Preserve exact remote-head/ancestry proof, dirty-worktree no-reset safety, concurrent resubmit fencing, and hierarchical branches before acceptance. Required tests: exact OOMPAH-860 sequence (hierarchical submit rejected, plain submit accepted, gate failure, repair reuses plain worktree); restart between acceptance/failure/repair; null and stale work_branch; parent/child status changes after acceptance; concurrent same-head submit; invalid remote/head/ancestry fails before mutation; canonical hierarchical control; no repeated zero-turn dispatch loop. Acceptance: every accepted submission can be repaired on the exact persisted branch without manual checkout/metadata edits, and submit validation can never require a branch that the subsequent repair dispatcher rejects.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


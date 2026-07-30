---
id: OOMPAH-576
type: task
status: Open
priority: null
title: Reject integration submissions from the wrong checkout before mutating task
  worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:55:54.699694Z'
updated_at: '2026-07-30T13:34:32.146120Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a0d0bdf76fa62b3007a3a55c9f010ba8c5e02c9d7ca4e709421b245ffd9f644
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4a8e46f1-7e63-433e-add3-a8411a558e32
  claim_owner: 42623072-9e4e-4956-a81f-a5c79aedc624
  claimed_at: '2026-07-30T13:34:26.813977+00:00'
  claim_expires_at: '2026-07-30T14:04:26.813977+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 7475d555-9b18-48eb-a1d0-08962bd6dfee
---
## Summary

Implementation scope: harden task submission and integration worktree preparation so a submission made from the service/default-branch checkout cannot overwrite an existing task's recorded work branch or reset that task's live worktree to origin/main. Validate that the submitted local branch matches the task's expected work-branch namespace and pushed remote head before updating the queue; make integration worktree preparation fail closed when the queue branch disagrees with an already-registered worktree branch, without running reset. Relevant context/files: oompah/task_cli.py submit payload construction, server submit endpoint, oompah/integration_queue.py, oompah/integration_executor.py, and ProjectStore worktree preparation. Regression observed on OOMPAH-483: submitting from /home/shedwards/src/oompah queued task_branch=main, then the executor reset the registered epic-OOMPAH-459--task-OOMPAH-483 worktree from bc448cf08 to origin/main; the remote branch preserved the work and an operator restored it by fast-forward. Tests: cover wrong-checkout submit rejection, unchanged queue record, unchanged registered task worktree HEAD/branch, correct task-worktree resubmission, and no destructive reset on branch mismatch. Acceptance criteria: wrong-checkout submission returns an actionable error before tracker/queue/worktree mutation; correct submissions still integrate; a malformed/stale queue row cannot rewrite a registered worktree.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 13:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 13:34
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

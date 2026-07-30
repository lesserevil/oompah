---
id: OOMPAH-627
type: bug
status: Ready to Integrate
priority: 1
title: Preserve integrated evidence when creating auditor worktrees
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:09:32.117751Z'
updated_at: '2026-07-30T22:12:22.804315Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-627
  head_sha: 2a8fc4a4b3a101c15e2fea0608480f783f9f3e28
  submitted_at: '2026-07-30T22:12:20.717648+00:00'
  updated_at: '2026-07-30T22:12:20.717648+00:00'
---
## Summary

Implementation scope: separate completion-auditor workspace creation from implementation-branch initialization for parallel epic children. An auditor must check out the existing task branch without rewriting oompah.work_branch or replacing an integrated oompah.integration record with state working. Preserve normal implementation dispatch behavior and private-branch synchronization. Relevant context: dispatching the OOMPAH-625 auditor at 22:06 recreated its worktree and changed its already-integrated metadata to working, erasing integrated_sha while the audit was in progress. Tests: reproduce workspace creation for an integrated parallel-epic child in auditor mode, assert integration metadata is untouched and the existing private branch is used, assert implementation mode still writes working metadata, and run focused workspace/auditor tests plus the Makefile gate. Acceptance criteria: auditor launch is read-only with respect to integration/work-branch metadata; implementation launch remains unchanged; focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 22:09
---
Claimed directly for the active race repair. The human-only label prevents duplicate server dispatch while the operator-owned branch is being prepared.
---
author: oompah
created: 2026-07-30 22:12
---
Implemented an explicit persist_dispatch_metadata boundary. Forced API and ACP auditor setup passes false, so an existing private task branch is checked out without replacing integrated evidence; implementation dispatch retains the prior working-record write. Verification: 33 focused parallel-workspace/ACP/orchestrator tests and 8 ACP handoff tests passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 22:12
---
Keep auditor worktree creation read-only with respect to work-branch and integration metadata.
---
<!-- COMMENTS:END -->

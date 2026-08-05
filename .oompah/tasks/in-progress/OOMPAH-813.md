---
id: OOMPAH-813
type: task
status: In Progress
priority: null
title: Fence revoked accepted-submission worker exits with the resolved project
parent: OOMPAH-768
children: []
blocked_by:
- OOMPAH-782
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T23:50:36.091912Z'
updated_at: '2026-08-05T00:21:24.214984Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-813
  head_sha: 7eada51f6fe7ea384c02317654c0b376183fb7af
  submitted_at: '2026-08-05T00:04:04.526160+00:00'
  updated_at: '2026-08-05T00:04:04.526160+00:00'
---
## Summary

Bug reproduction: in Orchestrator._on_worker_exit, the accepted_submission_record && revoked path calls _handle_revoked_submission_exit(project_id=project_id, ...) before project_id is assigned later in the method. A revoked worker that has already submitted therefore raises NameError instead of executing the safety recovery path. This predates the durable-domain stack but is present in its exact review head and Ruff reports F821. Implementation scope: resolve the project identity before any revoked-submission branch, preserve exact project/task/run authority fencing, and keep later worker-exit handling on the same resolved project without shadowing or cross-project fallback. Relevant code: oompah/orchestrator.py _on_worker_exit and _handle_revoked_submission_exit. Required tests: exercise _on_worker_exit itself (not only the helper) with an accepted submission plus revoked authority; assert no NameError, exact project is forwarded, cross-project records cannot be handled, and ordinary non-revoked exit behavior is unchanged. Run focused worker-exit/submission-fencing suites and terminal mutation scan. Acceptance: every revoked accepted-submission exit deterministically reaches the project-scoped recovery handler and never reads an uninitialized identity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 23:56
---
Implementation started on exact OOMPAH-782 base a3948097f in branch epic-OOMPAH-768--task-OOMPAH-813. Scope is the minimal _on_worker_exit project-identity initialization fix plus wrapper-level revoked, cross-project, and non-revoked regression coverage; branch will remain unsubmitted for ordered landing.
---
author: oompah
created: 2026-08-05 00:02
---
Implementation checkpoint: _on_worker_exit now freezes the exact live run project before cleanup/awaits, uses that same scope throughout later exit handling, and the revoked-submission helper rejects missing, changed, cross-project, or cross-task records without tracker mutation. Verification: 100 focused submission-fencing/run-identity/provider-retirement/task-handoff/auditor-exit tests passed; terminal mutation scan passed 8/8; focused Ruff F821 and diff checks passed.
---
author: oompah
created: 2026-08-05 00:03
---
Completed and pushed exact task head 7eada51f6fe7ea384c02317654c0b376183fb7af on epic-OOMPAH-768--task-OOMPAH-813, with direct parent a3948097f27f4e84ac0f2375408ac05f4e419d2c. Focused verification remains green: 100 tests, terminal mutation scan 8/8, Ruff F821, and diff check. Branch is clean and up to date with origin. Per ordered-landing handoff, OOMPAH-813 remains In Progress/claimed and has not been submitted; project owner should submit only after OOMPAH-782 lands.
---
author: oompah
created: 2026-08-05 00:04
---
Fixed revoked accepted-submission exit project fencing at exact head 7eada51f6fe7ea384c02317654c0b376183fb7af, directly based on OOMPAH-782 a3948097f. Wrapper/cross-project/non-revoked regressions included; 100 focused tests, terminal scan 8/8, Ruff F821 and diff checks pass.
---
author: oompah
created: 2026-08-05 00:19
---
Independent exact-head review found a second-order run-fencing race, reproduced in memory: _handle_revoked_submission_exit awaits preserve_worktree_changes; if a replacement RunningEntry is installed during that await, _remove_running_entry correctly returns false but the helper ignores it, clears replacement shared-claim state, and applies the retired run accepted record to the tracker. Reproduction at 7eada51f6: replacement entry preserved, both replacement claims cleared, one stale tracker update. Task returned to In Progress and claimed for repair. Add an interleaving regression and revalidate exact current run after the await/before every shared-state or tracker mutation; stale retired work must return with zero side effects.
---
author: oompah
created: 2026-08-05 00:21
---
Acceptance-blocker repair implemented: revoked submission recovery now uses the identity-safe running-entry removal as its final post-preservation compare-and-remove and returns without clearing claims or touching tracker task data when a replacement generation owns the slot. Added deterministic executor interleaving regression that installs a replacement during preserve_worktree_changes and verifies running/claimed/claimed_issues remain intact with no stale tracker fetch/update. Focused matrix passes 101 tests; Ruff F821, git diff --check, and terminal mutation scan 8/8 pass. Preparing commit/push; task remains unsubmitted and claimed for coordinator re-audit.
---
<!-- COMMENTS:END -->

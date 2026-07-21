---
id: OOMPAH-314
type: bug
status: Done
priority: 1
title: Deliver only selected commits to release branches and monitor release CI
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T17:25:55.951557Z'
updated_at: '2026-07-21T18:00:00.912298Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 42a5cb3f-cc02-48d8-8d15-585109da3db5
---
## Summary

Fix release delivery after PR #303 merged all of main into trickle release/0.11 despite an explicit selected-commit delivery. The queue currently calls cherry_pick_delivery with sync_source_branch=True, merging origin/main before applying source_commits. Selected delivery must apply only its immutable source_commits and must not merge the complete source branch. Add post-merge release-branch CI monitoring that creates actionable Oompah remediation work for failed release builds.\n\nTests: regression proves a selected subset cannot introduce an unselected main commit; queue integration verifies sync_source_branch is false; release CI failure fixture creates/surfaces remediation; conflict behavior remains actionable.\n\nAcceptance: no selected delivery can change a target branch except through its selected commits and required delivery metadata; release CI failure is visible/actionable in Oompah.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 17:31
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 17:31
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-21 17:36
---
Implemented the selected-commit delivery guard in PR #468: the orchestrator no longer requests a source-branch merge before applying selected delivery commits; focused executor tests pass. Corrective Trickle PR #304 is open against release/0.11 to reverse the unintended full-main merge in release-delivery PR #303 (including TRICKLE-29, TRICKLE-30, and TRICKLE-31); cargo test --workspace passes. Trickle remains paused until the correction has merged.
---
author: oompah
created: 2026-07-21 17:36
---
Understanding: The bug is in oompah/orchestrator.py where cherry_pick_delivery is called with sync_source_branch=True (line ~9572). This causes the queue to merge origin/main into the release branch BEFORE applying selected source_commits, which means a selected-commit delivery inadvertently pulls in ALL of main. Fix: change sync_source_branch=True to False (the default). Additionally need to add: (1) regression test proving selected subset cannot introduce unselected commits, (2) queue integration test verifying sync_source_branch=False, (3) release CI failure remediation test, (4) verify conflict behavior stays actionable. All tests currently pass (9951 pass). Branch OOMPAH-314 has no commits yet — implementing fix now.
---
author: oompah
created: 2026-07-21 17:40
---
Discovery: Root cause confirmed at oompah/orchestrator.py:9572 - cherry_pick_delivery called with sync_source_branch=True, which merges origin/main into the release worktree BEFORE applying source_commits. This is the PR #303 regression. Fix is straightforward: remove sync_source_branch=True. Additionally implementing: (1) ci_remediation_task_id field on ReleaseDelivery, (2) _monitor_merged_delivery_ci method on Orchestrator to poll release branch CI after delivery merges and dispatch remediation tasks on CI failure, (3) get_branch_head_sha SCM method to support the CI check. Tests to add in test_release_delivery_executor.py and test_release_delivery_queue.py (integration with queue verifying sync_source_branch=False).
---
author: oompah
created: 2026-07-21 17:59
---
Implementation complete: (1) Fixed sync_source_branch=True→False in orchestrator.py:9564 (the PR #303 root cause). (2) Added ci_remediation_task_id field to ReleaseDelivery + _MUTABLE_FIELDS. (3) Added get_branch_head_sha/get_ci_status_for_sha/get_branch_ci_status to SCMProvider base class and implemented get_branch_head_sha+get_ci_status_for_sha on GitHubProvider. (4) Added _monitor_merged_delivery_ci, _check_and_remediate_delivery_ci, _dispatch_release_ci_fix_task to Orchestrator. (5) Added 4 regression tests to test_release_delivery_executor.py. (6) Created test_release_delivery_ci_monitor.py with 22 tests covering CI monitoring, queue integration (sync_source_branch=False), and SCM methods. Full suite: 9977 passed.
---
author: oompah
created: 2026-07-21 17:59
---
Verification: Full test suite passes: 9977 passed, 36 skipped, 0 failures. New tests: 26 added (22 in test_release_delivery_ci_monitor.py + 4 in test_release_delivery_executor.py). Branch OOMPAH-314 pushed to origin. All acceptance criteria met: (1) no selected delivery can change a target branch except through its selected commits; (2) release CI failure is visible/actionable in Oompah via ci_remediation_task_id and _dispatch_release_ci_fix_task.
---
author: oompah
created: 2026-07-21 17:59
---
Completion: Delivered OOMPAH-314 with these changes: (1) Bug fix: orchestrator.py sync_source_branch=True→False — prevents unselected main commits from entering release branches. (2) ReleaseDelivery.ci_remediation_task_id field for idempotent CI remediation tracking. (3) SCMProvider.get_branch_head_sha/get_ci_status_for_sha/get_branch_ci_status methods (GitHubProvider implemented, base class default returns None/''/''). (4) Orchestrator._monitor_merged_delivery_ci + _check_and_remediate_delivery_ci + _dispatch_release_ci_fix_task for post-merge release branch CI failure detection and actionable task creation. (5) 26 new tests: regression proofs, queue integration sync_source_branch=False guard, CI failure fixture, conflict behavior, SCM methods.
---
author: oompah
created: 2026-07-21 18:00
---
Fixed sync_source_branch=True→False bug (PR #303 regression) and added post-merge release CI monitoring with actionable remediation tasks. 26 new tests covering all acceptance criteria.
---
<!-- COMMENTS:END -->

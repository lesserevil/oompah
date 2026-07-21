---
id: OOMPAH-336
type: bug
status: Done
priority: 1
title: Route release CI remediation to native project tasks
parent: null
children: []
blocked_by: []
labels:
- release-ci-failure
assignee: null
created_at: '2026-07-21T22:22:50.075291Z'
updated_at: '2026-07-21T22:42:51.712690Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 38a546ae-5b30-440f-af8c-f0142f4673cb
---
## Summary

Release-delivery CI failures must create actionable native tasks in the affected project, with CI-fix routing and explicit acceptance criteria. Existing remediation records that point to an unrelated external issue must be replaced by a project-local task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:26
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 22:26
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-21 22:27
---
Understanding: This task requires that release-delivery CI failures create actionable native tasks in the affected project (with ci-fix routing and acceptance criteria), and that stale remediation records pointing to unrelated external issues are replaced by project-local tasks. PR #485 'Route release CI remediation to project tasks' was just merged to main. I need to verify CI is green after the merge, and fix any failures if they exist.
---
author: oompah
created: 2026-07-21 22:32
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 22:32
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-21 22:38
---
Understanding: CI Failure Fixer agent dispatched (third pass). Previous agents identified that PR #485 'Route release CI remediation to project tasks' was merged to main. My job is to verify CI is green after the merge and fix any remaining failures. Checking local and remote test results now.
---
author: oompah
created: 2026-07-21 22:39
---
Discovery: PR #485 (commit c384cf949) implemented the required changes in oompah/orchestrator.py and tests/test_release_delivery_ci_monitor.py. The changes: (1) Added _has_live_release_ci_remediation() to check if a recorded ci_remediation_task_id still exists in the project tracker — stale/missing IDs return False so a new project-local task is created. (2) Changed _check_and_remediate_delivery_ci() to use _tracker_for_project() instead of the global tracker. (3) Added acceptance criteria and 'ci-fix' label to remediation tasks. The GitHub Actions CI run 29873724858 for the PR#485 merge shows 'completed success' (10734 passed, 5 skipped). Local tests also pass: 10508 passed, 36 skipped. All 23 tests in test_release_delivery_ci_monitor.py pass including the new test_stale_global_remediation_reference_is_replaced.
---
author: oompah
created: 2026-07-21 22:39
---
Verification: No CI failures found. CI is green both on GitHub (run 29873724858: 10734 passed, 5 skipped) and locally (10508 passed, 36 skipped). All 23 tests in tests/test_release_delivery_ci_monitor.py pass. The implementation from PR #485 is complete and correct. No additional fixes are needed.
---
author: oompah
created: 2026-07-21 22:39
---
Completion: PR #485 'Route release CI remediation to project tasks' (commit c384cf949) was successfully merged to main. Implementation delivers: (1) Release-delivery CI failures now create project-local tasks via _tracker_for_project() instead of the global tracker. (2) Stale/external remediation task IDs are detected by _has_live_release_ci_remediation() — missing tasks trigger a new project-local task creation. (3) Remediation tasks include explicit acceptance criteria and 'ci-fix' label for routing. (4) 3 new tests cover: acceptance criteria content, ci-fix label, and stale global reference replacement. CI is green (10734 passed on GitHub, 10508 passed locally).
---
author: oompah
created: 2026-07-21 22:42
---
PR #485 merged: release-delivery CI failures now create actionable project-local tasks via project tracker, stale global remediation references auto-replaced, ci-fix routing label and acceptance criteria added. CI green (10734 passed on GitHub, 10508 locally).
---
<!-- COMMENTS:END -->

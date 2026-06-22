---
id: OOMPAH-20
type: task
status: In Progress
priority: 1
title: Run CI for release branches
parent: OOMPAH-17
children: []
blocked_by:
- OOMPAH-18
labels:
- release:1.0
assignee: null
created_at: '2026-06-22T01:15:01.066849Z'
updated_at: '2026-06-22T02:08:12.577632Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a059ec85-8027-4bf8-813c-ebc529e68cfc
---
## Summary

Plan: plans/oompah-1.0-release.md#epic-a-define-and-harden-the-10-release-train

WHAT TO DO
Update CI triggers so the normal quality gate runs for release/* branches and pull requests targeting release branches.

HOW TO VERIFY
The workflow configuration includes release/* branch patterns and the changed workflow can be validated through a release-branch test run or an equivalent workflow syntax check.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:04
---
Understanding: OOMPAH-20 asks to add release/* branch patterns to CI triggers so the quality gate runs for release branches and PRs targeting them. As Duplicate Investigator, I will first search for any existing issues covering this same CI trigger change before implementing. Checking .oompah/tasks and plans for overlapping issues now.
---
author: oompah
created: 2026-06-22 02:05
---
DISCOVERY: Confirmed NOT a duplicate. No existing merged, done, or in-progress task covers CI trigger changes for release branches. OOMPAH-18 (done) only updated docs/tests/examples — it did not touch ci.yml triggers. The current .github/workflows/ci.yml only triggers on main: push, pull_request, and merge_group all target [main]. Need to add release/* to all three trigger patterns. This is the only change needed to satisfy the acceptance criteria.
---
author: oompah
created: 2026-06-22 02:08
---
IMPLEMENTATION: Added release/* branch patterns to all three trigger events in .github/workflows/ci.yml (push, pull_request, merge_group). The main branch patterns are preserved. Also added tests/test_ci_workflow.py with 5 tests validating: YAML validity, push/pull_request/merge_group each include release/*, and main is still covered.
---
author: oompah
created: 2026-06-22 02:08
---
VERIFICATION: All 5 new CI workflow tests pass (test_ci_workflow_yaml_is_valid, test_ci_workflow_push_includes_release_branches, test_ci_workflow_pull_request_includes_release_branches, test_ci_workflow_merge_group_includes_release_branches, test_ci_workflow_still_covers_main). Full test suite: 7048 passed, 28 skipped, pre-existing failures unrelated to this change.
---
<!-- COMMENTS:END -->

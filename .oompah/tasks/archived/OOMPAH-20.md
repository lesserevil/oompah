---
id: OOMPAH-20
type: task
status: Archived
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
updated_at: '2026-06-29T14:44:16.886857Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a059ec85-8027-4bf8-813c-ebc529e68cfc
oompah.task_costs:
  total_input_tokens: 83
  total_output_tokens: 2370
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 83
      output_tokens: 2370
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 83
    output_tokens: 2370
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:11:31.786849+00:00'
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
author: oompah
created: 2026-06-22 02:11
---
COMPLETION: Implemented the ci.yml trigger changes and wrote 5 tests in tests/test_ci_workflow.py (all pushed to epic-OOMPAH-17). The PAT lacks workflow scope to push .github/workflows/ci.yml — same constraint as OOMPAH-18/OOMPAH-43. Filed OOMPAH-44 for a maintainer to push the ci.yml change. The exact diff is documented in OOMPAH-44. Tests are on the branch and will pass once ci.yml is updated. This issue is NOT a duplicate — no other task covered CI trigger changes for release branches.
---
author: oompah
created: 2026-06-22 02:11
---
Added release/* patterns to ci.yml (all 3 trigger events) and 5 tests in tests/test_ci_workflow.py. Tests pushed to epic-OOMPAH-17. ci.yml push blocked by PAT workflow scope — OOMPAH-44 filed for maintainer.
---
author: oompah
created: 2026-06-22 02:11
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 47
- Tokens: 83 in / 2.4K out [2.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 46s
- Log: OOMPAH-20__20260622T020352Z.jsonl
---
<!-- COMMENTS:END -->

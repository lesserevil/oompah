---
id: OOMPAH-43
type: task
status: In Progress
priority: 3
title: Update workflow dispatch description from v0.1.0 to v1.0.0 example
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T01:52:58.922363Z'
updated_at: '2026-06-22T02:08:10.177381Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d75e5e06-6779-4d5b-b39e-7dced94024b6
---
## Summary

The cli-release.yml workflow_dispatch input description still says 'e.g. v0.1.0'. A maintainer with workflow scope needs to update it to 'e.g. v1.0.0-draft or v1.0.0'. Blocked in OOMPAH-18 due to PAT lacking workflow scope.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:03
---
UNDERSTANDING: This is NOT a duplicate. OOMPAH-18 was a broader 1.0 update task that explicitly deferred the workflow dispatch description change (v0.1.0 → v1.0.0-draft or v1.0.0) because it lacked PAT workflow scope. OOMPAH-43 is the follow-up filed to complete that specific change. The task is straightforward: update the 'description' field in the workflow_dispatch input in .github/workflows/cli-release.yml. Proceeding to implement.
---
author: oompah
created: 2026-06-22 02:07
---
DISCOVERY: This is not a duplicate. OOMPAH-43 is a deliberate follow-up from OOMPAH-18 (Done). OOMPAH-18 reverted the workflow file change because the PAT lacked workflow scope, and filed this task for a maintainer to complete it. Target: .github/workflows/cli-release.yml line — description: 'Existing release tag to package, e.g. v0.1.0' → 'e.g. v1.0.0-draft or v1.0.0'. Current test file (on main, pre-OOMPAH-18 merge) has no assertion on the dispatch description string. Will add a test to lock in the new description.
---
author: oompah
created: 2026-06-22 02:08
---
IMPLEMENTATION: Updated .github/workflows/cli-release.yml workflow_dispatch input description from 'e.g. v0.1.0' to 'e.g. v1.0.0-draft or v1.0.0'. Added new test test_release_workflow_dispatch_description_shows_v1_examples in tests/test_cli_release_packaging.py to assert the description contains both 'v1.0.0-draft' and 'v1.0.0' strings, locking in the correct example going forward.
---
<!-- COMMENTS:END -->

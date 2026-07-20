---
id: OOMPAH-44
type: task
status: Archived
priority: null
title: Push ci.yml release/* trigger update (requires workflow scope)
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:10:46.422112Z'
updated_at: '2026-07-13T20:45:23.912595Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary



## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:10
---
Follow-up from OOMPAH-20. The agent PAT lacks workflow scope to push .github/workflows/ci.yml changes.

A maintainer with workflow scope must push this change to the epic-OOMPAH-17 branch:

File: .github/workflows/ci.yml
Change: Add 'release/*' to all three trigger branch lists.

Exact change needed:
  on:
    push:
      branches: [main, 'release/*']
    pull_request:
      branches: [main, 'release/*']
    merge_group:
      branches: [main, 'release/*']

The file tests/test_ci_workflow.py is already committed on epic-OOMPAH-17. Once ci.yml is also pushed, all 5 tests will pass. The ci.yml change is currently sitting as an unstaged modification on the agent's local worktree.
---
author: oompah
created: 2026-06-22 14:06
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-44 (Push ci.yml release/* trigger update (requires workflow scope)), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-06-22 14:06
---
This task requires a maintainer credential with GitHub workflow scope to update .github/workflows/ci.yml. It is not dispatchable to the normal agent token.
---
<!-- COMMENTS:END -->

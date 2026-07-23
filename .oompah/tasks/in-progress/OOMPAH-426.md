---
id: OOMPAH-426
type: bug
status: In Progress
priority: 1
title: Block child task PRs from merging to main before their epic completes
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T21:15:59.630196Z'
updated_at: '2026-07-23T21:16:28.840965Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9b589287-01b3-4ddc-8498-b37e946c13ba
---
## Summary

Bug observed on EXOCOMP-57: although it is a child of still-open epic EXOCOMP-9 in a shared-epic project, it opened and YOLO-merged PR #1 directly from EXOCOMP-57 to main. Enforce the merge gate so a non-terminal child task with a parent epic cannot create, approve, or merge a PR targeting the project target branch/main; child work must land on the parent epic branch and only the completed epic may merge to main. Cover PR creation, YOLO merge/reconciliation, and any branch/work_branch override path with regression tests reproducing EXOCOMP-57. Ensure a clear Needs Human handoff if an existing invalid PR requires operator action. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 21:16
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->

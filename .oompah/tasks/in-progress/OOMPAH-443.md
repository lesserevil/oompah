---
id: OOMPAH-443
type: task
status: In Progress
priority: null
title: Require child landing evidence before epic merge and rollup
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-25T17:52:13.750962Z'
updated_at: '2026-07-25T17:52:23.701392Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the shared-epic lifecycle regression exposed by exocomp: epic PRs merged while child tasks were incomplete or had committed work only on separate branches, after which reconciliation blindly marked every child Merged. Before opening or merging an epic rollup PR, require every actionable child to be workflow-complete and verify available child landing/commit evidence is contained by the epic branch or target. When an epic is already merged, do not promote a child to Merged without containment evidence; surface a recoverable state with an actionable explanation instead. Cover incomplete children, stranded child branches, late child completion after parent merge, and valid shared-branch children with regression tests. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


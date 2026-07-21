---
id: OOMPAH-307
type: bug
status: Open
priority: 1
title: Keep shared-epic child work and merge state on the epic branch
parent: null
children: []
blocked_by: []
labels:
- needs:backend
assignee: null
created_at: '2026-07-21T16:27:57.025790Z'
updated_at: '2026-07-21T16:38:37.057417Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix native Markdown task dispatch so child tasks in a shared epic execute on the epic work branch and are not independently merged to main.\n\nObserved reproduction: OOMPAH-286 is a child of epic OOMPAH-285 but was assigned work_branch=OOMPAH-286, target_branch=main, and PR #466. Its status became Merged even though the parent epic branch remains the intended integration branch. Under the shared-only epic model, this child should contribute to OOMPAH-285’s branch and remain non-terminal until the epic is merged.\n\nImplementation requirements:\n- Identify shared epic membership before creating a worktree, branch, PR, or terminal-state transition.\n- Route child commits and tests to the parent epic worktree/work branch; never create a child-to-main PR for a shared child.\n- Record child completion as integrated-on-epic-branch (or equivalent non-terminal state) and show the parent epic/branch in dashboard, detail, CLI/API, and release association views.\n- Promote child tasks to Merged only when the parent epic merge to its target branch is confirmed.\n- Reconcile existing affected children safely: detect independently created child PRs/branches, preserve history, and surface an operator remediation path without rewriting or losing commits.\n\nTests:\n- Shared-epic child dispatch uses parent worktree/branch and creates no child PR to main.\n- Child completion before epic merge is not terminal; after confirmed epic merge it becomes Merged.\n- Regression fixture for OOMPAH-285/OOMPAH-286 routing prevents a child branch/PR #466-style outcome.\n- Existing independently merged child data is diagnosed and does not corrupt the epic branch.\n\nAcceptance criteria:\n- Shared-epic children never bypass the epic branch.\n- UI status explains whether a child is complete on the epic branch versus merged to target.\n- No child is falsely labeled Merged before its epic delivery is merged.\n- Relevant Makefile tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


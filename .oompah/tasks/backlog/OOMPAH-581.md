---
id: OOMPAH-581
type: task
status: Backlog
priority: null
title: Prune merged epic repair workspaces with task-style branch paths
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T04:35:07.041991Z'
updated_at: '2026-07-30T04:35:07.041991Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live cleanup after OOMPAH-459 exposed one remaining owned legacy shape: a terminal epic records work_branch=epic-<id>, but an epic repair/planner run may leave a clean task-style managed worktree at <worktree_root>/<id> on branch <id>. Implementation scope: extend terminal maintenance cleanup in oompah/projects.py/orchestrator cleanup routing to recognize this exact same-identifier repair workspace only for terminal epic records, require the managed registered path and owned exact branch, and delete its worktree plus local/remote ref only when clean and merged/ancestor-safe. Never infer arbitrary paths, shared branches, dirty worktrees, or unmerged heads. Tests: real bare-remote scenario for a terminal epic with canonical epic work_branch plus auxiliary <id> repair worktree/branch; prove cleanup removes the auxiliary workspace and refs, while dirty, unmerged, shared, and different-identifier branches remain preserved. Acceptance criteria: a future OOMPAH-459-shaped repair workspace is removed by the normal aggressive cleanup pass without weakening ownership/ancestry guards; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


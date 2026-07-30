---
id: OOMPAH-617
type: bug
status: Backlog
priority: 1
title: Integrate wrong-checkout submission protection
parent: OOMPAH-587
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:52:01.122820Z'
updated_at: '2026-07-30T20:52:01.122820Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: land the already implemented OOMPAH-576 fix onto the OOMPAH-587 epic branch. Reuse commit 6f5a859b2 from origin/OOMPAH-576; resolve only genuine conflicts with the current epic head. The change must reject task submission from a service/default checkout before queue or tracker mutation, validate the expected task branch and pushed head, and prevent integration worktree reset when a queue branch disagrees with the registered worktree. Relevant files: oompah/acp_tools.py, oompah/integration.py, oompah/integration_executor.py, oompah/projects.py, oompah/server.py, and the existing OOMPAH-576 regression tests. Tests: run focused project/integration/task-handoff/worker-submission suites on the combined epic tree and allow Oompah's exact combined-tree gate at integration. Acceptance criteria: the expected epic task branch is pushed and submitted; wrong-checkout submission fails before mutation; correct submission still integrates; malformed queue state cannot rewrite a live task worktree; OOMPAH-576's observed main/worktree collision cannot recur.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


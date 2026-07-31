---
id: OOMPAH-654
type: task
status: Backlog
priority: null
title: Keep service lifecycle identity metadata out of git worktree status
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T10:29:49.323393Z'
updated_at: '2026-07-31T10:29:49.323393Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Regression found immediately after deploying OOMPAH-652 on merged main ec0ec7d89: normal make restart safely creates .oompah.pid.meta beside the ignored .oompah.pid, but .gitignore ignores only *.pid. Canonical main becomes dirty solely because the service is running. Implementation scope: add the exact lifecycle metadata and any atomic temporary variants created by Makefile identity capture to the appropriate gitignore rules without broadly ignoring unrelated metadata; audit Makefile cleanup/start/restart paths and documentation if necessary. Add a regression test that creates the configured PID_FILE/PID_META_FILE artifacts in a representative checkout and proves git status remains clean while unrelated *.meta files remain visible, and verify make restart/status lifecycle tests. Acceptance: a normal running service with .oompah.pid and .oompah.pid.meta (including transient .tmp.* files if observable) does not dirty a clean checkout; unrelated metadata is not hidden; focused tests and git diff --check pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


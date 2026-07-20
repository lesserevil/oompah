---
id: OOMPAH-283
type: task
status: Backlog
priority: null
title: Expose active state-branch identity and checkpoint health in project APIs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T22:54:50.695408Z'
updated_at: '2026-07-20T22:54:50.695408Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: after a successful Stage B migration, GET /api/v1/projects reports state_branch: null and state_branch_shadow_write: null, while the state-branch status command correctly finds oompah/state/<project-id>. The status command also reports Last push: never immediately after bootstrap despite the branch being pushed.\n\nImplement the OOMPAH-253 API/health contract completely. For state-branch-enabled projects, return the computed branch name, a boolean shadow-write value, migration stage, and accurate last successful push/checkpoint information in project and state endpoints.\n\nTests: add API tests for a Stage B project asserting a non-null branch name and false shadow-write value; add health/status test asserting a pushed bootstrap commit is reflected as the last state commit/push.\n\nAcceptance criteria: dashboard and API consumers can identify the active state branch and its latest checkpoint without deriving branch names themselves; existing legacy projects retain null/disabled behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


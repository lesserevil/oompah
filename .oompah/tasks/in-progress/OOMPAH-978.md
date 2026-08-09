---
id: OOMPAH-978
type: bug
status: In Progress
priority: 1
title: Stop project config updates from dirtying managed checkouts
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- reliability
assignee: null
created_at: '2026-08-09T23:14:00.520291Z'
updated_at: '2026-08-09T23:18:22.412432Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-940

Bug: project create/update paths call tracker AGENTS.md installation directly against Project.repo_path. When the generated integration block changes, routine project configuration updates rewrite tracked AGENTS.md in the canonical managed clone. Later startup sync uses git pull --autostash, reapplies that implicit edit, leaves the checkout dirty, and blocks webhook fast-forward synchronization. Implementation scope: remove implicit AGENTS.md writes from project registration/configuration paths in oompah/server.py; keep bootstrap status/preview/apply as the explicit mutation workflow and preserve tracker configuration cache/lifecycle behavior. Update affected project CRUD tests and add regressions proving project create and project PATCH/config reload leave AGENTS.md byte-for-byte unchanged even when its managed block is stale, while POST /api/v1/projects/{id}/bootstrap/apply remains the only path that can apply and commit bootstrap changes. Required focused tests: project CRUD, agent instructions, and project bootstrap suites. Acceptance criteria: routine service/project configuration operations never dirty a clean managed checkout; explicit bootstrap apply behavior remains covered; all focused checks pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


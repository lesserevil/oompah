---
id: OOMPAH-892
type: task
status: Backlog
priority: null
title: Publish rebased epic branch through server-owned CAS capability
parent: OOMPAH-879
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-891
labels: []
assignee: null
created_at: '2026-08-07T13:30:27.249055Z'
updated_at: '2026-08-07T13:32:25.412210Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Add a server-owned epic-rebase publish capability. Accept only task/project/candidate commit identity from the worker; under authority then project locks resolve remote ref strings, verify current exact authority, candidate equals locked shared-worktree HEAD, target ancestry, and remote lease SHA; execute exact argv force-with-lease push and verify remote outcome with idempotent lost-response handling. Add tamper, restart, CAS-race, and authority-revocation tests. Acceptance: no worker shell command can publish a remote ref; only the server capability can publish the exact authorized candidate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


---
id: OOMPAH-892
type: task
status: In Progress
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
updated_at: '2026-08-07T15:07:36.570127Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 15:07
---
Direct owner implementation started atop validated safety commit 28c0729e in the OOMPAH-879 worktree. Project remains paused. This final child will move all epic-rebase publication into a server-owned exact-CAS capability and leave workers with task/project/candidate identity only. No remote push is authorized from the worker path.
---
<!-- COMMENTS:END -->

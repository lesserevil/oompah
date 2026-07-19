---
id: OOMPAH-249
type: task
status: In Progress
priority: null
title: Wire Release Delivery PR fallback into server backlog service
parent: null
children: []
blocked_by:
- OOMPAH-248
labels: []
assignee: null
created_at: '2026-07-19T19:14:04.819745Z'
updated_at: '2026-07-19T19:14:43.649430Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 0591c4c3-5581-4865-9466-20ae87fa608e
---
## Summary

Problem

OOMPAH-248 added SCM-backed PR commit discovery for deleted task branches, but the live Trickle release delivery endpoint still returns items=0 and unassociated=7513 after PR #446 merged and the service restarted. The server factory at oompah/server.py around _get_item_backlog_service constructs ItemBacklogService without its new scm and managed_repo constructor arguments. Therefore the fallback condition cannot run in production.

Required implementation

- Update the server-side ItemBacklogService factory to pass the project SCM provider and the canonical owner/repository slug derived from the managed project configuration.
- Ensure cache lifecycle/refresh behavior does not retain an old service instance missing these dependencies after configuration changes or restart.
- Do not change candidate eligibility: tracker Merged evidence remains required and returned PR commits must still be reachable from the default branch.
- Add route-level tests that exercise the real server factory, not only a directly constructed ItemBacklogService.

Tests

- API regression with a Merged native task whose work branch is absent and whose review_number resolves through the mocked SCM provider: GET Release Delivery backlog returns a Not selected primary item.
- Assert the SCM provider receives the project owner/repo slug and review number.
- Negative API case: PR commits not reachable from default branch remain absent.
- Cache/initialization test proves the configured SCM and managed repo reach the service used by the route.

Acceptance criteria

- With the actual server route and a deleted task branch, the PR fallback added in OOMPAH-248 is invoked and produces a queueable Release Delivery item.
- The live Trickle release/0.11 backlog no longer reports zero primary items solely because original task branches were deleted.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 19:14
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->

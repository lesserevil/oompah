---
id: OOMPAH-872
type: bug
status: Backlog
priority: 1
title: Resolve the service checkout to a safe management project for operational error
  filing
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:27:00.661610Z'
updated_at: '2026-08-07T05:27:00.661610Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

At service startup from /home/shedwards/src/oompah, the global backend/frontend ErrorWatcher cannot select a safe management tracker because the configured managed project repo_path is /home/shedwards/.oompah/repos/oompah. It therefore disables operational error-task creation even though the Oompah project is registered and project log watchers remain active. Implement identity-safe checkout-to-project resolution for service/runtime clones without weakening OOMPAH-511/OOMPAH-512/OOMPAH-514 fail-closed protections. Prefer durable canonical repository identity and explicit configured management-project authority over path coincidence; reject ambiguous or foreign matches. Relevant code: service startup ErrorWatcher wiring, project repository identity/path resolution, management tracker selection, startup health/alerts. Required tests: canonical service clone maps to the one configured Oompah project; cached mirror and agent worktree aliases resolve only with matching repository identity; ambiguous matches disable filing with an actionable diagnostic; foreign/unmanaged clones remain rejected; restart retains the mapping. Acceptance: the normal production checkout enables backend/frontend operational task filing to the intended project, while unsafe or ambiguous topologies still fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


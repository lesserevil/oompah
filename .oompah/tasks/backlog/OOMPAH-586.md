---
id: OOMPAH-586
type: epic
status: Backlog
priority: 1
title: Restore least-privilege task and lifecycle access
parent: OOMPAH-584
children:
- OOMPAH-593
- OOMPAH-594
- OOMPAH-595
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:13:33.901470Z'
updated_at: '2026-07-30T14:14:57.121585Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Restore reliable operator and service-launched worker access to the oompah task API without distributing server-wide credentials to agents. Integrate the existing OOMPAH-575 scoped-auth work, cover credential reload/drift, and make lifecycle health failures actionable.

Relevant context

Plain task CLI calls from repair workers returned HTTP 401. The running server also retained stale Basic-auth state until recycled even though the current on-disk htpasswd and client password matched. OOMPAH-575 already implements scoped Codex handoff regression coverage and must be reused rather than duplicated.

Acceptance criteria

Assigned workers can view/comment/submit only their task; unrelated or expired capabilities fail closed; operator status/restart/task commands survive supported credential rotation or report a precise actionable fault; secrets are never exposed to workers/logs; focused and complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


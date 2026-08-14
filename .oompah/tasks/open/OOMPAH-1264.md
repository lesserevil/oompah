---
id: OOMPAH-1264
type: feature
status: Open
priority: 1
title: Resolve external prerequisites with exact CAS and one fresh generation
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-1262
labels: []
assignee: null
created_at: '2026-08-14T02:39:54.222347Z'
updated_at: '2026-08-14T04:09:20.196937Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: oompah-1231-resolution-cas-v1
  request_fingerprint: 1f4866dfd9890e09cbc705a0030d9bf030cc49ba6b22639e33bb93bbf52f65e5
oompah.start_blocked_by: *id001
oompah.lifecycle_revision: 1
---
## Summary

Add a project-owner authenticated prerequisite-resolution API and task CLI operation using exact blocker ID plus task authority revision/generation compare-and-swap. Resolution must be idempotent, reject stale blocker/run identities, preserve structured continuation evidence (work branch, exact head, review and pipeline identity), and create exactly one fresh workflow generation instead of rearming old exhausted rows. Support task-qualified cross-project triggers, profile-capability triggers, and named operator actions without allowing status toggles merely to wake work. Reuse existing owner-resolution authentication and transition journal patterns. Required tests: authorization, malformed/cross-scope input, exact CAS, concurrent replacement, idempotent replay, atomic owner/job/status publication, dependency/profile resolution, and TRICKLE-143-shaped continuation resuming review/CI instead of generic implementation. Acceptance: resolving the named prerequisite naturally resumes the correct phase once, while stale or duplicate resolution cannot mutate current work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 03:55
---
Claimed for direct implementation in /home/shedwards/src/oompah-1264 on branch OOMPAH-1264, based on integrated prerequisite bf53cfb7a35c8c9773557712b55cbe09d5de6ef6 from epic-OOMPAH-1231. Oompah remains paused.
---
author: oompah
created: 2026-08-14 04:09
---
Implementation checkpoint: immutable project-owner resolution receipt and exact blocker/run/task-authority CAS are committed locally at 587aab590a7d352c988f35c7cbdf3a80c40c37e2. Lost-response idempotency, conflicting/stale/malformed authority, exact continuation evidence, and native/GitHub/GitLab projections pass 64 focused tests. Distinct resolution-lane workflow and authenticated API/CLI slices are in progress.
---
<!-- COMMENTS:END -->

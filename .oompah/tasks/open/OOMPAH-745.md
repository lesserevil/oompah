---
id: OOMPAH-745
type: task
status: Open
priority: 1
title: Add browser-level alert density and recovery regression coverage
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-742
- OOMPAH-743
- OOMPAH-744
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:27.836890Z'
updated_at: '2026-08-03T23:07:32.228623Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-745
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ea5e0154cb84e897e182323a5c5ecb62c34b8624fe7e160c8ad4160013fc8d1
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: cc0e5462-cd0d-40a6-b1e1-69b5cdfb4ad1
  claim_owner: a032ecbf-d61c-48ca-9cba-cbf452c15431
  claimed_at: '2026-08-03T23:07:04.459822+00:00'
  claim_expires_at: '2026-08-03T23:37:04.459822+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f42d7fad-ba2d-459b-a868-3ec71279540f
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-745
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-745
  base_branch: epic-OOMPAH-740
  base_sha: 583fb236963493a820f36eabdd29789fa5497e6b
  updated_at: '2026-08-03T23:07:28.423316+00:00'
---
## Summary

Add deterministic integration coverage proving that the complete alert experience remains compact, truthful, accessible, and convergent under production-like combinations of facts.

Scope:
- Extend the existing dashboard and WebSocket browser harnesses with representative alert payloads for integration rebase conflict, stale audit backlog, recovered auditor transport failure, running and failed quality gates, healthy repository hygiene, authentication policy denial, and genuine operator-actionable failures.
- Exercise a common desktop viewport matching the production screenshot and smaller responsive sizes.
- Verify initial load, incremental update, sequence-gap full resync, expand and collapse, many-alert overflow, task navigation, and recovery clearing.
- Assert semantic outcomes rather than fragile pixel snapshots where possible, while adding bounded layout measurements for alert-center height and board visibility.
- Include accessibility checks for disclosure state, focus order, alert announcements, and details access.
- Document any intentional presentation contract in existing user-facing dashboard documentation if operator behavior changes.

Relevant files: dashboard UI tests, WebSocket lifecycle and convergence tests, Granian end-to-end fixtures where applicable, and existing dashboard documentation.

Required tests and acceptance criteria:
- With the production-like mixed payload, the collapsed alert center remains bounded and the Kanban board is visible at initial render.
- Each underlying actionable fact appears once.
- Normal and healthy facts stay out of the actionable list.
- Expanding exposes sanitized details within an internally scrollable region.
- Recovery and full resync remove stale warnings without reload.
- No raw transcript appears in always-visible text.
- The full make test gate passes on the exact review-ready head.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:07
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-03 23:07
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

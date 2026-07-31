---
id: OOMPAH-669
type: bug
status: Open
priority: 1
title: Same-head task resubmission must restore Ready to Integrate lifecycle
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-31T21:52:16.588312Z'
updated_at: '2026-07-31T22:59:16.970056Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2fdeca993d4c091dd5af6a63ea4ddf674c7e65b46f17ae5430e199130f7db418
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 99ffddbe-5bff-4298-855a-4047cfcfa436
  claim_owner: 83d630e6-ba64-48af-a521-3ffb6e2a4e3f
  claimed_at: '2026-07-31T22:59:09.564544+00:00'
  claim_expires_at: '2026-07-31T23:29:09.564544+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: ccc4ab87-4d9a-4c27-a4c8-b4e5cc51b684
---
## Summary

Triggered by: OOMPAH-668

Live production reproduction on OOMPAH-668 on 2026-07-31: after an exact-head delivery error, the task was moved through Needs Human/In Progress and resubmitted from its clean registered worktree at the same pushed branch/head. POST /api/v1/issues/{id}/submit returned 201 and the task CLI printed Submitted for integration, but the canonical lifecycle remained In Progress and no new submission comment was written. Root cause is _persist_worker_submission in oompah/server.py: when the existing oompah.integration object has the same task_branch/head_sha, it returns early before tracker.update_issue(... Ready to Integrate) and before recording the new summary. This strands an explicitly resubmitted task despite a success response and forces a content-identical empty commit to change the head. Implement explicit-submit idempotency so every accepted submit request atomically reconciles lifecycle to Ready to Integrate and records/rearms delivery as appropriate, while duplicate requests already in Ready/queued/integrating stay idempotent and background synchronization cannot create loops. Coordinate with the existing queue rearm behavior from OOMPAH-570 and OOMPAH-628 rather than duplicating it. Relevant files: oompah/server.py submission persistence/API, integration queue wiring, task CLI/API response contract, and focused submission/reflow tests. Required deterministic tests: same branch/head resubmitted from In Progress, Needs Human, and Needs CI Fix becomes Ready and runs exactly one fresh delivery; duplicate same-head submission already Ready does not duplicate comments/gates/leases; concurrent status-change-versus-submit has one atomic authority winner; restart preserves the rearmed state; unrelated tasks/projects stay isolated. Acceptance: a 201 submit response always corresponds to durable Ready-to-Integrate lifecycle for that accepted generation, same-head recovery never needs an empty commit, no duplicate integration loop is introduced, focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:59
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-07-31 22:59
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

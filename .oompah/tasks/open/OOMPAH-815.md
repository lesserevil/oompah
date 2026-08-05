---
id: OOMPAH-815
type: task
status: Open
priority: null
title: Preserve accepted child branch identity across repair dispatch
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T00:29:12.870188Z'
updated_at: '2026-08-05T00:32:13.057144Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 16b4288530f95cbebd4c56f62ef0f26f61fc0cd1f8b5725bd524b9cadcbce151
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9543d01b-9442-4f12-8d21-d73fefbd3183
  claim_owner: 209db773-bcba-4efb-b625-7acd11d20c5f
  claimed_at: '2026-08-05T00:32:10.607861+00:00'
  claim_expires_at: '2026-08-05T01:02:10.607861+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Live reproduction on OOMPAH-814 at 2026-08-05 00:26 UTC: a direct-owner implementation was validly submitted and recorded in oompah.integration with task_branch=OOMPAH-814 and exact head cb1446d4, while the issue work_branch remained null. After the exact full gate failed and the server dispatched a CI repair, workspace setup recomputed epic-OOMPAH-763--task-OOMPAH-814, found the registered OOMPAH-814 worktree on the accepted branch, refused to reset it, and failed before the worker started. The same split identity can affect any manually/directly submitted epic child and repeats on every repair. Implementation scope: define one canonical immutable accepted branch identity across owner claim, task submit validation, integration record, issue work_branch metadata, workspace registry, retry/recovery dispatch, and terminal audit. Either reject a noncanonical child branch before mutating tracker/queue, or safely persist and reuse a valid accepted branch; never recompute a different branch after acceptance. Preserve exact remote-head verification, parent-base containment, worktree no-reset safety, concurrent submission fencing, and existing hierarchical child branches. Required tests: exact OOMPAH-814 plain-branch submit then Needs CI Fix repair; restart before repair; null/stale work_branch; canonical hierarchical control; remote branch/head mismatch rejection; dirty/divergent registered worktree preservation; concurrent resubmit; OOMPAH-813-style branch; and no retry loop or duplicate worker. Acceptance: an accepted submission can always be repaired/audited on the same proven branch, invalid branches fail before queue/tracker mutation, and workspace setup never disagrees with persisted integration authority.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


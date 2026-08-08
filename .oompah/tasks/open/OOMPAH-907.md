---
id: OOMPAH-907
type: bug
status: Open
priority: 1
title: Serialize orphan recovery with epic rollup authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T06:36:33.809062Z'
updated_at: '2026-08-08T06:38:31.273015Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cef7ecf12f50cd49b37e5292bdee1f79f0d9fc05bba449714f9ce4834bbdafeb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a0296069-1d33-4d7e-b5c8-3cd1ba3ea577
  claim_owner: 647a02bf-c5a0-4b20-a0a7-177c46bca082
  claimed_at: '2026-08-08T06:38:29.758018+00:00'
  claim_expires_at: '2026-08-08T07:08:29.758018+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Triggered by: OOMPAH-795

Live OOMPAH-795 repeatedly oscillates In Progress -> Open -> In Progress with no running agent and no owner claim: orphan recovery resets the accepted-code parent because it sees no worker, then epic rollup immediately restores In Progress because child OOMPAH-859 is non-terminal. The loop emits possible-state-loop warnings and at least 50 consecutive epic_rollup_parent rejections while doing no work. Implement one authoritative reconciliation rule/transaction so orphan recovery cannot reset a rollup parent whose child lineage or accepted integration evidence legitimately owns its non-terminal status, and so parent rollup cannot race a newer direct-owner/recovery decision. Relevant areas: stalled-task watchdog/orphan recovery, epic/native parent rollup, WorkDecision generation and task-transition serialization. Add a production-shaped OOMPAH-795 regression with an accepted parent head, no live agent, and one active child; prove repeated concurrent ticks converge to one truthful stable status, produce no loop warning, preserve dispatch for a genuinely orphaned leaf, and recover normally once the child terminalizes. Acceptance: no Open/In Progress oscillation, no false agent activity, exact owner/generation fencing remains fail-closed, and focused watchdog/epic-rollup/workflow plus full make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


---
id: OOMPAH-479
type: feature
status: Open
priority: 1
title: Route webhook, YOLO, and merged-branch reconciliation through Merged audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-477
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:27.240594Z'
updated_at: '2026-07-29T01:33:53.263624Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e2aaf43115f65ce1c0ec00b596ffebbaaccb8cad3c31286f5487466d56a644d3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: c7a2b234-73da-4091-9217-22250fd5f83f
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:33:47.227558+00:00'
  claim_expires_at: '2026-07-29T02:03:47.227558+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4883e3c5-e408-42ae-b116-94c9484f55a4
oompah.work_branch: epic-OOMPAH-459
---
## Summary

Implementation scope

Inventory and replace Merged writes driven by GitHub/GitLab merge webhooks, YOLO direct/queued merge outcomes, merged-label maintenance, deferred Done review reconciliation, stale In Review reconciliation, and branch-containment sweeps. Each authoritative merge signal requests Merged with review/source/target evidence. If no current Done audit exists, the coordinator chains Done then Merged. Physical merges may already have occurred, but tracker state remains In Validation until both contracts pass. Preserve CI/rebase recovery and wrong-target checks.

Tests

Add provider-neutral webhook/YOLO/reconciliation cases for correct merge, direct Merged without Done, duplicate webhook/poll events, wrong target, failed/pending CI, deleted source branch, source advanced after merge, shared epic branch, and no matching task. Assert no direct terminal tracker call. Run focused tests and make test.

Acceptance criteria

Every forge- or Git-observed landing is independently validated before the task/epic says Merged, while duplicate observations remain idempotent.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:33
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:33
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

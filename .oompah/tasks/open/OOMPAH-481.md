---
id: OOMPAH-481
type: feature
status: Open
priority: 1
title: Route automatic archive and intake retirement through Archived audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:29.211296Z'
updated_at: '2026-07-29T01:57:49.021504Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 37e03dedf4b09d9f40dde2f20036507fba50ed3ba0fb78907074894f9e017853
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d76b441a-fcb3-4b5b-945e-5cb9df6a08e7
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T01:57:42.133536+00:00'
  claim_expires_at: '2026-07-29T02:27:42.133536+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 50a525d2-144e-43a9-898a-64e107cb2239
oompah.work_branch: epic-OOMPAH-459
---
## Summary

Implementation scope

Update auto-archive maintenance, external issue close/archive reconciliation, duplicate retirement, error-task cleanup, and other automatic archive_issue/status=Archived calls to request an Archived audit. Supply retention or structured disposition reason and pre-archive state. Do not repeatedly request archive while an audit is pending. On unsafe retirement, restore the recorded prior state or use the coordinator failure classification. Existing archived upgrade records stay grandfathered.

Tests

Cover aged Done/Merged auto-archive, recent item, active review/agent/retry, external issue close, duplicate with source reference, missing disposition evidence, repeated maintenance ticks, failed tracker writes, unsafe restoration, and grandfathered Archived records. Run archive/intake/error-watcher tests and make test.

Acceptance criteria

No automatic path hides unresolved work in Archived; valid retirement remains bounded/idempotent and produces a concise durable audit comment.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:57
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

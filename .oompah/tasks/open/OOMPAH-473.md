---
id: OOMPAH-473
type: feature
status: Open
priority: 1
title: Collect safe-retirement evidence for Archived audits
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-471
- OOMPAH-472
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:13.914904Z'
updated_at: '2026-07-29T01:21:14.144221Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 93f7062d478aebea3d6ead2993ecfb71bce8583d8d9e75ff7663c7820ddec830
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 27c3774d-b087-400a-b37f-231194756345
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:21:07.064360+00:00'
  claim_expires_at: '2026-07-29T01:51:07.064360+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 1d4a65c3-90be-473a-8cb9-7b1f2ed9d226
oompah.work_branch: epic-OOMPAH-458
---
## Summary

Implementation scope

Build a read-only ArchivedEvidenceCollector. Record the pre-archive status and verify its current Done/Merged audit when applicable, configured retention/disposition reason, no active worker/claim/retry, no open review, no active child or unresolved dependency, and no requirements/evidence-changing activity after the prior audit. For direct archive dispositions such as duplicate or obsolete work, require a structured reason and referenced replacement/source evidence rather than inventing a completion audit. Return the exact unsafe condition and recommended restoration state.

Tests

Cover retention-qualified Done/Merged items, recent items, active worker/retry/review, active child, unresolved dependency, changed requirements, changed branch SHA, duplicate with/without source link, obsolete reason, and safe restoration state. Run focused tests and make test.

Acceptance criteria

Automatic archive passes only when retirement is safe and justified; archival never hides active, changed, or unresolved work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:21
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

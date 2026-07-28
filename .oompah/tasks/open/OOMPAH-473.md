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
updated_at: '2026-07-28T18:09:21.610701Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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


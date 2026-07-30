---
id: OOMPAH-589
type: bug
status: Open
priority: 1
title: Validate auditor provider endpoints before candidate dispatch
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:20.256845Z'
updated_at: '2026-07-30T14:18:39.159218Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5959c896665e6c4f26f1aecbff8cf62fb2974c3e9536790adddc03a5eb144815
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 6444f301-e3d2-404e-9821-322f9b175ef5
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T14:18:37.219393+00:00'
  claim_expires_at: '2026-07-30T14:48:37.219393+00:00'
  retry_count: 0
  retry_after: null
---
## Summary

Implementation scope

Validate every completion-auditor candidate transport configuration before launch. OpenAI-compatible endpoints must resolve to an absolute HTTP(S) base URL; a missing base must never become the relative URL /chat/completions. Exclude invalid candidates from dispatch, retain independence/provider filtering, and emit a redacted actionable reason without secrets. Relevant areas include provider configuration/loading, oompah/auditor_dispatch.py, the completion-auditor session factory, and health state serialization.

Tests

Add unit/integration regressions for absent, relative, malformed, and valid base URLs; mixed candidate pools; provider fallback; credential redaction; and startup/runtime configuration changes. Run focused provider/auditor tests and make test.

Acceptance criteria

No auditor launch can reach unknown URL type /chat/completions; valid independent candidates still dispatch; invalid candidates are safely skipped and visible through structured health evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
<!-- COMMENTS:END -->

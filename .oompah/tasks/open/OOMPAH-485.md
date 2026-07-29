---
id: OOMPAH-485
type: feature
status: Open
priority: 1
title: Add In Validation and terminal-audit details to the dashboard
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-484
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:24.220262Z'
updated_at: '2026-07-29T02:02:48.068209Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f9d89ebd05e20449a1d7e84fd785a177730fdaa2fa8b119f3e7ce82caf5e0adc
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 6661c08c-ffa9-4602-9921-d170e4338a60
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T02:02:43.804832+00:00'
  claim_expires_at: '2026-07-29T02:32:43.804832+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 1a92387f-66be-4904-bf9f-d8eaf75859c5
oompah.work_branch: epic-OOMPAH-460
---
## Summary

Implementation scope

Add an In Validation board column/count using existing responsive board patterns. In task detail, show requested target, queued/running phase, attempt, evidence revision, contributor models, auditor provider/model, latest result, and actionable failure instructions. Add an explicit owner override control only for authorized users; require target, confirmation, and reason, and call the existing terminal status API with audit_override. Show normal pending audits as status, not alerts. Handle long model names and missing/unknown values accessibly.

Tests

Add template/JavaScript tests for column rendering, task placement, every audit phase, safe escaping, authorized/unauthorized override visibility, required reason validation, API request shape, loading/error behavior, responsive layout hooks, and no duplicate terminal columns. Run focused UI tests and make test.

Acceptance criteria

A user can see why work is validating, which independent model is checking it, what failed, and deliberately perform an authorized documented override without editing tracker labels.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:02
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

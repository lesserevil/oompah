---
id: OOMPAH-483
type: feature
status: Open
priority: 1
title: Detect and block terminal-state writes that bypass the coordinator
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-476
- OOMPAH-477
- OOMPAH-478
- OOMPAH-479
- OOMPAH-480
- OOMPAH-481
- OOMPAH-482
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:31.119782Z'
updated_at: '2026-07-29T02:00:30.624622Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e78ed4a0eb886be67172d00b18afaf76c115d5eb8d03c0af2f5e1c3159d895f7
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 43f0a918-6460-4892-b86e-fb3b91965fe0
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T02:00:23.964023+00:00'
  claim_expires_at: '2026-07-29T02:30:23.964023+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 814b53b9-4eba-491e-bbbf-6c6900a127df
oompah.work_branch: epic-OOMPAH-459
---
## Summary

Implementation scope

Add a periodic reconciliation pass that compares future terminal records with current audit/override metadata and the grandfather baseline. An unaudited new Done/Merged/Archived record is moved to In Validation with the corresponding request chain and an audit comment. Handle direct forge label changes and writes from stale service versions idempotently. Add an AST/source regression test that finds tracker.update_issue terminal constants, close_issue, and archive_issue calls outside a small documented coordinator/persistence allowlist; replace or explicitly justify every current hit. Do not flag terminal-state comparisons or tests as mutations.

Tests

Cover direct tracker write, GitHub/GitLab label event, stale process race, grandfathered record, authorized override, changed fingerprint, repeated sweep, tracker failure, and static scanner positive/negative fixtures. Run focused tests and make test.

Acceptance criteria

A missed integration cannot silently create a trusted terminal state, and future direct terminal mutation code fails CI unless routed through the coordinator.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:00
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

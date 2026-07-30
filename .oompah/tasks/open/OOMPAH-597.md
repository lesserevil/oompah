---
id: OOMPAH-597
type: task
status: Open
priority: 1
title: Recover and drain the OOMPAH-460 ordered integration chain
parent: OOMPAH-587
children: []
blocked_by:
- OOMPAH-596
- OOMPAH-593
start_blocked_by: &id001 []
labels: []
assignee: null
created_at: '2026-07-30T14:15:28.342383Z'
updated_at: '2026-07-30T15:32:35.692629Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ced605c3c18d1e2b0c1aa7a9f3f11c892c63ac4c63ee64582ba26731621a0b47
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 6fda61a9-7109-4ef3-83b7-11b5688a7e74
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T15:32:28.310247+00:00'
  claim_expires_at: '2026-07-30T16:02:28.310247+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: e91a28e1-41c1-4f5b-ab25-19dd441a07ad
---
## Summary

Implementation scope

Using the normal repair and integration mechanisms, resolve the current branch conflicts for OOMPAH-484 and OOMPAH-487 against the latest epic/main base, preserve both tasks intent and tests, and drain OOMPAH-485, OOMPAH-488, and OOMPAH-489 in dependency order. Reconcile the auxiliary OOMPAH-580 task through the terminal-audit path. Do not bypass quality gates, terminal audits, or edit task Markdown directly. File narrowly scoped follow-ups for any newly discovered code defect.

Tests

Run focused tests for each resolved conflict, the complete epic branch gate on the exact review-ready head, and live queue/audit verification.

Acceptance criteria

The five Ready children reach Done with integrated SHAs and passing audits, no queue row remains blocked/ready without progress, and epic OOMPAH-460 can advance through its normal PR/merge lifecycle.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 15:32
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->

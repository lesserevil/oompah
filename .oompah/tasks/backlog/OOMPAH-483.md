---
id: OOMPAH-483
type: feature
status: Backlog
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
labels: []
assignee: null
created_at: '2026-07-28T13:07:31.119782Z'
updated_at: '2026-07-28T13:09:53.444969Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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


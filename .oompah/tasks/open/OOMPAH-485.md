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
labels: []
assignee: null
created_at: '2026-07-28T13:08:24.220262Z'
updated_at: '2026-07-28T18:07:05.362702Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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


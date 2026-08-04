---
id: OOMPAH-791
type: feature
status: Backlog
priority: 1
title: Cut epic and nested-epic rollup over to LandingFact-driven jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:17.853130Z'
updated_at: '2026-08-04T13:59:17.853130Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Migrate epic readiness, child landing verification, rollup review creation, nested target resolution, auto-close, terminal validation, rebase/repair, cleanup, and restart reconciliation to shared facts/decisions/jobs. Enforce acyclic containment; require normal child Done plus landing proof and nested epic landing on immediate parent; never make child eligibility depend on a parent status derived from that child. Preserve patch-equivalence and durable evidence after source pruning. Required real-Git scenarios: multi-level nested epics, parent open to main while child landed to parent, deleted refs, rebase, direct maintenance, new/reopened child during review creation, and OOMPAH-731/739/748. Acceptance: no parent-child proof cycle, all epic consumers share target/landing facts, and rollups converge without manual status overrides.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


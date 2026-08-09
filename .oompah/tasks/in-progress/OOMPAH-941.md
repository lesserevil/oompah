---
id: OOMPAH-941
type: bug
status: In Progress
priority: 1
title: Project authorized owner delivery before requiring landing recovery
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:20.700706Z'
updated_at: '2026-08-09T09:11:32.485405Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Production generation 260 leaves 73 owner-overridden Done tasks in landing_missing/evidence_unknown/retry.exhausted because their accepted project-owner terminal provenance is not represented in canonical delivery facts. Scope: collect only authorized, revision-bound owner terminal provenance that actually proves delivery to the configured target; project it before scheduling integration_landing_refresh; do not treat a generic Done status, comment, or unbound override as merge evidence. Relevant code: terminal transition provenance/audit metadata, workflow fact collection, integration work decisions, restart persistence. Tests: valid owner delivery with exact accepted revision becomes terminal without a landing job; unbound/wrong-target/stale/malformed override remains fail-closed; restart parity and superseded history. Acceptance: qualifying live rows leave current exhaustion naturally, non-qualifying rows remain actionable, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
<!-- COMMENTS:END -->

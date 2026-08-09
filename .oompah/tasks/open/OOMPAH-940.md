---
id: OOMPAH-940
type: epic
status: Open
priority: 1
title: Converge the legacy Done backlog from authoritative delivery evidence
parent: null
children:
- OOMPAH-941
- OOMPAH-942
- OOMPAH-943
- OOMPAH-944
- OOMPAH-945
blocked_by:
- OOMPAH-939
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:16.594615Z'
updated_at: '2026-08-09T09:10:01.037769Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-935 and OOMPAH-937\n\nThe live all-enforce rollout now has zero current liveness divergence, but 185 Oompah tasks remain in Done and generation 260 still reports 97 actionable exhausted jobs. Production evidence divides the residual backlog into independent authority gaps: authorized owner-delivery provenance is ignored, terminal parent branches were pruned without a trusted accepted-head fallback, successful landing refresh effects are not durably fed back, epic cleanup uses a separate child-proof path, and terminal transition guards can contradict an exact-current terminal work decision. Decompose and deliver the child bugs without direct database edits or broad status overrides.\n\nScope: make the workflow fact, action, transition, and cleanup paths share durable exact evidence and one current authority decision; preserve immutable history, bounded scheduling, pause semantics, and fail-closed behavior. Required rollout verification: complete scan, zero current divergence, zero current exhausted jobs or an explicitly non-task system owner, no repeated successful landing refreshes, no contradictory terminal guard decisions, and natural topology-safe movement of the legacy Done backlog. Required tests: focused unit/integration/restart regressions for each child plus complete protected branch gates and a live rollout canary. Acceptance: all children and OOMPAH-939 land; the Oompah project has no erroneously stuck non-terminal task and the workflow rollout check passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


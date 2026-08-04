---
id: OOMPAH-772
type: feature
status: In Progress
priority: 1
title: Encode the canonical task lifecycle and invariants
parent: OOMPAH-764
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:58:41.045890Z'
updated_at: '2026-08-04T14:08:11.054471Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Implement a machine-readable main task lifecycle contract, analogous to release_addendum_schema.VALID_TRANSITIONS but covering all canonical task states. Model business status separately from execution phase and total disposition; define legal transitions, terminal/nonterminal behavior, ownership expectations, retry/reassessment requirements, containment/dependency constraints, and safety/eventual-progress invariants. Relevant files: oompah/statuses.py, new workflow contract module, docs/task-epic-workflow.md, and tests. Required tests: transition table completeness, no illegal/self transitions unless explicitly idempotent, total status mapping, invariant validation, and compatibility aliases. Acceptance: every canonical status maps to one defined disposition and owner/reassessment contract; downstream code imports this contract instead of reconstructing lifecycle categories.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:08
---
Direct-owner implementation started. Scope: encode the canonical task lifecycle, execution phases, total dispositions, transition table, and machine-checkable safety/liveness invariants with focused regression tests and documentation. This is the foundation dependency for the transition service, WorkDecision, durable jobs, verification harness, and all domain cutovers.
---
<!-- COMMENTS:END -->

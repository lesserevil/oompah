---
id: OOMPAH-772
type: feature
status: Ready to Integrate
priority: 1
title: Encode the canonical task lifecycle and invariants
parent: OOMPAH-764
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:58:41.045890Z'
updated_at: '2026-08-04T14:18:50.696019Z'
work_branch: epic-OOMPAH-764--task-OOMPAH-772
target_branch: epic-OOMPAH-764
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.target_branch: epic-OOMPAH-764
oompah.work_branch: epic-OOMPAH-764--task-OOMPAH-772
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-764--task-OOMPAH-772
  base_branch: epic-OOMPAH-764
  head_sha: cc490d183dfbb610acfe6541c1a86dfc66a2e2d2
  submitted_at: '2026-08-04T14:18:44.593231+00:00'
  updated_at: '2026-08-04T14:18:44.593231+00:00'
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
author: oompah
created: 2026-08-04 14:18
---
Implementation complete and focused verification is green: 49 workflow/status contract tests plus 612 tracker/config/dispatch compatibility tests passed; Ruff and the repository secret scan passed. The new authoritative contract defines all canonical statuses, phases, dispositions, owner/reassessment contracts, legal version-fenced edges, evidence requirements, and machine-addressable safety/liveness invariants; statuses.py is now a compatibility facade and the workflow guide documents the separation.
---
author: oompah
created: 2026-08-04 14:18
---
Implemented the authoritative canonical workflow contract with complete status mappings, legal version-fenced transition rules, ownership and reassessment semantics, safety/liveness invariants, a compatibility facade, documentation, and focused regression coverage (661 tests passed).
---
<!-- COMMENTS:END -->

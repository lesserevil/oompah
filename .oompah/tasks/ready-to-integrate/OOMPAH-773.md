---
id: OOMPAH-773
type: task
status: Ready to Integrate
priority: 1
title: Define stable workflow reason codes and liveness SLOs
parent: OOMPAH-764
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-772
labels: []
assignee: null
created_at: '2026-08-04T13:58:42.900744Z'
updated_at: '2026-08-04T14:27:06.907874Z'
work_branch: epic-OOMPAH-764--task-OOMPAH-773
target_branch: epic-OOMPAH-764
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.target_branch: epic-OOMPAH-764
oompah.work_branch: epic-OOMPAH-764--task-OOMPAH-773
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-764--task-OOMPAH-773
  base_branch: epic-OOMPAH-764
  head_sha: e34e3c58b8f99cda238df44d1e59d816303d3112
  submitted_at: '2026-08-04T14:27:00.846137+00:00'
  updated_at: '2026-08-04T14:27:00.846137+00:00'
---
## Summary

Define a versioned reason-code taxonomy and measurable SLO contract for Open, In Progress, Ready to Integrate, In Validation, In Review, recovery, and restart convergence. Specify which conditions are normal/informational versus action_required, the responsible subsystem, evidence fields, reassessment deadline, and operator remedy. Add schema validation and documentation. Required tests: stable serialization, unknown forward-compatible codes, severity mapping, bounded deadline validation, and total coverage of canonical nonterminal statuses. Acceptance: code and UI can communicate why a task is not progressing without message-text parsing; normal recovery never maps to warning; each nonterminal decision has a bounded reassessment policy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:26
---
Implementation complete: added the v1 stable workflow reason taxonomy, presentation classification/severity contract, responsible-subsystem and evidence schema, bounded reassessment SLOs for every non-final status, forward-compatible unknown-code parsing, and documentation. Normal recovery codes are structurally prohibited from warning severity. Focused/compatibility verification passed (673 tests), plus Ruff and secret scanning.
---
author: oompah
created: 2026-08-04 14:27
---
Implemented a versioned workflow reason-code and liveness-SLO schema with total non-final status coverage, stable serialization, forward-compatible unknown codes, evidence/remedy contracts, normal-recovery severity guarantees, docs, and regression tests.
---
<!-- COMMENTS:END -->

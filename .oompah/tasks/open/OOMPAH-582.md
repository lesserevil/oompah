---
id: OOMPAH-582
type: task
status: Open
priority: null
title: Satisfy legacy Done cross-epic dependencies after parent merge
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T04:39:46.196812Z'
updated_at: '2026-07-30T04:39:56.636652Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live reproduction: after OOMPAH-459 merged and epic-OOMPAH-460 was rebased to current main, OOMPAH-484 remains Ready to Integrate because dependency OOMPAH-483 is Done but its legacy integration record has state=working and no integrated_sha. The code is already reachable through OOMPAH-483's Merged parent epic OOMPAH-459 and current default branch, but _integration_satisfied_dependencies only permits the default-branch witness when the dependency itself is Merged/Archived. Implementation scope: in oompah/orchestrator.py, allow a terminal Done cross-epic dependency with missing/unreachable integrated_sha to use the current default-branch reachability witness only when its parent epic resolves from the same issue index and that parent is Merged or Archived. Preserve same-epic behavior and do not satisfy Done children of nonterminal/missing parents. Update the operator-facing integration queue summary in oompah/server.py to use the same rule so it does not keep reporting a false upstream-code blocker after the parent epic lands. Tests: add focused scheduler and API summary cases for Done child + Merged parent + default ref reachable, plus negative cases for parent Done/In Progress/missing and default ref not reachable. Acceptance criteria: OOMPAH-483 is considered satisfied for OOMPAH-484 only after OOMPAH-459 has terminal-landed and main is reachable from epic-OOMPAH-460; OOMPAH-484 becomes claimable; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


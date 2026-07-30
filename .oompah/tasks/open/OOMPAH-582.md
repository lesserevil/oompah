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
updated_at: '2026-07-30T04:40:37.018499Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 25c9271d788a889a3576cb8aba9615a008b7c63f4bc224e416c9f3dd289047de
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 6d1e87e4-3ba5-4563-967a-a462dd99460a
  claim_owner: 4e500792-3d44-4947-bbef-0f678c7beafb
  claimed_at: '2026-07-30T04:40:32.997499+00:00'
  claim_expires_at: '2026-07-30T05:10:32.997499+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 73a55790-95c9-4004-bd80-bee8fb12cc99
---
## Summary

Live reproduction: after OOMPAH-459 merged and epic-OOMPAH-460 was rebased to current main, OOMPAH-484 remains Ready to Integrate because dependency OOMPAH-483 is Done but its legacy integration record has state=working and no integrated_sha. The code is already reachable through OOMPAH-483's Merged parent epic OOMPAH-459 and current default branch, but _integration_satisfied_dependencies only permits the default-branch witness when the dependency itself is Merged/Archived. Implementation scope: in oompah/orchestrator.py, allow a terminal Done cross-epic dependency with missing/unreachable integrated_sha to use the current default-branch reachability witness only when its parent epic resolves from the same issue index and that parent is Merged or Archived. Preserve same-epic behavior and do not satisfy Done children of nonterminal/missing parents. Update the operator-facing integration queue summary in oompah/server.py to use the same rule so it does not keep reporting a false upstream-code blocker after the parent epic lands. Tests: add focused scheduler and API summary cases for Done child + Merged parent + default ref reachable, plus negative cases for parent Done/In Progress/missing and default ref not reachable. Acceptance criteria: OOMPAH-483 is considered satisfied for OOMPAH-484 only after OOMPAH-459 has terminal-landed and main is reachable from epic-OOMPAH-460; OOMPAH-484 becomes claimable; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 04:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 04:40
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

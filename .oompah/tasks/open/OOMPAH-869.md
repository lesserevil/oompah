---
id: OOMPAH-869
type: task
status: Open
priority: null
title: Make inherited validation-fence restart test deterministic under saturated
  gates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T04:34:37.725618Z'
updated_at: '2026-08-07T04:35:34.753216Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 077f3f68e3b381aff73ebec786cc81ad4f29999f676618a095ac0225de6ca31d
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: ba5222cb-ec51-4d96-883d-83e5fbd520d8
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-07T04:35:22.969033+00:00'
  claim_expires_at: '2026-08-07T05:05:22.969033+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a6a1b6a4-6099-4aff-8385-8f0692731757
---
## Summary

Hosted CI on exact OOMPAH-740 head 231d2b8a7 passed Python 3.11 and 3.13 but Python 3.12 failed tests/test_validation_resource_lease.py::test_restart_observes_child_that_inherited_kernel_fence after 15,779 other tests. The test starts sleep 0.5, then expects a new lease acquire with a 0.05 second wait bound to time out. Under saturated scheduling, the child can finish before the assertion reaches acquire, so the lease correctly succeeds and the timing assertion fails. Implementation scope: replace wall-clock process lifetime assumptions with deterministic child/fence synchronization that proves a surviving inherited file descriptor blocks restart acquisition; retain bounded teardown and verify the lease becomes available only after the exact child releases the kernel fence. Relevant files: tests/test_validation_resource_lease.py and validation-resource helpers only if a production defect is independently reproduced. Required tests: the exact case repeated serially and in parallel, the complete validation-resource lease module serial and parallel, and an exact full gate. Acceptance criteria: no fixed sleep is used as proof that the child remains alive, the test deterministically observes owner_count one before the blocking acquire, the acquire times out while the inherited descriptor is held, succeeds after explicit release, and no child process or lease owner leaks.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 04:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 04:35
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

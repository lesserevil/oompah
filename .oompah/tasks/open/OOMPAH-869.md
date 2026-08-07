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
updated_at: '2026-08-07T04:34:54.862296Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Hosted CI on exact OOMPAH-740 head 231d2b8a7 passed Python 3.11 and 3.13 but Python 3.12 failed tests/test_validation_resource_lease.py::test_restart_observes_child_that_inherited_kernel_fence after 15,779 other tests. The test starts sleep 0.5, then expects a new lease acquire with a 0.05 second wait bound to time out. Under saturated scheduling, the child can finish before the assertion reaches acquire, so the lease correctly succeeds and the timing assertion fails. Implementation scope: replace wall-clock process lifetime assumptions with deterministic child/fence synchronization that proves a surviving inherited file descriptor blocks restart acquisition; retain bounded teardown and verify the lease becomes available only after the exact child releases the kernel fence. Relevant files: tests/test_validation_resource_lease.py and validation-resource helpers only if a production defect is independently reproduced. Required tests: the exact case repeated serially and in parallel, the complete validation-resource lease module serial and parallel, and an exact full gate. Acceptance criteria: no fixed sleep is used as proof that the child remains alive, the test deterministically observes owner_count one before the blocking acquire, the acquire times out while the inherited descriptor is held, succeeds after explicit release, and no child process or lease owner leaks.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


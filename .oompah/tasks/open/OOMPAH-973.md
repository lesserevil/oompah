---
id: OOMPAH-973
type: task
status: Open
priority: null
title: Make deferred gate cleanup proof deterministic under loaded CI
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T20:35:08.355449Z'
updated_at: '2026-08-09T20:35:25.978613Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Protected Python 3.11 CI for OOMPAH-972 exact head 9f5bc28fb failed only tests/test_quality_gate.py::test_gate_cleanup_defers_bounded_work_to_one_convergent_reaper after 19,183 passes: synchronous cleanup took 0.519670069 seconds against a hard assertion of <0.5 seconds. OOMPAH-972 changes only setup/install detection and cannot affect BranchQualityGate cleanup. A wall-clock assertion with 19.7 ms margin is race-dependent under loaded CI and is a bug. Implementation scope: replace elapsed-time hope with deterministic synchronization/instrumentation proving cleanup returns after a bounded synchronous slice, remaining work is owned by exactly one convergent reaper, and container/owner metadata are eventually removed. Do not merely widen the timeout or weaken cleanup bounds. Relevant files: tests/test_quality_gate.py and narrow BranchQualityGate cleanup test seams only if necessary. Required tests: reproduce scheduling/load without a wall-clock pass condition; prove a deliberately blocked deferred slice cannot block the caller; prove one reaper owns pending cleanup, converges exactly once, and removes container/owner evidence; preserve depth/operation/time slice enforcement and cleanup identity safety. Acceptance: repeated focused runs pass deterministically, quality-gate module passes, diff/Ruff checks pass, and protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 20:35
---
Accepted for direct-owner repair from PR #780 Python 3.11 hosted run 31334221635: the sole failure was 0.519670069 seconds versus a 0.5-second wall-clock assertion after 19,183 passing tests; branch changes are unrelated setup logic.
---
<!-- COMMENTS:END -->

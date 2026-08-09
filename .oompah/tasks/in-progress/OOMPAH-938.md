---
id: OOMPAH-938
type: bug
status: In Progress
priority: 1
title: Make validation lease aging regression deterministic under load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T08:25:48.619150Z'
updated_at: '2026-08-09T08:31:25.479848Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-905

The complete OOMPAH-935/936/937 integration gate exposed a reproducible race in tests/test_validation_resource_lease.py::test_aging_survives_manager_restart_and_fresh_exact_retains_urgency. The test configures aging_seconds=0.01, then assumes a newly queued worker remains younger than that threshold while another thread is created and scheduled. Under eight-worker or concurrent stress load, more than 10 ms elapses, the supposedly fresh worker legitimately ages, and the expected exact-before-worker ordering reverses. Production arbitration is behaving according to policy; the test clock/threshold is nondeterministic. Replace the sub-scheduler-tick wall-clock assumption with a threshold comfortably above the test timeout while backdating the explicitly old waiter beyond that threshold, or inject deterministic time if the existing lease API supports it. Preserve coverage that aged worker waiters outrank fresh exact gates across restart and that genuinely fresh exact gates retain priority. Required verification: the focused test passes serially and at least 32 repetitions under eight-way host load; adjacent validation-resource tests pass; complete protected branch CI passes. Acceptance: no ordering assertion depends on completing thread setup within 10 ms and production lease semantics remain unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 08:29
---
Direct-owner fix committed in the combined integration at cafc100c4. The test now uses a 30-second aging band, explicitly backdates the old waiter beyond all 21 priority bands, and keeps fresh waiters unambiguously fresh under scheduler load. Verification: focused test passes; 32 repetitions at eight-way concurrency pass; all 499 validation-resource lease tests pass. Production lease code is unchanged. Awaiting protected-main integration.
---
author: oompah
created: 2026-08-09 08:31
---
Combined delivery is pushed at final head cafc100c4 on PR #750. Protected hosted CI is running the complete gate on Python 3.11, 3.12, and 3.13.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-938
type: bug
status: Merged
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
updated_at: '2026-08-09T08:49:23.330360Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-514e40b4e080
    project_id: proj-14849f1b
    task_id: OOMPAH-938
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 984bf5a4cd7053312e6b0519e2021d85f9992fac1a257b2c49689172cada7789
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner direct delivery is present on protected main at b7e7d950
      after PR #750 and all required hosted/focused validation passed; no separate
      terminal audit is needed for this human-only test correction.'
    created_at: '2026-08-09T08:49:08.094062+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-938
    target_state: Merged
    evidence_fingerprint: 984bf5a4cd7053312e6b0519e2021d85f9992fac1a257b2c49689172cada7789
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T08:49:17.918419+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-09 08:49
---
Delivered to protected main by merged PR #750 at b7e7d9509a4e6025b48c54336098acef2dda4986. Hosted complete gates passed on Python 3.11, 3.12, and 3.13. Focused validation: the regression passed serially, 32 repetitions under eight-way concurrency passed, and all 499 validation-resource tests passed; production code was unchanged.
---
author: oompah
created: 2026-08-09 08:49
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner direct delivery is present on protected main at b7e7d950 after PR #750 and all required hosted/focused validation passed; no separate terminal audit is needed for this human-only test correction.
---
author: oompah
created: 2026-08-09 08:49
---
Merged in PR #750 at b7e7d950; all required validation passed.
---
<!-- COMMENTS:END -->

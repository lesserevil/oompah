---
id: OOMPAH-688
type: task
status: Open
priority: null
title: Make slow-tick telemetry tests deterministic under load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T23:11:33.946132Z'
updated_at: '2026-08-01T23:12:02.868908Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 396bfb10a05238676da45fa675e1c1f4b5aa329c2213456458b15432fcdac00d
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 73c05981-b828-4441-97ea-61ae49176a08
  claim_owner: 9c8dda42-c87b-429a-bdb1-42da8ebebe7e
  claimed_at: '2026-08-01T23:11:57.750115+00:00'
  claim_expires_at: '2026-08-01T23:41:57.750115+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4d058dc8-7292-4424-af84-a9dc30bf0eaf
---
## Summary

Observed twice during operator recovery on 2026-08-01: tests/test_orchestrator_tick_telemetry.py::TestSlowTickSubstepLogging::test_no_slow_tick_warning_for_fast_ticks failed only in the parallel full branch gate, while the exact test and clean full reruns passed. The assertion uses a one-second timing boundary and can classify an otherwise fast synthetic tick as slow when the host is contended, producing false Needs CI Fix transitions for unrelated task heads (most recently OOMPAH-685 at 94d7ce2f7).\n\nImplementation scope:\n- Replace wall-clock/load-sensitive behavior in the slow-tick telemetry test with deterministic clock injection or an equivalent controlled elapsed-time seam.\n- Audit adjacent tick telemetry tests for the same real-time threshold pattern and convert them to deterministic time control without weakening production slow-tick logging.\n- Preserve coverage that genuinely fast ticks do not warn and slow ticks report the expected phase/substep breakdown.\n\nRelevant context: tests/test_orchestrator_tick_telemetry.py and the orchestrator tick timing/logging helpers.\n\nRequired tests:\n- Deterministically exercise elapsed time below, at, and above the configured slow-tick threshold.\n- Demonstrate repeated execution is stable under parallel pytest load.\n- Run the focused telemetry suite and make test.\n\nAcceptance criteria:\n- The test no longer depends on scheduler/host wall-clock timing.\n- Production thresholds and telemetry semantics remain unchanged.\n- Focused tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 23:12
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-01 23:12
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

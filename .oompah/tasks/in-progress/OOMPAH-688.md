---
id: OOMPAH-688
type: task
status: In Progress
priority: null
title: Make slow-tick telemetry tests deterministic under load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T23:11:33.946132Z'
updated_at: '2026-08-01T23:13:18.805452Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 396bfb10a05238676da45fa675e1c1f4b5aa329c2213456458b15432fcdac00d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T23:13:08.993872+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Searched the current state-branch task records for the exact test name,
    slow-tick telemetry, timing thresholds, wall-clock behavior, and CI failures.
    The only active related task, OOMPAH-685, is a distinct integration-credential
    fix; its comments explicitly identify the flaky telemetry test and file OOMPAH-688
    as the follow-up. OOMPAH-666 had a related but terminal slow-tick mock-contract
    repair and is excluded.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4d058dc8-7292-4424-af84-a9dc30bf0eaf
oompah.task_costs:
  total_input_tokens: 471081
  total_output_tokens: 2582
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 471081
      output_tokens: 2582
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 471081
    output_tokens: 2582
    cost_usd: 0.0
    recorded_at: '2026-08-01T23:13:08.992560+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-688__20260801T231203Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: OOMPAH-688
    source_sha: 3d50e86c334e8a6318b767b281bc254fa6d93cc2
    completed_at: '2026-08-01T23:13:09.005446+00:00'
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
author: oompah
created: 2026-08-01 23:13
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 9
- Tokens: 471.1K in / 2.6K out [473.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 8s
- Log: OOMPAH-688__20260801T231203Z.jsonl
---
<!-- COMMENTS:END -->

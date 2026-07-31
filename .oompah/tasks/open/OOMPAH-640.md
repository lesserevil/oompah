---
id: OOMPAH-640
type: task
status: Open
priority: null
title: Complete combined stall-to-dispatch recovery regression coverage
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T05:59:47.260716Z'
updated_at: '2026-07-31T06:06:53.834492Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ac81c38f3684a776100adff1365492d7e4f68e5c3580a6447826a757979893cb
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T06:06:48.878502+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-417 directly covers this regression but is Archived; OOMPAH-414/415/416
    are terminal historical tasks. Active OOMPAH-641 concerns unrelated shared-epic
    hardening.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 2ece76fd-3703-4c4f-8be6-9887ccebb834
oompah.task_costs:
  total_input_tokens: 1230045
  total_output_tokens: 4894
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1230045
      output_tokens: 4894
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1230045
    output_tokens: 4894
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:06:48.875575+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-640__20260731T060457Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-640
    source_sha: bb0fd760c3b2938d15ec2026ef5bfc2fd34b0682
    completed_at: '2026-07-31T06:06:48.905150+00:00'
---
## Summary

Follow-up to OOMPAH-417 after parent epic OOMPAH-414 merged. Implementation scope: add the missing integrated regression that exercises a stale dispatch loop recovery, orphaned In Progress tasks reset to Open, the REFRESH_REQUESTED wake, and dispatch of both recovered tasks on the next event-driven tick. Reuse the shipped OOMPAH-415 threshold behavior and OOMPAH-416 orphan-reset wake; do not rewrite those features. Relevant files: tests/test_dispatch_loop_heartbeat.py, tests/test_orphan_reset_dispatch_wake.py, or a focused new regression module, with only production changes if the combined test exposes a real bug. Required tests: prove recovery occurs before the legacy 15-minute threshold; prove one wake is posted after multiple resets; prove two recovered eligible tasks are dispatched without waiting for full sync; cover duplicate wake/tick idempotency. Acceptance: the combined July 23 failure path is deterministic and green, focused tests pass, terminal mutation scan passes, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 06:06
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 19
- Tokens: 1.2M in / 4.9K out [1.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 59s
- Log: OOMPAH-640__20260731T060457Z.jsonl
---
<!-- COMMENTS:END -->

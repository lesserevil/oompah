---
id: OOMPAH-625
type: bug
status: Ready to Integrate
priority: 1
title: Release terminal-auditor branch claims on forced termination
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:58:34.567478Z'
updated_at: '2026-07-30T22:01:34.823310Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-625
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d0577e40e55bd24cbfb63151e1b9d35254575d0f5079e9b7f9fdf505c2c5b251
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Task state or duplicate-relevant content changed while screening was running.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: '2026-07-30T22:01:28.071817+00:00'
oompah.agent_run_id: f71d790f-a7a4-40ef-be07-6ffa6a636594
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-625
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-625
  head_sha: 078bcd40c159a7906c30444ceae2e563b48e1ca3
  submitted_at: '2026-07-30T22:01:25.519747+00:00'
  updated_at: '2026-07-30T22:01:25.519747+00:00'
oompah.task_costs:
  total_input_tokens: 870000
  total_output_tokens: 4588
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 870000
      output_tokens: 4588
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 870000
    output_tokens: 4588
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:01:28.070502+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-625__20260730T215946Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-625
    source_sha: ebb5b12d9bd9668458750ec38bee7d7216f186d7
    completed_at: '2026-07-30T22:01:28.079969+00:00'
---
## Summary

Implementation scope: update the orchestrator forced/manual worker termination path so terminating an auditor releases its  ownership exactly when that same runtime entry is removed. Preserve replacement-worker fencing and survivor-process safety; ordinary and duplicate-preflight termination semantics must remain unchanged. Add observability for the released claim if useful. Relevant context: OOMPAH-591's Claude auditor was terminated during a UI terminal-status transition at 20:20,  removed the RunningEntry and ordinary claim but retained  in , causing every later audit tick to skip the fresh pending audit forever. Tests: reproduce a forced auditor termination with a populated branch claim, assert running/claimed/claimed_issues/branch ownership are all released, cover a mismatched replacement claim so an older terminating worker cannot release a newer owner's fence, and run focused auditor/termination tests plus the Makefile gate. Acceptance criteria: forced auditor termination cannot deadlock future audit dispatch; a stale worker cannot clear a replacement auditor's branch claim; all focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:58
---
Confirmed reproducer: Orchestrator._terminate_running removes the RunningEntry and ordinary claimed/claimed_issues ownership but does not remove the matching entry.branch_key from Orchestrator._audit_branch_claims. The leaked key epic-OOMPAH-585--task-OOMPAH-591 has blocked its fresh audit since the forced UI-transition termination. Preserve a newer owner by releasing only when the recorded attempt ID matches the terminating entry.
---
author: oompah
created: 2026-07-30 21:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 22:01
---
Implemented matching-owner release for completion-auditor branch fences across forced termination, normal exit, launch failure, paused dispatch, and pre-dispatch state-change cleanup. A terminating stale attempt cannot clear a newer replacement attempt claim. Verification: 58 focused auditor-dispatch/forced-termination/telemetry tests passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 22:01
---
Release only the terminating auditor attempt branch fence and preserve newer owners; add forced-termination race regressions.
---
author: oompah
created: 2026-07-30 22:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 15
- Tokens: 870.0K in / 4.6K out [874.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 49s
- Log: OOMPAH-625__20260730T215946Z.jsonl
---
<!-- COMMENTS:END -->

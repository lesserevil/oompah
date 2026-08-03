---
id: OOMPAH-625
type: bug
status: Done
priority: 1
title: Release terminal-auditor branch claims on forced termination
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:58:34.567478Z'
updated_at: '2026-08-03T20:04:46.086587Z'
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
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-625
  base_branch: epic-OOMPAH-585
  base_sha: 078bcd40c159a7906c30444ceae2e563b48e1ca3
  updated_at: '2026-07-30T22:06:46.829592+00:00'
oompah.task_costs:
  total_input_tokens: 870012
  total_output_tokens: 5493
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 870000
      output_tokens: 4588
      cost_usd: 0.0
    unknown:
      input_tokens: 12
      output_tokens: 905
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 870000
    output_tokens: 4588
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:01:28.070502+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 12
    output_tokens: 905
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:12:34.811125+00:00'
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
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-4ecb52e715e9: '2026-07-30T22:11:49.091543+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f9429e5a1f44
    project_id: proj-14849f1b
    task_id: OOMPAH-625
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fc9071e490560eeba582f9939c39cb972653a862f834afb8de6f7250c22d25de
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:28:26.427714+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-625
    target_state: Merged
    evidence_fingerprint: fc9071e490560eeba582f9939c39cb972653a862f834afb8de6f7250c22d25de
    audit_ids:
    - audit-1bceaba36854
    kind: override
    applied: true
    retired_at: '2026-08-02T18:28:35.750651+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1bceaba36854
    project_id: proj-14849f1b
    task_id: OOMPAH-625
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f11179dfe4c6c18227a18d75264163171378e638fd4f7ad0e9bd32fff809f99e
    attempts:
    - version: 1
      attempt_id: attempt-4ecb52e715e9
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f11179dfe4c6c18227a18d75264163171378e638fd4f7ad0e9bd32fff809f99e
      created_at: '2026-07-30T22:06:42.800313+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T22:06:42.800313+00:00'
      branch_key: epic-OOMPAH-585--task-OOMPAH-625
      verdict: pass
      completed_at: '2026-07-30T22:11:49.091258+00:00'
      ended_at: '2026-07-30T22:11:49.091258+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T22:06:15.939614+00:00'
    updated_at: '2026-07-30T22:11:49.091258+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4ecb52e715e9
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f11179dfe4c6c18227a18d75264163171378e638fd4f7ad0e9bd32fff809f99e
    created_at: '2026-07-30T22:06:42.800313+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T22:06:42.800313+00:00'
    branch_key: epic-OOMPAH-585--task-OOMPAH-625
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
author: oompah
created: 2026-07-30 22:06
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 22:06
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 22:06
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 22:07
---
Auditor handoff: exact submitted head 078bcd40c passed the complete integration Makefile gate before absorption into epic-OOMPAH-585. Focused operator evidence is 58 passing auditor-dispatch/forced-termination/telemetry tests plus a passing terminal mutation scan. The read-only policy is expected to reject pytest/cache-writing shell commands; inspect the committed regression and existing gate evidence, then submit the structured verdict without rerunning the full suite.
---
author: oompah
created: 2026-07-30 22:11
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_commit: 078bcd40c159a7906c30444ceae2e563b48e1ca3
- commit_title: OOMPAH-625: release forced auditor branch claims
- diff_stat: oompah/orchestrator.py +36/-6, tests/test_auditor_termination_cleanup.py +91 new
- release_helper_line: oompah/orchestrator.py:4375 _release_audit_branch_claim(branch_key, attempt_id) — pops fence only when _audit_branch_claims[branch_key] == attempt_id
- callsites_updated: orchestrator.py:4536 (dispatch schedule), 4599 (launch failure), 19727 (paused dispatch abort), 19892 (pre-dispatch state-change), 23344 (normal audit exit), 25341 (forced _terminate_running)
- terminate_running_guard: orchestrator.py:25340 `if entry.is_auditor:` gates release; survivor-process check at 25299 returns False before release path, preserving survivor safety
- regression_tests: tests/test_auditor_termination_cleanup.py: 2 passed
- focused_auditor_terminal_suites: tests/test_auditor_dispatch.py, test_auditor_contract.py, test_terminal_audit.py, test_terminal_audit_enforcement.py, test_terminal_transition_coordinator.py: 175 passed
- handler_race_health_suites: tests/test_orchestrator_handlers.py, test_dispatch_close_race.py, test_terminal_audit_health.py, test_auditor_termination_cleanup.py: 332 passed
- auditor_result_status_suites: tests/test_auditor_focus.py, test_terminal_audit_scanner.py, test_terminal_audit_metadata.py, test_auditor_result_api.py, test_terminal_audit_health_api.py, test_terminal_status_interfaces.py, test_terminal_override.py: 153 passed
- preflight_verifier_selector_suites: tests/test_candidate_preflight.py, test_completion_verifier.py, test_auditor_candidate_selector.py, test_dashboard_terminal_audit_health.py: 180 passed
- git_status: working tree clean; branch up to date with origin/epic-OOMPAH-585--task-OOMPAH-625
- direct_pop_scan: grep -n '_audit_branch_claims\.pop' oompah: only match is inside _release_audit_branch_claim itself (line 4386), no bypassing callsites remain
---
author: oompah
created: 2026-07-30 22:12
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 39
- Tokens: 12 in / 905 out [917 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 51s
- Log: OOMPAH-625__20260730T220650Z.jsonl
---
author: oompah
created: 2026-08-02 18:28
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-851
type: bug
status: Done
priority: 1
title: Make every tick-test dispatch mock honor the timing mapping contract
parent: OOMPAH-763
children: []
blocked_by:
- OOMPAH-863
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:40:40.631980Z'
updated_at: '2026-08-07T19:50:27.938850Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-851
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0f04834629ae82aa106dc9b43017e82efc864fb07257c2fb6ffdf362f3197cda
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: 'Required structural peers could not fit the bounded duplicate corpus.
    Omitted peer identifiers: OOMPAH-848, OOMPAH-849, OOMPAH-850.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 3
  retry_after: '2026-08-06T04:43:24.776678+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-851
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-851
  base_branch: epic-OOMPAH-763
  base_sha: 6df7dcbe10c6bba1e03df940dbe28111875ebccd
  head_sha: 87bfe5f6198a383778eb4e3d39f41fcaa50500d0
  submitted_at: '2026-08-07T19:19:44.675410+00:00'
  updated_at: '2026-08-07T19:19:44.675410+00:00'
oompah.task_costs:
  total_input_tokens: 46123
  total_output_tokens: 368
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 45841
      output_tokens: 297
      cost_usd: 0.0
    unknown:
      input_tokens: 282
      output_tokens: 71
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 45841
    output_tokens: 297
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:43:24.760382+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 282
    output_tokens: 71
    cost_usd: 0.0
    recorded_at: '2026-08-07T19:50:02.603905+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-851__20260806T044259Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-851
    source_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
    completed_at: '2026-08-06T04:43:24.799880+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-5d49b0012912
    project_id: proj-14849f1b
    task_id: OOMPAH-851
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 004695e34c16994dbe93a54d9b082ebed06decf0b6302154f3ce2e7fe22517d1
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct operator review accepted this test-contract-only change after all
      651 affected tests passed both xdist4 and serial, with check-secrets and diff
      checks green, and the exact commits were integrated on shared epic 42f98aaed.
      The terminal auditor's redundant full suite has spent over 16 minutes with all
      four workers blocked in jbd2_log_wait_commit and is starving OOMPAH-859 near
      its lease timeout; the combined systemic epic will receive the required full
      exact gate after composition.
    created_at: '2026-08-07T19:49:30.890575+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-851
    target_state: Done
    evidence_fingerprint: 004695e34c16994dbe93a54d9b082ebed06decf0b6302154f3ce2e7fe22517d1
    audit_ids:
    - audit-3be8cbb0bb70
    kind: override
    applied: true
    retired_at: '2026-08-07T19:49:40.436011+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Retain integrated test-contract commits through shared epic 42f98aaed
      as terminal provenance; no new revision exists and combined epic exact validation
      remains scheduled.
    marked_at: '2026-08-07T19:50:26.471940+00:00'
    updated_at: '2026-08-07T19:50:26.471940+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Retain integrated test-contract commits through shared epic 42f98aaed
        as terminal provenance; no new revision exists and combined epic exact validation
        remains scheduled.
      recorded_at: '2026-08-07T19:50:26.471940+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-3be8cbb0bb70
    project_id: proj-14849f1b
    task_id: OOMPAH-851
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 004695e34c16994dbe93a54d9b082ebed06decf0b6302154f3ce2e7fe22517d1
    attempts:
    - version: 1
      attempt_id: attempt-e3190cd0eca9
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 004695e34c16994dbe93a54d9b082ebed06decf0b6302154f3ce2e7fe22517d1
      created_at: '2026-08-07T19:22:18.262696+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-07T19:22:18.262696+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-851
      selected_ref: 87bfe5f6198a383778eb4e3d39f41fcaa50500d0
      selected_sha: 87bfe5f6198a383778eb4e3d39f41fcaa50500d0
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-07T19:21:14.225137+00:00'
    selected_ref: 87bfe5f6198a383778eb4e3d39f41fcaa50500d0
    selected_sha: 87bfe5f6198a383778eb4e3d39f41fcaa50500d0
    updated_at: '2026-08-07T19:49:40.435979+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e3190cd0eca9
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 004695e34c16994dbe93a54d9b082ebed06decf0b6302154f3ce2e7fe22517d1
    created_at: '2026-08-07T19:22:18.262696+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-07T19:22:18.262696+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-851
    selected_ref: 87bfe5f6198a383778eb4e3d39f41fcaa50500d0
    selected_sha: 87bfe5f6198a383778eb4e3d39f41fcaa50500d0
---
## Summary

Regression evidence: OOMPAH-791 exact-head gate 0b5b039a failed tests/test_orchestrator_handlers.py::TestRunStep5cEpicMaintenance::test_tick_skips_new_epic_maintenance_when_previous_still_running after 16,192 passes. The test uses _handle_dispatch_needed = AsyncMock(), whose awaited value is another AsyncMock; when host load makes _tick exceed the slow-tick threshold, production correctly calls dispatch_timings.items() and the synthetic mock violates the Mapping contract. Static audit found six remaining bare assignments: tests/test_long_tick_regression.py:741, tests/test_dispatch_loop_heartbeat.py:615, and tests/test_orchestrator_handlers.py around 1385, 2612, 3167, and 3457, versus 21 faithful return_value={} mocks. Implementation scope: convert and audit every _tick unit-test mock so _handle_dispatch_needed returns a real timing Mapping; add a deterministic slow-path regression that forces elapsed time past the threshold and proves the target behavior remains valid; do not suppress production diagnostics or raise global timeouts. Relevant files: the three named test modules and shared orchestrator test helpers; production code only if a typed seam is required. Required tests: each converted test in forced fast and slow timing paths, affected modules serial and -n 4, static guard or helper coverage preventing new bare mocks, and make test. Acceptance criteria: no _tick test supplies a non-Mapping dispatch result; the observed maintenance-future test passes even when the slow path is deterministically forced; production timing telemetry remains unchanged; canonical full gate is stable under load.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 04:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 45.8K in / 297 out [46.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 35s
- Log: OOMPAH-851__20260806T044259Z.jsonl
---
author: oompah
created: 2026-08-06 04:43
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-848, OOMPAH-849, OOMPAH-850. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-06 05:42
---
Prepared timing-mock contract repair is independently static-reviewed, clean, and pushed at 288946416. All direct _handle_dispatch_needed AsyncMocks return real mappings, the originally failing maintenance test deterministically forces slow diagnostics, and an AST regression prevents bare mocks. Checkpoint only; focused tests and O763 restack are pending.
---
author: oompah
created: 2026-08-06 17:38
---
Focused validation exposed the new whole-test-corpus AST guard exceeding the global five-second timeout under the live OOMPAH-846 lease-bypass saturation. Added a scoped semantic optimization: source files that cannot spell all three resolvable target components are skipped before AST parsing, reducing parse candidates from 406 modules to 23 while existing split-string/dynamic-target cases remain covered; added an invalid-unrelated-source regression. The first contaminated rerun was operator-aborted at 64 percent only to release the lane to the higher-priority OOMPAH-831 exact gate. No code failure was observed in that aborted run; full serial and xdist rerun remains required after the exact gate.
---
author: oompah
created: 2026-08-06 17:58
---
The broad focused matrix exposed a real concurrent standalone-delivery alert race, not a timing-mock defect: durable capacity admitted one review, but a losing sweep re-armed a capacity-wait alert for that same winning task. Filed OOMPAH-863 with a deterministic barrier regression and made it a finish dependency so OOMPAH-851 cannot enter an exact integration gate that can reproduce the unrelated race. The OOMPAH-851 AST contract optimization remains preserved and its exact failing node will be rerun after OOMPAH-863 lands.
---
author: oompah
created: 2026-08-07 19:20
---
Made every tick-test dispatch double return a faithful timing mapping, added deterministic slow-path/static contract coverage, and optimized the guard without weakening fail-closed detection. Restacked onto shared epic 6df7dcbe1; all 651 affected tests pass both parallel and serial; check-secrets and diff checks pass.
---
author: oompah
created: 2026-08-07 19:21
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-07 19:22
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-07 19:22
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-07 19:49
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct operator review accepted this test-contract-only change after all 651 affected tests passed both xdist4 and serial, with check-secrets and diff checks green, and the exact commits were integrated on shared epic 42f98aaed. The terminal auditor's redundant full suite has spent over 16 minutes with all four workers blocked in jbd2_log_wait_commit and is starving OOMPAH-859 near its lease timeout; the combined systemic epic will receive the required full exact gate after composition.
---
author: oompah
created: 2026-08-07 19:50
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 16
- Tokens: 282 in / 71 out [353 total]
- Cost: $0.0000
- Exit: terminated, Duration: 27m 42s
- Log: OOMPAH-851__20260807T192233Z.jsonl
---
author: oompah
created: 2026-08-07 19:50
---
Tick-test timing contracts integrated; 651 affected tests pass both parallel and serial. Redundant I/O-stalled terminal full suite overridden pending the combined epic full gate.
---
<!-- COMMENTS:END -->

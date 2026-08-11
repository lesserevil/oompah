---
id: OOMPAH-1080
type: task
status: In Validation
priority: null
title: Import trusted protected ordinary-PR exact-head gates before terminal-audit
  dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:00:26.321021Z'
updated_at: '2026-08-11T11:48:54.506732Z'
work_branch: OOMPAH-1080
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/818
review_number: '818'
review_head: eabbcdaceabad696070014a6fa166c8d1334f46a
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: ac7161fc-9c77-4b8e-aa7b-5686df38ab4b
  request_fingerprint: 2bf5c669d1b5f34c19c01be0a65e261135dfea89635e99fb0c368010765c3a6f
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1080
  head_sha: eabbcdaceabad696070014a6fa166c8d1334f46a
  submitted_at: '2026-08-11T11:27:23.712478+00:00'
  updated_at: '2026-08-11T11:27:23.712478+00:00'
oompah.work_branch: OOMPAH-1080
oompah.review_url: https://github.com/lesserevil/oompah/pull/818
oompah.review_number: '818'
oompah.target_branch: main
oompah.review_head: eabbcdaceabad696070014a6fa166c8d1334f46a
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-f40993597ee1
    project_id: proj-14849f1b
    task_id: OOMPAH-1080
    digest: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
  - version: 1
    audit_id: audit-a2ff6b47d77f
    project_id: proj-14849f1b
    task_id: OOMPAH-1080
    digest: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1080","audit-f40993597ee1","attempt-3307ed4270fd"]': '2026-08-11T11:48:30.590727+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1080
    target_state: Done
    evidence_fingerprint: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
    workflow_revision: null
    selected_ref: eabbcdaceabad696070014a6fa166c8d1334f46a
    selected_sha: eabbcdaceabad696070014a6fa166c8d1334f46a
    landing_revision: null
    audit_ids:
    - audit-f40993597ee1
    kind: result
    applied: true
    retired_at: '2026-08-11T11:48:30.590743+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1080
    audit_id: audit-f40993597ee1
    attempt_id: attempt-3307ed4270fd
    target_state: Done
    evidence_fingerprint: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
    status: In Validation
    audit_ids:
    - audit-f40993597ee1
    kind: result
    applied: true
    created_at: '2026-08-11T11:48:30.590753+00:00'
    applied_at: '2026-08-11T11:48:39.001071+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f40993597ee1
    project_id: proj-14849f1b
    task_id: OOMPAH-1080
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
    attempts:
    - version: 1
      attempt_id: attempt-3307ed4270fd
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
      created_at: '2026-08-11T11:44:23.926912+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T11:44:23.926912+00:00'
      branch_key: OOMPAH-1080
      selected_ref: eabbcdaceabad696070014a6fa166c8d1334f46a
      selected_sha: eabbcdaceabad696070014a6fa166c8d1334f46a
      verdict: pass
      completed_at: '2026-08-11T11:48:30.590551+00:00'
      ended_at: '2026-08-11T11:48:30.590551+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T11:40:14.620111+00:00'
    selected_ref: eabbcdaceabad696070014a6fa166c8d1334f46a
    selected_sha: eabbcdaceabad696070014a6fa166c8d1334f46a
    updated_at: '2026-08-11T11:48:30.590551+00:00'
  - version: 1
    audit_id: audit-a2ff6b47d77f
    project_id: proj-14849f1b
    task_id: OOMPAH-1080
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T11:40:14.620111+00:00'
    selected_ref: eabbcdaceabad696070014a6fa166c8d1334f46a
    selected_sha: eabbcdaceabad696070014a6fa166c8d1334f46a
  attempt_history:
  - version: 1
    attempt_id: attempt-3307ed4270fd
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 517b6cec65ddd2782a17fce0fc2e6091100b1c7a149088226f7d0f90cd4fca17
    created_at: '2026-08-11T11:44:23.926912+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T11:44:23.926912+00:00'
    branch_key: OOMPAH-1080
    selected_ref: eabbcdaceabad696070014a6fa166c8d1334f46a
    selected_sha: eabbcdaceabad696070014a6fa166c8d1334f46a
oompah.task_costs:
  total_input_tokens: 266
  total_output_tokens: 11040
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 266
      output_tokens: 11040
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 266
    output_tokens: 11040
    cost_usd: 0.0
    recorded_at: '2026-08-11T11:48:49.168863+00:00'
---
## Summary

Triggered by: OOMPAH-1071. Problem: OOMPAH-1071 final reviewed head 238736... differed from its earlier local gate head baa287..., yet protected PR 810 had passed the pinned Python 3.11/3.12/3.13 matrix and merged exactly. Terminal audit did not import that ordinary PR evidence, reran the full Makefile gate for more than 15 minutes, serialized validation, and delayed graceful deployment. OOMPAH-1001 imports only recovery-PR evidence. Scope: generalize the existing strict protected-evidence importer to ordinary merged PRs before terminal-audit dispatch, retaining exact project/repo/source/head/base/target-containment/configured-command/workflow-blob/job/app/attempt/trust-fingerprint checks and fail-closed behavior. Never consume aggregate CI status, synthetic merge evidence without the existing exact-head/tree attestation, partial/skipped/neutral/cancelled jobs, stale attempts, advanced heads, wrong base/source, degraded API, or changed trust configuration. Relevant code: oompah/scm.py, oompah/quality_gate.py, oompah/orchestrator.py and terminal-audit launch/reconciliation tests. Tests/acceptance: an OOMPAH-1071/PR810-shaped ordinary merged PR imports one durable exact-head PASS and the first audit reuses it without launching make test, including after restart; stale/wrong/replayed/concurrent evidence fails closed or is idempotent; recovery PR behavior remains green; protected CI and focused tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 11:27
---
Generalize strict protected exact-head gate import from recovery PRs to ordinary merged PRs at eabbcdaceabad696070014a6fa166c8d1334f46a; 294 focused quality-gate tests and terminal scan pass.
---
author: oompah
created: 2026-08-11 11:35
---
Independent exact-head review ACCEPT for eabbcdaceabad696070014a6fa166c8d1334f46a. Reviewer verified remote/head identity, ordinary and recovery protected-evidence boundaries, provider/job/attempt/app/workflow/tree trust binding, replay and revocation behavior, and no aggregate-CI fallback. Independent tests: 294 quality-gate tests and 12 strict protected-workflow provider tests passed.
---
author: oompah
created: 2026-08-11 11:38
---
Branch quality gate passed for `eabbcdaceabad696070014a6fa166c8d1334f46a` using `make test` in 196.8s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 11:40
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 11:44
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 11:44
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 11:48
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- implementation_changes.new_method: _terminal_audit_ordinary_review_identity validates exact ordinary merged PR identity with 14 strict checks
- implementation_changes.removed_requirement: staged_attempt_identity=True no longer required for gate import
- implementation_changes.added_validation: Review ID tracking, integration state checking, base commit matching
- implementation_changes.fail_closed_paths: Returns None on any uncertainty or mismatch (14+ validation points)
- test_coverage.main_positive_case: test_terminal_audit_launch_imports_ordinary_merged_pr_exact_head_gate
- test_coverage.forge_mismatch_tests: 2 parametrized test_terminal_audit_launch_rejects_ordinary_review_forge_mismatch
- test_coverage.race_condition_tests: 2 parametrized test_terminal_audit_launch_rejects_ordinary_review_mutated_during_fetch
- test_coverage.durability_test: test_terminal_audit_ordinary_protected_import_survives_restart_and_revocation
- test_coverage.optimization_test: test_terminal_audit_launch_ordinary_pass_never_queries_protected_workflow
- test_coverage.edge_case_test: test_terminal_audit_quality_gate_rejects_conflicting_ordinary_and_bound_heads
- quality_gate_evidence.gate_command: make test
- quality_gate_evidence.result: passed
- quality_gate_evidence.duration_seconds: 196.75
- quality_gate_evidence.authority_current: true
- quality_gate_evidence.test_count: 294 quality-gate tests plus terminal scan
---
author: oompah
created: 2026-08-11 11:48
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 76, Tool calls: 32
- Tokens: 266 in / 11.0K out [11.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 22s
- Log: OOMPAH-1080__20260811T114437Z.jsonl
---
<!-- COMMENTS:END -->

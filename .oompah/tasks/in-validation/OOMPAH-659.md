---
id: OOMPAH-659
type: task
status: In Validation
priority: null
title: Defer standalone full gates until finish dependencies are satisfied
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-657
labels: []
assignee: null
created_at: '2026-07-31T12:15:02.565914Z'
updated_at: '2026-08-07T14:10:45.058399Z'
work_branch: OOMPAH-659
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/620
review_number: '620'
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 903f68bf1e5410244cf5b06395503984aed024890c87202e33be151b4e57ccf2
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T13:03:56.243622+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search, I have enough information to provide\
    \ my verdict.\n\n**Summary of investigation:**\n\n1. **Active tasks searched**:\
    \ Only two non-terminal tasks exist in `.oompah/tasks`:\n   - OOMPAH-281 (Open):\
    \ Containerized GitHub Actions runner \u2014 completely unrelated\n   - OOMPAH-282\
    \ (Backlog): State branch migration UnicodeEncodeError \u2014 completely unrelated\n\
    \n2. **Merged/Archived tasks**: All tasks OOMPAH-1 through OOMPAH-280 are in terminal\
    \ states (Archived or Merged). None can be duplicate targets per the rules.\n\n\
    3. **Keyword searches**: Exhaustive searches for `standalone gate`, `finish dependency`,\
    \ `ready-to-integrate`, `defer gate`, `quality gate`, `effective_depend`, `watchdog\
    \ churn`, `needs CI fix`, `integration queue` \u2014 all returned **zero matches**\
    \ in `.oompah/tasks`.\n\n4. **OOMPAH-657 context**: Tests in `test_delivery_plane_recovery.py`\
    \ and `test_quality_gate.py` reference OOMPAH-657, confirming it was already implemented\
    \ and submitted (per coordination comment: \"OOMPAH-657 submitted 0212dada64768ed8f89e7b27f461f121c4a42299\"\
    ). It is a terminal/submitted task \u2014 not an active duplicate target. OOMPAH-658\
    \ is the triggering task that spawned this investigation.\n\n5. **OOMPAH-659's\
    \ scope** (deferring standalone full gates until finish dependencies are satisfied)\
    \ is a **new, distinct problem** not covered by any active task.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: Searched all active, non-terminal tasks in `.oompah/tasks`\
    \ (OOMPAH-281/Open, OOMPAH-282/Backlog) \u2014 both are unrelated (containerized\
    \ runner and state branch migration error respectively). Exhaustive keyword searches\
    \ for standalone gate deferral, finish-order dependencies, ready-to-integrate\
    \ waiting, quality gate, effective_dependencies, and watchdog churn returned zero\
    \ matches across all task folders (open, backlog, merged, archived). OOMPAH-657,\
    \ the closest related task, is in a submitted/terminal state (confirmed by coor"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c07feddf-478e-4f4c-b40a-33529654f7b1
oompah.task_costs:
  total_input_tokens: 7599257
  total_output_tokens: 51940
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 7599218
      output_tokens: 45356
      cost_usd: 0.0
    unknown:
      input_tokens: 39
      output_tokens: 6584
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 21
    output_tokens: 4865
    cost_usd: 0.0
    recorded_at: '2026-07-31T13:03:56.242390+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 7599197
    output_tokens: 40491
    cost_usd: 0.0
    recorded_at: '2026-07-31T13:19:32.382060+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 22
    output_tokens: 4239
    cost_usd: 0.0
    recorded_at: '2026-07-31T13:43:20.737174+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 17
    output_tokens: 2345
    cost_usd: 0.0
    recorded_at: '2026-07-31T13:45:13.158444+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-659__20260731T130144Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: duplicate_detector
    source_branch: OOMPAH-659
    source_sha: 3316ec40933d1c387619d534e607a3b0100df7dc
    completed_at: '2026-07-31T13:03:56.254699+00:00'
  - run_id: OOMPAH-659__20260731T130424Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: ci_fix
    source_branch: OOMPAH-659
    source_sha: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
    completed_at: '2026-07-31T13:19:32.385404+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-659
  base_branch: main
  base_sha: 3316ec40933d1c387619d534e607a3b0100df7dc
  head_sha: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
  submitted_at: '2026-07-31T13:19:04.263341+00:00'
  updated_at: '2026-07-31T13:19:37.021543+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/620
oompah.review_number: '620'
oompah.work_branch: OOMPAH-659
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-f1bf3af95a07: '2026-07-31T13:43:05.795755+00:00'
    attempt-864c8121bc62: '2026-07-31T13:44:54.451377+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-659
    target_state: Done
    evidence_fingerprint: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    audit_ids:
    - audit-62a88de713f5
    kind: result
    applied: true
    retired_at: '2026-07-31T13:43:05.795769+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-659
    target_state: Merged
    evidence_fingerprint: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    audit_ids:
    - audit-ad8765d07973
    kind: result
    applied: true
    retired_at: '2026-07-31T13:44:54.451398+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-659
    audit_id: audit-62a88de713f5
    attempt_id: attempt-f1bf3af95a07
    target_state: Done
    evidence_fingerprint: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    status: In Validation
    audit_ids:
    - audit-62a88de713f5
    applied: true
    created_at: '2026-07-31T13:43:05.795787+00:00'
    applied_at: '2026-07-31T13:43:09.374692+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-659
    audit_id: audit-ad8765d07973
    attempt_id: attempt-864c8121bc62
    target_state: Merged
    evidence_fingerprint: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    status: Merged
    audit_ids:
    - audit-ad8765d07973
    applied: true
    created_at: '2026-07-31T13:44:54.451420+00:00'
    applied_at: '2026-07-31T13:44:59.524567+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-62a88de713f5
    project_id: proj-14849f1b
    task_id: OOMPAH-659
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    attempts:
    - version: 1
      attempt_id: attempt-f1bf3af95a07
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
      created_at: '2026-07-31T13:40:28.069038+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T13:40:28.069038+00:00'
      branch_key: OOMPAH-659
      verdict: pass
      completed_at: '2026-07-31T13:43:05.795585+00:00'
      ended_at: '2026-07-31T13:43:05.795585+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T13:40:11.909583+00:00'
    updated_at: '2026-07-31T13:43:05.795585+00:00'
  - version: 1
    audit_id: audit-ad8765d07973
    project_id: proj-14849f1b
    task_id: OOMPAH-659
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    attempts:
    - version: 1
      attempt_id: attempt-864c8121bc62
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
      created_at: '2026-07-31T13:43:27.066432+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T13:43:27.066432+00:00'
      branch_key: OOMPAH-659
      verdict: pass
      completed_at: '2026-07-31T13:44:54.451197+00:00'
      ended_at: '2026-07-31T13:44:54.451197+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T13:40:11.909583+00:00'
    updated_at: '2026-07-31T13:44:54.451197+00:00'
  - version: 1
    audit_id: audit-506a7bd5874f
    project_id: proj-14849f1b
    task_id: OOMPAH-659
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae42e3ca1d0805bf39c4394639c2b01a024f43615c74047831fc2a56b4538bc2
    attempts:
    - version: 1
      attempt_id: attempt-55951b17aa0b
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ae42e3ca1d0805bf39c4394639c2b01a024f43615c74047831fc2a56b4538bc2
      created_at: '2026-08-07T14:10:37.000709+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-07T14:10:37.000709+00:00'
      branch_key: OOMPAH-659
      selected_ref: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
      selected_sha: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-07T14:08:18.986638+00:00'
    selected_ref: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
    selected_sha: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
    updated_at: '2026-08-07T14:10:37.000709+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-f1bf3af95a07
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    created_at: '2026-07-31T13:40:28.069038+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T13:40:28.069038+00:00'
    branch_key: OOMPAH-659
  - version: 1
    attempt_id: attempt-864c8121bc62
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 30c09f3dce6d46574763a22aeaeab2353f843d3875c8feaf48628818d2f2c745
    created_at: '2026-07-31T13:43:27.066432+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T13:43:27.066432+00:00'
    branch_key: OOMPAH-659
  - version: 1
    attempt_id: attempt-55951b17aa0b
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae42e3ca1d0805bf39c4394639c2b01a024f43615c74047831fc2a56b4538bc2
    created_at: '2026-08-07T14:10:37.000709+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-07T14:10:37.000709+00:00'
    branch_key: OOMPAH-659
    selected_ref: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
    selected_sha: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
---
## Summary

Triggered by: OOMPAH-658\n\nLive production reproduction on 2026-07-31: standalone task OOMPAH-658 has a normal finish-order dependency on OOMPAH-657, but each worker submission immediately starts the configured repository-wide quality gate. When the premature gate is operator-terminated, the task moves to Needs CI Fix, the stalled-task watchdog reopens it, another worker resubmits the unchanged head, and the loop repeats. Epic integration queues already wait for effective finish dependencies; standalone Ready-to-Integrate delivery does not.\n\nImplementation scope: before any standalone branch quality gate or review creation, compute the task's effective finish-order dependencies (including inherited parent constraints) using the same canonical dependency/status/audit-satisfaction semantics as ordered integration. If any dependency is unfinished, leave the exact submitted task/head durably in Ready to Integrate, do not run the gate, do not create a review, do not route to Needs CI Fix, and expose one idempotent non-actionable waiting reason that clears when dependencies become satisfied or the task/head changes. On dependency completion, restart, or explicit refresh, resume exactly once from the same submitted head through the normal immutable gate/review flow. Hard-start dependencies must continue to govern implementation dispatch separately.\n\nRelevant code: oompah/orchestrator.py standalone Ready-to-Integrate reconciliation and review-quality-gate entry points, dependency indexing/effective_dependencies helpers, delivery alerts/state surfaces, and tests/test_standalone_ready_to_integrate.py. Required deterministic tests: unfinished normal dependency causes zero gate/review calls across repeated ticks and restart; terminal-audit-satisfied dependency releases exactly one gate; inherited dependency behaves identically; dependency regression or head/status change cancels stale authority; project/task isolation; no Needs CI Fix/watchdog churn. Acceptance: standalone work may implement in parallel but can never consume its one full gate or create a review before every finish-order dependency is satisfied, and focused scheduler tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 12:15
---
Hard-start ordered after OOMPAH-657 because both tasks change standalone gate authority/cancellation code; implementation before that integration would create a conflict and test against obsolete lifecycle semantics.
---
author: oompah
created: 2026-07-31 13:01
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 13:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 13:03
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 43, Tool calls: 29
- Tokens: 21 in / 4.9K out [4.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 14s
- Log: OOMPAH-659__20260731T130144Z.jsonl
---
author: oompah
created: 2026-07-31 13:04
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 13:04
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-31 13:19
---
Deferred standalone gates until effective finish dependencies are terminal-audit satisfied.
---
author: oompah
created: 2026-07-31 13:19
---
Agent completed successfully in 914s (7639688 tokens)
---
author: oompah
created: 2026-07-31 13:19
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 61
- Tokens: 7.6M in / 40.5K out [7.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 14s
- Log: OOMPAH-659__20260731T130424Z.jsonl
---
author: oompah
created: 2026-07-31 13:30
---
Branch quality gate passed for `cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50` using `make test` in 375.1s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 13:40
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 13:40
---
YOLO: merged PR #620.
---
author: oompah
created: 2026-07-31 13:40
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 13:40
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 13:43
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merge_commit: 507534cf21032d8bd94ce6e9d5dcd4d1497b3a65
- implementation_commit: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
- pr_number: #620
- focused_test_result: tests/test_standalone_ready_to_integrate.py 27 passed in 10.58s
- full_gate: make test previously passed on cbbc1a5a1 in 375.1s per tracker branch-gate record
- files_changed: oompah/orchestrator.py (+284/-8), tests/test_standalone_ready_to_integrate.py (+244/-0)
---
author: oompah
created: 2026-07-31 13:43
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 23, Tool calls: 16
- Tokens: 22 in / 4.2K out [4.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 51s
- Log: OOMPAH-659__20260731T134034Z.jsonl
---
author: oompah
created: 2026-07-31 13:43
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 13:43
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 13:44
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- merge_commit: 507534cf21032d8bd94ce6e9d5dcd4d1497b3a65
- implementation_commit: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
- pr_number: #620
- focused_test_result: tests/test_standalone_ready_to_integrate.py: 27 passed in 18.18s
- full_gate_prior: make test passed on cbbc1a5a1 in 375.1s (tracker record)
- merge_on_main: yes (origin/main contains 507534cf2)
- files_changed: oompah/orchestrator.py, tests/test_standalone_ready_to_integrate.py
---
author: oompah
created: 2026-07-31 13:45
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 15, Tool calls: 11
- Tokens: 17 in / 2.3K out [2.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 43s
- Log: OOMPAH-659__20260731T134333Z.jsonl
---
author: oompah
created: 2026-08-07 14:10
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-07 14:10
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->

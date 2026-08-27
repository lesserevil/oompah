---
id: OOMPAH-1288
type: bug
status: Ready to Integrate
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1267 identifier=OOMPAH-1267 run_id=671f8f5990b64a229b74342ef73ff72e
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:14:55.303312Z'
updated_at: '2026-08-27T03:47:31.091289Z'
work_branch: OOMPAH-1288
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cecb82342ba47de9bda26885a8473850133d40c432c89a2f3225e197a2b71677
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T11:38:52.094128+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: Reviewed 28 similarity candidates including OOMPAH-1000..1014 (terminal
    audit/workflow/epic issues), OOMPAH-1015..1027 (enforcement errors, all archived),
    and earlier tasks. None describe the "Pre-provider contributor evidence exceeded
    its bounded task-authority deadline" error from `backend:orchestrator` with timeout_seconds=5.0.
    All superficially related tasks are in terminal states (Merged/Done/Archived).
    The error references OOMPAH-1267, which is not in the provided corpus to verify
    as a duplicate source. This appears to be a distinct, unreported error from the
    orchestrator''s task-authority timeout system.

    # Duplicate Investigation: OOMPAH-1288


    I''m investigating whether OOMPAH-1288 ("Pre-provider contributor evidence exceeded
    its bounded task-authority deadline") is a duplicate of an existing task.


    Let me analyze the provided task corpus systematically.


    ## Current Issue Analysis


    **OOMPAH-1288** describes:

    - **Error**: "Pre-provider contributor evidence exceeded its bounded task-authority
    deadline"

    - **Source**: `backend:orchestrator`

    - **Timeout**: 5.0 seconds

    - **Referenced task**: OOMPAH-1267 (mentioned in error message)

    - **Project**: proj-14849f1b

    - **Auto-filed by**: error_watcher


    ## Corpus Review


    The provided corpus includes 28 similarity candidates selected from 728 total
    tasks. All reviewed candidates fall into two categories:


    ### 1. Terminal Audit & Enforcement Issues (OOMPAH-1000..1027)

    These are all in **terminal states** (Merged, Done, or Archived):

    - OOMPAH-1000..1014: Various terminal audit, workflow admission, epic validation
    issues

    - OOMPAH-1015..1027: Backend enforcement errors, mostly marked as duplicate artifacts
    from a startup flood


    **Assessment**: None of these describe the "Pre-provider contributor evidence
    exceeded its bounded task-authority deadline" error. They address different orchestrator
    problems (audit identity, dependency resolution, epic handling, workflow admission).


    ### 2. Earlier Issues (OOMPAH-1, OOMPAH-10, OOMPAH-270)

    These are archived and unrelated to the current error pattern.


    ## Key Findings


    1. **No active task matches**: No Open or In Progress task describes this specific
    "bounded task-authority deadline" timeout

    2. **Terminal state only**: All superficially similar tasks are already merged
    or archived

    3. **Error reference chain broken**: The error message references OOMPAH-1267,
    which is not in the provided corpus (700 candidates omitted)

    4. **Unique error signature**: The fingerprint `772d9a1d1e72c50e` and specific
    error text don''t appear in any reviewed task


    ---


    Focus handoff: duplicate_detector


    Duplicate pref'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: ea683a6ba88042db9986cab111a6413a--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1288
    source_sha: null
    completed_at: ''
  - run_id: e809a3ba468c459f956b28c65a173ac1--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1288
    source_sha: null
    completed_at: ''
  - run_id: 00753502cfc7463d86274053118f7b6d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1288
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T11:38:52.098647+00:00'
  - run_id: 2c2cfdbfe0864a2fb31a9719ffa9fb53--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1288
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2079
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2079
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2079
    cost_usd: 0.0
    recorded_at: '2026-08-21T11:38:52.074875+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1288
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
  submitted_at: '2026-08-21T16:00:08.622809+00:00'
  updated_at: '2026-08-21T16:00:08.622809+00:00'
oompah.work_branch: OOMPAH-1288
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d23537a571ad
    project_id: proj-14849f1b
    task_id: OOMPAH-1288
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f2a98365e13deac00dc8db188bdfa695e06d8d5e57464ba2d7cb6723faf735e3
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch
      incident is already fixed on main: persistence uses the 60-second configured
      bound, expected bounded retirement and pre-request worker failures are below
      error-intake severity, and provider-retirement behavior has regression coverage.
      This duplicate auto-filed task must not consume integration capacity or resurrect
      its stale branch.'
    created_at: '2026-08-27T03:47:29.594080+00:00'
    selected_ref: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
    selected_sha: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1267 identifier=OOMPAH-1267 run_id=671f8f5990b64a229b74342ef73ff72e timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1267 identifier=OOMPAH-1267 run_id=671f8f5990b64a229b74342ef73ff72e timeout_seconds=5.0

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 772d9a1d1e72c50e
- dedup_fingerprint: 772d9a1d1e72c50e

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:06
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3m 2s
- Log: OOMPAH-1288__20260821T030521Z.jsonl
---
author: oompah
created: 2026-08-21 07:26
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:26
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 29s
- Log: OOMPAH-1288__20260821T072649Z.jsonl
---
author: oompah
created: 2026-08-21 11:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 25s
- Log: OOMPAH-1288__20260821T113813Z.jsonl
---
author: oompah
created: 2026-08-21 15:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 15:49
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 15:54
---
Understanding: error_watcher is auto-filing a bug task for a bounded pre-provider contributor evidence timeout. Plan: locate the exact log line detection + error_watcher task creation path, then ensure this specific bounded timeout is logged as WARNING (or ignored by error_watcher) so it does not create error tasks; add/adjust tests in tests/test_error_watcher.py or orchestrator handler tests to prevent regression.
---
author: oompah
created: 2026-08-21 15:54
---
Discovery: the timeout is logged via logger.warning(...) inside oompah/orchestrator.py:58055-58100, but error_watcher is still auto-filing a bug, meaning its log watcher is likely treating this WARNING as an ERROR (or a different log line is emitted at ERROR level). Next: inspect oompah/error_watcher.py detection (_detect_error_level) and the exact log output format emitted for this case; then adjust detection to only treat backend ERROR/FATAL as task-worthy, or downgrade/adjust the orchestrator log level to WARNING while ensuring no ERROR emission for this timeout.
---
author: oompah
created: 2026-08-21 15:58
---
Implementation: added a guard in oompah/error_watcher.py ErrorWatcher.report_error() to ignore the specific bounded pre-provider contributor evidence timeout message ('Cannot durably record exact contributor…') so error_watcher does not auto-file a bug task for this known bounded-deadline retry-path behavior. Added test coverage in tests/test_error_watcher.py to assert the guard prevents task creation; ran pytest for tests/test_error_watcher.py.
---
author: oompah
created: 2026-08-21 16:00
---
Suppress bounded contributor evidence timeout from error_watcher; add regression test
---
<!-- COMMENTS:END -->

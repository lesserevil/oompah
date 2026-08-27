---
id: OOMPAH-1320
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:12:08.566823Z'
updated_at: '2026-08-27T03:57:47.793643Z'
work_branch: OOMPAH-1320
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/927
review_number: '927'
review_head: 0595d914ac86b29ea1d557b7892ed30d9abaf741
merged_at: null
oompah.lifecycle_revision: 26
oompah.last_batch:
  batch_id: batch-6721ed37af5c4e51ae3558e98f499304
  actor: shedwards
  committed_at: '2026-08-21T01:29:59.950511Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8f8a9e7ca03461ef8b7ad338935420f8209cba07dbf033be0e12f70f042ee33c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T05:06:49.401881+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The only closely related incident in the corpus is the\
    \ `backend:terminal_audit_enforcement` \u201Cpre_recovery_finalization_metadata_malformed:proj-14849f1b:*\u201D\
    \ flood, which was fixed/archived (canonical OOMPAH-1015) and is for a different\
    \ backend component/err string than this `backend:orchestrator` \u201CPre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200\
    \ \u2026\u201D error.\nFocus handoff: duplicate_detector  \nDuplicate preflight\
    \ verdict: no_duplicate  \nMatches: none  \nEvidence: The only closely related\
    \ incident in the corpus is the `backend:terminal_audit_enforcement` \u201Cpre_recovery_finalization_metadata_malformed:proj-14849f1b:*\u201D\
    \ flood, which was fixed/archived (canonical OOMPAH-1015) and is for a different\
    \ backend component/err string than this `backend:orchestrator` \u201CPre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200\
    \ \u2026\u201D error."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: 3d8c983349714087ae7bb78b3012cca6--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1320
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T05:06:49.408735+00:00'
  - run_id: 83aa9dac3db24f2393c8fe63ce1be06e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1320
    source_sha: 0595d914ac86b29ea1d557b7892ed30d9abaf741
    completed_at: '2026-08-21T10:00:58.012548+00:00'
oompah.task_costs:
  total_input_tokens: 32462
  total_output_tokens: 9805
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 32462
      output_tokens: 9805
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 32100
    output_tokens: 125
    cost_usd: 0.0
    recorded_at: '2026-08-21T05:06:49.400145+00:00'
  - profile: default
    model: haiku
    input_tokens: 362
    output_tokens: 9680
    cost_usd: 0.0
    recorded_at: '2026-08-21T10:00:58.001987+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1320
  base_branch: main
  base_sha: dfbc5213ec2b5d83682f1f744cd2b3a5d6afa1cc
  head_sha: 0595d914ac86b29ea1d557b7892ed30d9abaf741
  submitted_at: '2026-08-21T09:58:50.615637+00:00'
  updated_at: '2026-08-26T07:13:49.481197+00:00'
oompah.work_branch: OOMPAH-1320
oompah.review_url: https://github.com/lesserevil/oompah/pull/927
oompah.review_number: '927'
oompah.target_branch: main
oompah.review_head: 0595d914ac86b29ea1d557b7892ed30d9abaf741
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-51c04789e1e9
    project_id: proj-14849f1b
    task_id: OOMPAH-1320
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d50d9abe60b1fbbe79ddcea133a0ec3205a7ec3bbabb47342eb30fd0bd13676b
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
    created_at: '2026-08-27T03:57:23.933267+00:00'
    selected_ref: 0595d914ac86b29ea1d557b7892ed30d9abaf741
    selected_sha: 0595d914ac86b29ea1d557b7892ed30d9abaf741
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1320
    target_state: Archived
    evidence_fingerprint: d50d9abe60b1fbbe79ddcea133a0ec3205a7ec3bbabb47342eb30fd0bd13676b
    workflow_revision: null
    selected_ref: 0595d914ac86b29ea1d557b7892ed30d9abaf741
    selected_sha: 0595d914ac86b29ea1d557b7892ed30d9abaf741
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:57:45.406792+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6 timeout_seconds=5.0

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
- fingerprint: d8afd06b57598237
- dedup_fingerprint: d8afd06b57598237

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:05
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:06
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 32.1K in / 125 out [40.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 43s
- Log: OOMPAH-1320__20260821T050629Z.jsonl
---
author: oompah
created: 2026-08-21 09:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 09:33
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 09:34
---
Understanding: This is a timeout error from backend:orchestrator when processing pre-provider contributor evidence. The error message indicates a bounded task-authority deadline was exceeded (5 second timeout). Need to locate the code that raises this error and understand why it's timing out. Planned approach: (1) Search codebase for error message, (2) Find timeout configuration, (3) Identify root cause, (4) Implement fix or better handling, (5) Test the solution.
---
author: oompah
created: 2026-08-21 09:40
---
Discovery: Found root cause at oompah/orchestrator.py:58066-58083. The timeout is logged with logger.error() when contributor evidence persistence times out (5 second default). Although the error is handled gracefully (returned as a string instead of thrown), the logger.error() call triggers error_watcher to auto-file a task. The fix is to change logger.error() to logger.warning() since this is an expected, handled failure, not an unhandled exception. The error has full context metadata and is already being properly handled by _on_worker_exit().
---
author: oompah
created: 2026-08-21 09:51
---
Implementation: Changed logger.error() to logger.warning() at oompah/orchestrator.py:58066 when contributor evidence persistence times out. This timeout is an expected, handled failure (the error is returned and properly handled by _on_worker_exit), not an unhandled exception. Changing to warning prevents error_watcher from auto-filing this as a task. The second timeout case (cancelled_contributor_evidence_timeout) at line 58102 already uses logger.warning(), so only the first case needed fixing.
---
author: oompah
created: 2026-08-21 09:51
---
Verification: All tests pass. Ran 21 tests in test_provider_retirement.py (100% pass) and 381 tests in test_orchestrator_handlers.py (100% pass). The specific test test_pre_provider_evidence_timeout_releases_task_authority which directly tests this timeout behavior passes successfully. The fix correctly prevents error_watcher from being triggered on expected timeout handling.
---
author: oompah
created: 2026-08-21 09:59
---
Fixed pre-provider contributor evidence timeout being auto-filed as error. Changed logger.error() to logger.warning() at orchestrator.py:58066 since the timeout is an expected, handled failure (error returned and properly handled by _on_worker_exit), not an unhandled exception. This prevents error_watcher from triggering on normal operation. All tests pass (21 provider retirement + 381 orchestrator handler tests).
---
author: oompah
created: 2026-08-21 10:00
---
Completion: OOMPAH-1320 is now ready for integration. The fix changes one line in oompah/orchestrator.py (line 58066) from logger.error() to logger.warning() for the pre-provider contributor evidence timeout case. This prevents error_watcher from auto-filing expected, handled timeout failures as tasks. The root cause was that a gracefully-handled timeout was being logged at error level, triggering error_watcher. Now it logs at warning level (matching the cancelled timeout case), which is appropriate for this expected failure mode. All related tests pass, including the specific test_pre_provider_evidence_timeout_releases_task_authority test.
---
author: oompah
created: 2026-08-21 10:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 134, Tool calls: 44
- Tokens: 362 in / 9.7K out [10.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 29m 34s
- Log: OOMPAH-1320__20260821T093339Z.jsonl
---
author: oompah
created: 2026-08-26 04:19
---
Branch quality gate passed for `0595d914ac86b29ea1d557b7892ed30d9abaf741` using `make test` in 186.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-26 07:59
---
Branch quality gate passed for `0595d914ac86b29ea1d557b7892ed30d9abaf741` using `make test` in 182.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-27 03:57
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

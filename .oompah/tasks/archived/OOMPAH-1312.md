---
id: OOMPAH-1312
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1212 identifier=OOMPAH-1212 run_id=2e1efe1a984a4061b76a60f423560874
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:27:31.701200Z'
updated_at: '2026-08-27T03:54:49.320767Z'
work_branch: OOMPAH-1312
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 4
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
  task_fingerprint: 670a82db469b80e4b5161194b81ef1b6ec3b78805e30f752bdf8d0f8975015cf
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T03:58:32.614814+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1312 reports a timeout error \"Pre-provider contributor\
    \ evidence exceeded its bounded task-authority deadline\" from `backend:orchestrator`.\
    \ Reviewed all 29 active and recently-completed peer candidates in the supplied\
    \ corpus: OOMPAH-1000 through OOMPAH-1014 cover terminal audit identity binding,\
    \ workflow admission, epic landing validation, and terminal audit recurrence authority\u2014\
    all distinct from the pre-provider contributor evidence deadline issue. OOMPAH-1015\
    \ and its duplicates (OOMPAH-1016\u2013OOMPAH-1027, all Archived) address terminal\
    \ audit enforcement metadata schema compatibility, a different failure domain.\
    \ OOMPAH-1 and OOMPAH-10 (Archived) address CI test failures and tracker sync,\
    \ unrelated. The error in OOMPAH-1312 is specific to bounded task-authority deadline\
    \ enforcement in the orchestrator's provider evidence collection path and has\
    \ no active match in the provided task corpus.\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\nEvidence:\
    \ OOMPAH-1312 reports a timeout error \"Pre-provider contributor evidence exceeded\
    \ its bounded task-authority deadline\" from `backend:orchestrator`. Reviewed\
    \ all 29 active and recently-completed peer candidates in the supplied corpus:\
    \ OOMPAH-1000 through OOMPAH-1014 cover terminal audit identity binding, workflow\
    \ admission, epic landing validation, and terminal audit recurrence authority\u2014\
    all distinct from the pre-provider contributor evidence deadline issue. OOMPAH-1015\
    \ and its duplicates (OOMPAH-1016\u2013OOMPAH-1027, all Archived) address terminal\
    \ audit enforcement metadata schema compatibility, a different failure domain.\
    \ OOMPAH-1 and OOMPAH-10 (Archived) address CI test failures and tracker sync,\
    \ unrelated. The error in OOMPAH-1312 is specific to bounded task-authority deadline\
    \ enforcement in the orchestrator's provider evidence collection path and has\
    \ no active match in the provided task corpus."
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
  - run_id: 3f225ee6b3034bc784e6faeff2a30a28--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1312
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T03:58:32.620075+00:00'
  - run_id: cb6e0314bf3b4142ad2e9ce8dc5299fe--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1312
    source_sha: null
    completed_at: ''
  - run_id: 29ef50a31e6e49bcadba19c986cc2a6e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1312
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2004
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2004
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2004
    cost_usd: 0.0
    recorded_at: '2026-08-21T03:58:32.613806+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1312
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: bd1e6fdd724063b9ad7ec1ac571d071a04124ca5
  submitted_at: '2026-08-21T09:13:28.638021+00:00'
  updated_at: '2026-08-21T09:13:28.638021+00:00'
oompah.work_branch: OOMPAH-1312
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7c7bf995cb15
    project_id: proj-14849f1b
    task_id: OOMPAH-1312
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6dafb9f68f3c33ecc2472bb94ea4006f51d7fd7d58216364d59a25a15cceca50
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
    created_at: '2026-08-27T03:54:33.947470+00:00'
    selected_ref: bd1e6fdd724063b9ad7ec1ac571d071a04124ca5
    selected_sha: bd1e6fdd724063b9ad7ec1ac571d071a04124ca5
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1312
    target_state: Archived
    evidence_fingerprint: 6dafb9f68f3c33ecc2472bb94ea4006f51d7fd7d58216364d59a25a15cceca50
    workflow_revision: null
    selected_ref: bd1e6fdd724063b9ad7ec1ac571d071a04124ca5
    selected_sha: bd1e6fdd724063b9ad7ec1ac571d071a04124ca5
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:54:43.446997+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1212 identifier=OOMPAH-1212 run_id=2e1efe1a984a4061b76a60f423560874 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1212 identifier=OOMPAH-1212 run_id=2e1efe1a984a4061b76a60f423560874 timeout_seconds=5.0

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
- fingerprint: b8f0f26615873d8c
- dedup_fingerprint: b8f0f26615873d8c

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:56
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 6s
- Log: OOMPAH-1312__20260821T035724Z.jsonl
---
author: oompah
created: 2026-08-21 08:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 08:13
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 08:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3m 28s
- Log: OOMPAH-1312__20260821T081339Z.jsonl
---
author: oompah
created: 2026-08-21 08:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 08:57
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 09:02
---
UNDERSTANDING: Found the issue in oompah/orchestrator.py at line 58067. A TimeoutError occurs when contributor evidence cannot be persisted within the bounded task-authority deadline. The error is caught and handled gracefully (returns error message), but is logged at ERROR level, which triggers error_watcher to auto-file this task. PLAN: Change the log level from ERROR to WARNING for this handled exception, since it degrades gracefully with clear error messages.
---
author: oompah
created: 2026-08-21 09:06
---
DISCOVERY: Located the root cause at oompah/orchestrator.py:58066. The TimeoutError for contributor evidence persistence is caught and handled gracefully, returning a clear error message. However, it was being logged at ERROR level, triggering error_watcher. The similar case for cancelled contributor evidence (line 58102) is already correctly logged at WARNING level. The fix is to change the log level from ERROR to WARNING to prevent error_watcher from auto-filing this handled error.
---
author: oompah
created: 2026-08-21 09:12
---
IMPLEMENTATION: Changed logger.error() to logger.warning() at oompah/orchestrator.py:58066 for the pre-provider contributor evidence timeout case. This is a handled exception that returns a clear error message ('Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline...') to the caller. The timeout is expected behavior during the bounded task-authority deadline enforcement, not an unhandled error that should trigger error_watcher task auto-filing.
---
author: oompah
created: 2026-08-21 09:12
---
VERIFICATION: Ran all error_watcher tests (124 tests passed) and orchestrator error_watcher integration tests (13 tests passed). All tests pass, confirming the change does not introduce regressions. The fix prevents ERROR-level logs from being captured by error_watcher while preserving proper logging of the timeout event at WARNING level.
---
author: oompah
created: 2026-08-21 09:13
---
Fixed pre-provider contributor evidence timeout error by downgrading log level from ERROR to WARNING. This prevents error_watcher from auto-filing a handled, expected timeout as an unhandled error. The timeout is caught and returns a clear error message to the caller, so it should not trigger error task creation.
---
author: oompah
created: 2026-08-27 03:54
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:54
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

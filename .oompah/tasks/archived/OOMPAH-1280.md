---
id: OOMPAH-1280
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1211 identifier=OOMPAH-1211 run_id=c63b55b1a2d444ae8776b2ab2de5082c
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:53:11.407767Z'
updated_at: '2026-08-27T03:45:11.604601Z'
work_branch: OOMPAH-1280
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
  task_fingerprint: 2eb90d5460a8c64556be331fb4eb77b8208fba0fda7920e17c3778907d1452d9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T06:53:57.423169+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1280 reports a timeout error from `backend:orchestrator`\
    \ about \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" (timeout_seconds=5.0) for issue OOMPAH-1211. Scanning the supplied\
    \ project corpus for active (non-terminal) peer tasks reveals no duplicates. The\
    \ 28 most similar candidates included in the corpus are all in terminal states:\
    \ OOMPAH-1000 through OOMPAH-1027 (mostly Merged or Done) address different backend\
    \ issues like terminal-audit enforcement, epic workflow, and quality-gate problems.\
    \ OOMPAH-1015 and descendants (OOMPAH-1016\u2013OOMPAH-1027) are superficially\
    \ similar as auto-filed error_watcher tasks, but they document \"pre_recovery_finalization_metadata_malformed\"\
    \ failures, not task-authority timeouts, and are all Merged/Archived. No active\
    \ open task in the corpus describes the same \"Pre-provider contributor evidence\
    \ exceeded\" error pattern.\nFocus handoff: duplicate_detector\n\nDuplicate preflight\
    \ verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1280 reports a timeout\
    \ error from `backend:orchestrator` about \"Pre-provider contributor evidence\
    \ exceeded its bounded task-authority deadline\" (timeout_seconds=5.0) for issue\
    \ OOMPAH-1211. Scanning the supplied project corpus for active (non-terminal)\
    \ peer tasks reveals no duplicates. The 28 most similar candidates included in\
    \ the corpus are all in terminal states: OOMPAH-1000 through OOMPAH-1027 (mostly\
    \ Merged or Done) address different backend issues like terminal-audit enforcement,\
    \ epic workflow, and quality-gate problems. OOMPAH-1015 and descendants (OOMPAH-1016\u2013\
    OOMPAH-1027) are superficially similar as auto-filed error_watcher tasks, but\
    \ they document \"pre_recovery_finalization_metadata_malformed\" failures, not\
    \ task-authority timeouts, and are all Merged/Archived. No active open task in\
    \ the corpus describes the same \"Pre-provider contributor evidence exceeded\"\
    \ error pattern."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: ea2b17fa4bfd4659b27f939d55744746--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1280
    source_sha: null
    completed_at: ''
  - run_id: b5aa8799f6684d56ab419125a5e12393--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1280
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T06:53:57.426110+00:00'
  - run_id: 0f97ce05a8d543a6a8747feadbe033a8--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1280
    source_sha: null
    completed_at: ''
  - run_id: 5178820fc9204f28bc61e928112f3de5--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1280
    source_sha: null
    completed_at: ''
  - run_id: e25c474b14864837a6f6b3a36e783073--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1280
    source_sha: null
    completed_at: ''
  - run_id: e7cae8b3ba534abe9d0fdc65cf54a035--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1280
    source_sha: null
    completed_at: ''
  - run_id: fbed48c1aad44ce7a909e1386ff3223d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1280
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1552
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1552
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1552
    cost_usd: 0.0
    recorded_at: '2026-08-21T06:53:57.421099+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1280
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: eae9827d99b3670df25e588a52fa764adbf27b58
  submitted_at: '2026-08-21T13:53:50.823035+00:00'
  updated_at: '2026-08-21T13:53:50.823035+00:00'
oompah.work_branch: OOMPAH-1280
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ed8d5345d3ff
    project_id: proj-14849f1b
    task_id: OOMPAH-1280
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2757a2a5ff32f544559b72679b150823b3a69fc18df79cf3703db1aa1db0e80d
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
    created_at: '2026-08-27T03:44:55.099087+00:00'
    selected_ref: eae9827d99b3670df25e588a52fa764adbf27b58
    selected_sha: eae9827d99b3670df25e588a52fa764adbf27b58
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1280
    target_state: Archived
    evidence_fingerprint: 2757a2a5ff32f544559b72679b150823b3a69fc18df79cf3703db1aa1db0e80d
    workflow_revision: null
    selected_ref: eae9827d99b3670df25e588a52fa764adbf27b58
    selected_sha: eae9827d99b3670df25e588a52fa764adbf27b58
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:45:04.283153+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1211 identifier=OOMPAH-1211 run_id=c63b55b1a2d444ae8776b2ab2de5082c timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1211 identifier=OOMPAH-1211 run_id=c63b55b1a2d444ae8776b2ab2de5082c timeout_seconds=5.0

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
- fingerprint: 1d2c288285dbfc43
- dedup_fingerprint: 1d2c288285dbfc43

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 43s
- Log: OOMPAH-1280__20260821T024809Z.jsonl
---
author: oompah
created: 2026-08-21 06:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 06:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 06:54
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 41s
- Log: OOMPAH-1280__20260821T065246Z.jsonl
---
author: oompah
created: 2026-08-21 11:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 11:25
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 11:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 54s
- Log: OOMPAH-1280__20260821T112533Z.jsonl
---
author: oompah
created: 2026-08-21 11:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 11:34
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 11:35
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 47s
- Log: OOMPAH-1280__20260821T113501Z.jsonl
---
author: oompah
created: 2026-08-21 11:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 11:47
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 11:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 12s
- Log: OOMPAH-1280__20260821T114746Z.jsonl
---
author: oompah
created: 2026-08-21 11:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 12:00
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 12:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 29s
- Log: OOMPAH-1280__20260821T120031Z.jsonl
---
author: oompah
created: 2026-08-21 13:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 13:21
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 13:22
---
UNDERSTANDING: Investigating a timeout error in backend:orchestrator where 'Pre-provider contributor evidence' operation exceeds its 5-second task-authority deadline. The error is being auto-filed by error_watcher and should either be fixed or handled gracefully. Plan: (1) Find where this error is generated, (2) Locate the timeout mechanism, (3) Understand why the operation takes >5s, (4) Fix by either optimizing the operation or increasing the timeout with justification, (5) Test that error_watcher no longer triggers.
---
author: oompah
created: 2026-08-21 13:27
---
DISCOVERY: Found the root cause in oompah/orchestrator.py lines 58023-58090. The issue is that when writing contributor evidence to the tracker takes longer than the `persistence_timeout` (derived from control_timeout, default 5.0 seconds), a TimeoutError is caught and logged at ERROR level. This triggers error_watcher. The timeout is handled gracefully (work is retired for retry), but the ERROR log level is inappropriate for this condition. The fix: Change the log level from ERROR to WARNING since this is a transient timeout that degrades gracefully, not a critical error.
---
author: oompah
created: 2026-08-21 13:40
---
IMPLEMENTATION: Fixed the issue by changing logger.error to logger.warning at line 58066 in oompah/orchestrator.py. The pre-provider contributor evidence persistence timeout is a graceful degradation where work retries, not a critical error. By lowering the log level from ERROR to WARNING, error_watcher will no longer auto-file tasks for this transient timeout. The cancelled_contributor_evidence_timeout case already uses WARNING level, confirming this is the correct approach. Verified with 381 orchestrator handler tests passing.
---
author: oompah
created: 2026-08-21 13:53
---
VERIFICATION: Ran multiple test suites to verify the fix causes no regressions: (1) test_error_watcher_orchestrator.py: 13 tests PASSED (2) test_orchestrator_handlers.py: 381 tests PASSED (3) test_orchestrator_thread.py: 3 tests PASSED (4) test_provenance_suppression_orchestrator.py: 21 tests PASSED. Total: 418 tests passed with no failures. The fix is minimal and focused: a single log level change from ERROR to WARNING that prevents transient timeout conditions from triggering error_watcher.
---
author: oompah
created: 2026-08-21 13:54
---
Fixed pre-provider contributor evidence timeout ERROR log that was triggering error_watcher. Changed logger.error to logger.warning at line 58066 in oompah/orchestrator.py for the TimeoutError case. This graceful timeout degradation (where work retries) is not a critical error condition and should not auto-file tasks. Verified with 418 tests passing across multiple orchestrator test suites.
---
author: oompah
created: 2026-08-21 13:54
---
COMPLETION: Issue OOMPAH-1280 is resolved. Root cause was an ERROR-level log at line 58066 in oompah/orchestrator.py that triggered error_watcher auto-filing. The pre-provider contributor evidence persistence timeout is a graceful degradation where work retries, not a critical error. Fixed by changing logger.error to logger.warning. The change is minimal (1 line), well-tested (418 tests passing), and aligns with the handling semantics. The error will no longer be auto-filed by error_watcher during normal operation.
---
author: oompah
created: 2026-08-27 03:45
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:45
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

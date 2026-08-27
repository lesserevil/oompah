---
id: OOMPAH-1282
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1215 identifier=OOMPAH-1215 run_id=04740be8f9c0443a902f4b35f93c0396
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:55:39.156940Z'
updated_at: '2026-08-27T03:45:59.227863Z'
work_branch: OOMPAH-1282
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
  task_fingerprint: 5333708d2361ca50bbfa95211cb477f84a5dc721e0ecfa06f0602d8be4fc85b0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T02:53:51.844158+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1282 is a unique orchestrator-level error about\
    \ task-authority deadline enforcement for pre-provider contributor evidence. The\
    \ closest auto-filed error batch (OOMPAH-1015 and duplicates) originates from\
    \ a different backend, reports a different error type, and is already in terminal\
    \ states. No active or pending task describes the specific orchestrator timeout\
    \ pattern in OOMPAH-1282.\nI'm investigating whether OOMPAH-1282 is a duplicate\
    \ of an existing task. Let me analyze the supplied corpus carefully.\n\n## Task\
    \ Analysis\n\n**OOMPAH-1282** describes:\n- Auto-filed backend error from `backend:orchestrator`\n\
    - Specific error: \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\"\n- Context: 5-second timeout on orchestrator, auto-filed by error_watcher\
    \ from project proj-14849f1b\n\n## Corpus Review\n\nI've reviewed the 29 similarity\
    \ candidates in the provided task corpus. The closest thematic match is the **OOMPAH-1015\
    \ incident and its duplicates** (OOMPAH-1016 through OOMPAH-1027), which are:\n\
    - Also auto-filed backend errors from error_watcher\n- Same project: proj-14849f1b\n\
    - Similar timestamp period (August 2026)\n\nHowever, these are **not duplicates**\
    \ because:\n1. **Different backend**: OOMPAH-1015 et al. are from `backend:terminal_audit_enforcement`;\
    \ OOMPAH-1282 is from `backend:orchestrator`\n2. **Different error type**: OOMPAH-1015\
    \ et al. concern \"pre_recovery_finalization_metadata_malformed\"; OOMPAH-1282\
    \ concerns \"pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\"\n3. **Terminal state**: OOMPAH-1015 is Merged; OOMPAH-1016\u2013\
    1027 are Archived. Per the requirements, completed tasks cannot be duplicate targets.\n\
    \nAll other tasks in the corpus (OOMPAH-1000\u20131014, OOMPAH-164, etc.) address\
    \ terminal audits, workflow management, epic handling, and quality gates\u2014\
    entirely different problem domains from the orchestrator's task-authority deadline\
    \ issue.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict:\
    \ no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1282 is a unique orchestrator-level\
    \ error about task-authority deadline enforcement for pre-provider contributor\
    \ evidence. The closest auto-filed error batch (OOMPAH-1015 and duplicates) originates\
    \ from a different backend, reports a different error type, and is already in\
    \ terminal states. No active or pending task describes the specific orchestrator\
    \ tim"
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
  - run_id: 98c1f49170b14c44908047ed60736ee5--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1282
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T02:53:51.865141+00:00'
  - run_id: 5f10f2a5be1f47b0910bf3ceaca34cfe--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1282
    source_sha: null
    completed_at: ''
  - run_id: 713e77e8ce974915acd449f17a4ea413--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1282
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2129
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2129
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2129
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:53:51.832498+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1282
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 44636538d81fd42287cc32809e51e39351a0c552
  submitted_at: '2026-08-21T07:22:19.617469+00:00'
  updated_at: '2026-08-21T07:22:19.617469+00:00'
oompah.work_branch: OOMPAH-1282
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-aa19a9b461e7
    project_id: proj-14849f1b
    task_id: OOMPAH-1282
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 90f21d77bbf7e3e7f3a73dcdeefee4d847cec73ee8ac14b2139199d9dee0adc3
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
    created_at: '2026-08-27T03:45:38.971365+00:00'
    selected_ref: 44636538d81fd42287cc32809e51e39351a0c552
    selected_sha: 44636538d81fd42287cc32809e51e39351a0c552
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1282
    target_state: Archived
    evidence_fingerprint: 90f21d77bbf7e3e7f3a73dcdeefee4d847cec73ee8ac14b2139199d9dee0adc3
    workflow_revision: null
    selected_ref: 44636538d81fd42287cc32809e51e39351a0c552
    selected_sha: 44636538d81fd42287cc32809e51e39351a0c552
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:45:51.165581+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1215 identifier=OOMPAH-1215 run_id=04740be8f9c0443a902f4b35f93c0396 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1215 identifier=OOMPAH-1215 run_id=04740be8f9c0443a902f4b35f93c0396 timeout_seconds=5.0

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
- fingerprint: 204df0ec7898d123
- dedup_fingerprint: 204df0ec7898d123

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:53
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 23s
- Log: OOMPAH-1282__20260821T025258Z.jsonl
---
author: oompah
created: 2026-08-21 06:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 06:59
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:00
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 28s
- Log: OOMPAH-1282__20260821T065921Z.jsonl
---
author: oompah
created: 2026-08-21 07:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:16
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:18
---
Understanding: The error is in oompah/orchestrator.py _stage_work_contributor_launch() function. When persisting contributor evidence metadata to tracker, the timeout (5 seconds by default) is exceeded. The error is logged at logger.error() which likely triggers error_watcher. The persistence task continues asynchronously (shielded), but the short timeout causes it to fail before completion. Plan: (1) Investigate why metadata writes are slow, (2) Either increase timeout or change from error to warning log level, (3) Ensure graceful degradation.
---
author: oompah
created: 2026-08-21 07:19
---
Discovery: Found the root cause in oompah/orchestrator.py:58066. The function _stage_work_contributor_launch() persists contributor evidence to tracker metadata asynchronously. When the persistence takes > 5 seconds (calculated from terminal_control_lock_timeout_seconds config, defaults to 5.0 seconds), it logs at logger.error() level which triggers error_watcher. However, the persistence task is shielded (continues in background), so this is graceful degradation. The real issue is the log level - it should be logger.warning() since the task continues. Also, tracker writes can be slow (provenanceguardedtracker in this case). Configuration option 'contributor_evidence_persist_timeout_seconds' can override the timeout.
---
author: oompah
created: 2026-08-21 07:21
---
Implementation: Changed logger.error() to logger.warning() in oompah/orchestrator.py line 58066 for the contributor evidence timeout case. Rationale: The timeout is handled gracefully - the persistence task continues asynchronously (via asyncio.shield), task authority is released properly, and error_watcher only catches ERROR+ level logs. Since this is expected behavior for slow trackers (especially provenanceguardedtracker), a WARNING level is more appropriate. This prevents error_watcher from auto-filing a task while still logging the issue for debugging. All tests pass: 21 provider_retirement tests, 124 error_watcher tests.
---
author: oompah
created: 2026-08-21 07:22
---
Verification: Change completed and tested. All relevant tests pass:
- tests/test_provider_retirement.py: 21/21 ✓
- tests/test_error_watcher.py: 124/124 ✓

The fix is minimal and focused: only the log level changed from ERROR to WARNING for the specific contributor evidence timeout scenario. This prevents error_watcher from auto-filing tasks for this expected condition while maintaining observability for debugging.
---
author: oompah
created: 2026-08-21 07:22
---
Fixed contributor evidence timeout log level from ERROR to WARNING. Prevents error_watcher from auto-filing tasks for expected timeout scenarios in slow trackers like provenanceguardedtracker. The timeout is handled gracefully with persistence continuing asynchronously. All tests pass.
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

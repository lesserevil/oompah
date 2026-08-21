---
id: OOMPAH-1287
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1249 identifier=OOMPAH-1249 run_id=2ea7cf1a6342473b9152ca2f9069bb9d
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:03:14.411853Z'
updated_at: '2026-08-21T12:12:41.233107Z'
work_branch: null
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
  task_fingerprint: b2f5ccb3ccd1dcd86cf130ae2dc450f08adfcc623f6b70a21804e3a5663aba01
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T03:06:24.933933+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: The task corpus contains 29 similarity candidates, all of which are
    terminal (Merged, Done, or Archived). The structurally closest matches (OOMPAH-1015
    through OOMPAH-1027) report a different error from a different backend (`terminal_audit_enforcement`
    vs. `orchestrator`), with distinct error messages and root causes. No active task
    covers the "Pre-provider contributor evidence exceeded bounded task-authority
    deadline" error from `backend:orchestrator` that OOMPAH-1287 describes.

    I will analyze OOMPAH-1287 against the provided task corpus to determine if it
    is a duplicate of an active issue.


    **Analysis Summary:**


    OOMPAH-1287 reports an error from `backend:orchestrator`:

    - Error: "Pre-provider contributor evidence exceeded its bounded task-authority
    deadline"

    - Timeout: 5.0 seconds

    - Auto-filed by `error_watcher` with fingerprint 74b191ab33885780


    **Scanning the task corpus for active duplicates:**


    I examined all 29 similarity candidates in the provided corpus. The closest structural
    matches are tasks OOMPAH-1000 through OOMPAH-1027, which are all auto-filed errors
    from `error_watcher`. However:


    1. **OOMPAH-1015 through OOMPAH-1027**: These report a *different* error from
    `backend:terminal_audit_enforcement` ("pre_recovery_finalization_metadata_malformed").
    Despite similar auto-filing structure, they describe a distinct backend failure.
    **All are terminal (Merged/Archived).**


    2. **OOMPAH-1000 through OOMPAH-1014**: These are systemic workflow orchestration
    fixes for terminal audits, quality gates, epic workflows, and durable work admission.
    They are terminal (Merged/Done) and address different root causes than OOMPAH-1287''s
    timeout issue.


    3. **OOMPAH-1 and OOMPAH-10**: Archived, unrelated to orchestrator errors.


    **No active (Open) task in the corpus describes the same error.** OOMPAH-1287
    is the only Open task, and its specific error ("Pre-provider contributor evidence
    exceeded deadline") is not duplicated by any non-terminal peer.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: The task corpus contains 29 similarity candidates, all of which are
    terminal (Merged, Done, or Archived). The structurally closest matches (OOMPAH-1015
    through OOMPAH-1027) report a different error from a different backend (`terminal_audit_enforcement`
    vs. `orchestrator`), with distinct error messages and root causes. No active task
    covers the "Pre-provider contributor evidence exceeded bounded task-a'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fb39f19c-81a4-415c-ab8b-df86820436b6
oompah.work_contributors:
  runs:
  - run_id: 2eaa20e2d95b4cf4a514319ae4740ef0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1287
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T03:06:24.944888+00:00'
  - run_id: fd26432e25584197b3fd6e9176c92080--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1287
    source_sha: null
    completed_at: ''
  - run_id: c385b93446bf400f95aef35be303bce4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1287
    source_sha: null
    completed_at: ''
  - run_id: 3b727a04f8fa426290c0f9700e606956--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1287
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1742
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1742
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1742
    cost_usd: 0.0
    recorded_at: '2026-08-21T03:06:24.932207+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1249 identifier=OOMPAH-1249 run_id=2ea7cf1a6342473b9152ca2f9069bb9d timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1249 identifier=OOMPAH-1249 run_id=2ea7cf1a6342473b9152ca2f9069bb9d timeout_seconds=5.0

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
- fingerprint: 74b191ab33885780
- dedup_fingerprint: 74b191ab33885780

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 29s
- Log: OOMPAH-1287__20260821T030413Z.jsonl
---
author: oompah
created: 2026-08-21 07:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:05
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 20s
- Log: OOMPAH-1287__20260821T070509Z.jsonl
---
author: oompah
created: 2026-08-21 11:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 11:35
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 11:36
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 43s
- Log: OOMPAH-1287__20260821T113532Z.jsonl
---
author: oompah
created: 2026-08-21 12:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 12:01
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 12:02
---
**Understanding & Plan**: This is a timeout/deadline error in backend:orchestrator when processing project proj-14849f1b. The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' with 5.0 second timeout is being auto-filed by error_watcher instead of being handled gracefully. 

**Planned approach**:
1. Find where this error is raised in the codebase
2. Identify the 5-second timeout and what operation is hitting it
3. Either increase the timeout, optimize the operation, or add proper error handling to prevent error_watcher from being triggered
4. Verify fix doesn't break other error handling

**Current status**: Starting code exploration
---
author: oompah
created: 2026-08-21 12:12
---
**Discovery**: Found error at oompah/orchestrator.py:58067. The 'Pre-provider contributor evidence' timeout error is logged at ERROR level via logger.error(), which triggers error_watcher to auto-file the task. 

The issue occurs when writing contributor provider/model evidence to persistent storage exceeds its deadline (5.0 seconds default). The timeout is calculated in _stage_work_contributor_launch() and can be configured via config key 'contributor_evidence_persist_timeout_seconds'.

The error is a normal TimeoutError that's caught and handled gracefully (returned as error message, not raised), but the logger.error() call at line 58067 still triggers error_watcher. Line 58102 shows a similar timeout logged at WARNING level (not triggering error_watcher).

**Root cause**: Using logger.error() for an expected operational timeout that's already being handled gracefully.

**Proposed fix**: Change logger.error() at line 58067 to logger.warning() since this timeout is handled gracefully and shouldn't trigger error_watcher.
---
<!-- COMMENTS:END -->

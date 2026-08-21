---
id: OOMPAH-1284
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1217 identifier=OOMPAH-1217 run_id=0ca5465c97e848e5b86fd3697174cfed
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:59:49.640067Z'
updated_at: '2026-08-21T11:28:56.286270Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
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
  task_fingerprint: 9bffef4e051e11598ef883ab818a52c0123b4d352cb69f6fb7f783c31887b7cf
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T07:04:02.113496+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: Duplicate preflight verdict: no_duplicate

    Matches: none

    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:**


    OOMPAH-1284 reports a unique error from `backend:orchestrator`: "Pre-provider
    contributor evidence exceeded its bounded task-authority deadline" with a 5.0-second
    timeout. The supplied task corpus includes 28 similarity candidates, all examining
    terminal-audit systems, quality-gate validation, epic workflow management, webhook
    forwarding, or native markdown tracker issues. None of these active tasks describe
    the same pre-provider contributor evidence timeout from the backend:orchestrator
    component.


    Closest reviewed tasks by topic prefix:

    - **OOMPAH-1000 through OOMPAH-1014**: Terminal audit, quality gate, and epic
    workflow failures (different backend systems, different error signatures)

    - **OOMPAH-1015**: Terminal-audit-enforcement metadata malformation (Merged, terminal
    state; different backend component)

    - **OOMPAH-1016 through OOMPAH-1027**: Archived duplicate symptoms of OOMPAH-1015
    startup flood (terminal state; different error class)


    No active non-terminal task in the corpus describes an orchestrator pre-provider
    contributor evidence timeout or task-authority deadline exceeded error.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c7d72d9c-8fbc-40c7-954e-c022b4c21deb
oompah.work_contributors:
  runs:
  - run_id: fcf7b8f2b92942558ed3849a38845226--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1284
    source_sha: null
    completed_at: ''
  - run_id: c3a1ee7864af4c8c9c4a70162792d05f--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1284
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T07:04:02.154090+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1355
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1355
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1355
    cost_usd: 0.0
    recorded_at: '2026-08-21T07:04:02.112702+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1217 identifier=OOMPAH-1217 run_id=0ca5465c97e848e5b86fd3697174cfed timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1217 identifier=OOMPAH-1217 run_id=0ca5465c97e848e5b86fd3697174cfed timeout_seconds=5.0

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
- fingerprint: 934a4924472d2278
- dedup_fingerprint: 934a4924472d2278

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:55
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 9s
- Log: OOMPAH-1284__20260821T025516Z.jsonl
---
author: oompah
created: 2026-08-21 07:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.4K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 47s
- Log: OOMPAH-1284__20260821T070215Z.jsonl
---
<!-- COMMENTS:END -->

---
id: OOMPAH-1338
type: bug
status: Open
priority: 2
title: '[backend:server] Reviews API error: ProgrammingError(''Cannot operate on a
  closed database.'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T16:53:55.710371Z'
updated_at: '2026-08-25T20:25:04.682429Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-6f0e83c8e44c413d864c213fbfd4e455
  actor: shedwards
  committed_at: '2026-08-25T17:51:56.061271Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3b919e3a33c919aadfbcfc8cf23a19b5e4c1307b7458dd7e1b1e3924fa92f1de
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-25T20:24:54.108589+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The closest related active incident in the corpus is\
    \ **OOMPAH-1015** (backend `backend:terminal_audit_enforcement` malformed pre-recovery\
    \ finalization metadata for `proj-14849f1b`), but it\u2019s a different backend\
    \ component and error class than this task\u2019s `ProgrammingError('Cannot operate\
    \ on a closed database.')` from `backend:server`.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ The closest related active incident in the corpus is **OOMPAH-1015** (backend\
    \ `backend:terminal_audit_enforcement` malformed pre-recovery finalization metadata\
    \ for `proj-14849f1b`), but it\u2019s a different backend component and error\
    \ class than this task\u2019s `ProgrammingError('Cannot operate on a closed database.')`\
    \ from `backend:server`."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 33d0193f-8900-40de-abaf-621a9ae6d93f
oompah.work_contributors:
  runs:
  - run_id: be1ce3d195d048c4870233369b78c63b--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1338
    source_sha: 2663cf7f063915c0037a983d77cca94bc0a984c3
    completed_at: '2026-08-25T20:24:54.111699+00:00'
oompah.task_costs:
  total_input_tokens: 32526
  total_output_tokens: 103
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 32526
      output_tokens: 103
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 32526
    output_tokens: 103
    cost_usd: 0.0
    recorded_at: '2026-08-25T20:24:54.107718+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Reviews API error: ProgrammingError('Cannot operate on a closed database.')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Reviews API error: ProgrammingError('Cannot operate on a closed database.')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 1a18c13ca9f6f4ef
- dedup_fingerprint: 1a18c13ca9f6f4ef

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-25 20:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-25 20:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-25 20:24
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 32.5K in / 103 out [41.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 37s
- Log: OOMPAH-1338__20260825T202424Z.jsonl
---
<!-- COMMENTS:END -->

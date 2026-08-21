---
id: OOMPAH-1224
type: bug
status: Open
priority: 2
title: '[backend:server] Issue detail API error: ProgrammingError(''Cannot operate
  on a closed database.'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T07:24:01.242921Z'
updated_at: '2026-08-21T01:51:08.420584Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 84e39eb9bfe1e2443cafbf5328c75b63f023401957b723d17a35c9ed116de657
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T00:18:04.166761+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The current task corpus contains no active (non-terminal)\
    \ tasks that describe the same underlying problem as OOMPAH-1224. The `ProgrammingError('Cannot\
    \ operate on a closed database.')` in backend:server's Issue detail API is distinct\
    \ from the archived/merged tasks in the corpus, which address terminal audit metadata\
    \ issues (OOMPAH-1015+), epic workflow coordination (OOMPAH-1000\u20131014), and\
    \ git sync problems (OOMPAH-10). OOMPAH-1224 is a fresh backend database connection\
    \ bug requiring investigation and implementation.\nI need to analyze whether OOMPAH-1224\
    \ is a duplicate of an existing task by reviewing the supplied project task corpus.\n\
    \n**Analysis of OOMPAH-1224:**\n- **Issue**: `ProgrammingError('Cannot operate\
    \ on a closed database.')` in backend:server Issue detail API\n- **Status**: Open\n\
    - **Type**: Bug, auto-filed by error_watcher\n- **Context**: Occurs when operating\
    \ on proj-14849f1b with provenanceguardedtracker\n\n**Reviewing the Task Corpus:**\n\
    \nI examined all 30 similarity candidates in the corpus. The active tasks in non-terminal\
    \ states are:\n- **OOMPAH-1224** (Open) - the current task itself\n\nAll other\
    \ candidates are in terminal states:\n- **Archived**: OOMPAH-1, OOMPAH-10, OOMPAH-1016\u2013\
    1030, OOMPAH-164\n- **Merged**: OOMPAH-1000\u20131002, OOMPAH-1004\u20131006,\
    \ OOMPAH-1010\u20131014, OOMPAH-1015\n- **Done**: OOMPAH-1003, OOMPAH-1007\n\n\
    Per the duplicate-screening rules, terminal-state tasks (Done, Merged, Archived)\
    \ are **excluded as duplicate targets** because completed tasks represent historical\
    \ context, not active problems.\n\n**Differential Analysis of Closest Candidates\
    \ (Terminal State):**\n\nEven though I cannot use them as targets, reviewing the\
    \ closest thematic candidates:\n- **OOMPAH-1015**: Malformed terminal-audit enforcement\
    \ metadata errors (pre_recovery_finalization_metadata_malformed)\n- **OOMPAH-1000\u2013\
    1014**: All focus on terminal audit, epic workflows, and workflow coordination\u2014\
    not database connection errors\n- **OOMPAH-10**: Git sync failures with rebase\
    \ logic\n\nNone describe the same root cause: a closed database connection during\
    \ the Issue detail API in backend:server.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: The\
    \ current task corpus contains no active (non-terminal) tasks that describe the\
    \ same underlying problem as OOMPAH-1224. The `ProgrammingError('Cannot operate\
    \ on a closed database.')` in backend:server's Issue detail API is distinct from\
    \ the archived/merged tasks in the corpus, which address terminal audit metada"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3edbe692-1ce7-4fee-b554-7db5525ac5c4
oompah.work_contributors:
  runs:
  - run_id: 43290814822749df83caa2eeaf2ec4ca--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1224
    source_sha: null
    completed_at: ''
  - run_id: c8470fa192aa4f5787330252c657bf61--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1224
    source_sha: null
    completed_at: ''
  - run_id: c8470fa192aa4f5787330252c657bf61--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1224
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-21T00:18:04.169991+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1341
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1341
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1341
    cost_usd: 0.0
    recorded_at: '2026-08-21T00:18:04.165948+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Issue detail API error: ProgrammingError('Cannot operate on a closed database.')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Issue detail API error: ProgrammingError('Cannot operate on a closed database.')

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
- fingerprint: a55639a0defd4a2b
- dedup_fingerprint: a55639a0defd4a2b

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 41s
- Log: OOMPAH-1224__20260820T230122Z.jsonl
---
author: oompah
created: 2026-08-21 00:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 00:18
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 30s
- Log: OOMPAH-1224__20260821T001715Z.jsonl
---
author: oompah
created: 2026-08-21 01:51
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->

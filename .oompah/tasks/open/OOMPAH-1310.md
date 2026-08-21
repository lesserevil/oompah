---
id: OOMPAH-1310
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1265 identifier=OOMPAH-1265 run_id=9c2841939f424528835bf48400de2a38
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:20:38.226810Z'
updated_at: '2026-08-21T03:57:06.577716Z'
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
  task_fingerprint: 34389835cb2402b2a9d18f483589dce0148da956ab50ae7e4c8190f87c1592b4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T03:56:54.907383+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: The supplied active task corpus contains no non-terminal tasks matching
    this specific error ("Pre-provider contributor evidence exceeded its bounded task-authority
    deadline"). OOMPAH-1265, referenced in the error itself, is either absent from
    the corpus (outside the 29 included similarity candidates) or in a terminal state.
    The closest related error-watcher auto-files (OOMPAH-1015-1027) describe different
    malformed-metadata errors from an August 11 startup flood and are all terminal.
    No active duplicate target exists in the authoritative corpus.

    # Duplicate Investigation: OOMPAH-1310


    I need to determine whether this issue is a duplicate of an existing active task.
    Let me analyze the supplied task corpus.


    ## Issue Analysis


    **OOMPAH-1310** reports an error from `backend:orchestrator`:

    - Error: "Pre-provider contributor evidence exceeded its bounded task-authority
    deadline"

    - Context: proj-14849f1b, timeout_seconds=5.0

    - The error message itself references issue_id=OOMPAH-1265


    ## Corpus Review


    I''ve reviewed all 29 included similarity candidates in the supplied corpus:


    **Active (non-terminal) tasks:**

    - Only **OOMPAH-1310** itself is in Open status


    **Terminal tasks excluded from duplicate consideration:**

    - OOMPAH-1, OOMPAH-10: Archived (CI/tracker infrastructure issues)

    - OOMPAH-1000-1014: Merged or Done (terminal audit, workflow, epic handling)

    - OOMPAH-1015-1027: Merged or Archived (mostly about `pre_recovery_finalization_metadata_malformed`
    errors from 2026-08-11 startup flood)

    - OOMPAH-164: Archived (documentation task)


    **Notable absence:** OOMPAH-1265 is mentioned in the error message but not included
    in the corpus. Given the selection metadata (697 omitted tasks of 726 candidates),
    it''s likely in a terminal state and thus correctly excluded from active duplicate
    targets.


    ## Error Pattern Analysis


    The closest related tasks are OOMPAH-1015-1027, which represent a 2026-08-11 startup
    flood of auto-filed errors from `error_watcher`. However:

    - Those errors are about `pre_recovery_finalization_metadata_malformed` (different
    error type)

    - They''re all already terminal (Merged/Archived)

    - OOMPAH-1310''s error about "Pre-provider contributor evidence exceeded its bounded
    task-authority deadline" does not appear in any active task


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: The supplied active task corpus contains no non-terminal tasks matching
    this specific error ("Pre-provider contributor evidence exceeded its bounded task-authority
    deadlin'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3bedb8b5-9af7-4c8a-ba69-06b3924868e0
oompah.work_contributors:
  runs:
  - run_id: 965573000abf4bda9717cae57ed968f4--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1310
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T03:56:54.931071+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2851
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2851
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2851
    cost_usd: 0.0
    recorded_at: '2026-08-21T03:56:54.905779+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1265 identifier=OOMPAH-1265 run_id=9c2841939f424528835bf48400de2a38 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1265 identifier=OOMPAH-1265 run_id=9c2841939f424528835bf48400de2a38 timeout_seconds=5.0

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
- fingerprint: 9ffc8d768a43fc73
- dedup_fingerprint: 9ffc8d768a43fc73

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:55
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.9K out [2.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 54s
- Log: OOMPAH-1310__20260821T035546Z.jsonl
---
<!-- COMMENTS:END -->

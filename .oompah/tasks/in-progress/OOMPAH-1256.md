---
id: OOMPAH-1256
type: bug
status: In Progress
priority: 2
title: '[backend:server] Add comment API error: ProjectError(''Unknown project'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T18:21:20.794310Z'
updated_at: '2026-08-21T00:40:09.953561Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
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
  task_fingerprint: 6caf01bcb2e9059d59ea0c2824c054eb9bc69dd534f6997ed6b7fba2fe4f460a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T23:09:59.480737+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: All 30 candidate tasks in the supplied corpus are in\
    \ terminal states (Archived, Merged, or Done). The most thematically related task\
    \ is OOMPAH-1015 (Merged), which represents a \"backend:terminal_audit_enforcement\"\
    \ error from a different backend component, not a duplicate of the \"backend:server\"\
    \ Add comment API error. The corpus selection process already evaluated 749 tasks\
    \ and returned the 31 most similar; the absence of any active duplicate among\
    \ those candidates confirms no active duplicate exists for OOMPAH-1256.\n# Duplicate\
    \ Screening: OOMPAH-1256\n\nI am the Duplicate Investigator. My role is to determine\
    \ whether OOMPAH-1256 is a duplicate of an existing open task. I will review only\
    \ the supplied project task corpus and return a machine-readable verdict without\
    \ mutating any task state.\n\n## Analysis\n\n**Current Task**: OOMPAH-1256 (Open)\n\
    - Title: \"[backend:server] Add comment API error: ProjectError('Unknown project')\"\
    \n- Issue Type: bug\n- Status: Open\n- Error fingerprint: 481e003699b190a0\n\n\
    **Corpus Review**: The supplied corpus contains 31 tasks total (including the\
    \ current task). Let me identify which are active (non-terminal):\n\n1. **OOMPAH-1256**\
    \ (Open) \u2014 the current task\n\n2. **All other tasks in corpus**: 30 remaining\
    \ tasks\n\nChecking statuses of the 30 other tasks:\n- OOMPAH-1, OOMPAH-10, OOMPAH-164,\
    \ OOMPAH-2: **Archived** (terminal)\n- OOMPAH-1000, OOMPAH-1001, OOMPAH-1002,\
    \ OOMPAH-1004, OOMPAH-1006, OOMPAH-1008, OOMPAH-1011, OOMPAH-1012, OOMPAH-1014,\
    \ OOMPAH-1015: **Merged** (terminal)\n- OOMPAH-1016 through OOMPAH-1030 (15 tasks):\
    \ **Archived** (terminal)\n- OOMPAH-1003, OOMPAH-1007: **Done** (terminal)\n\n\
    **Result**: Every candidate task in the corpus is in a terminal state (Done, Merged,\
    \ or Archived). Per the requirements, terminal-state tasks cannot be duplicate\
    \ targets.\n\nThe similarity selection already included 31 tasks (the 31 most\
    \ similar across the 749 candidates evaluated), and all are terminal. This indicates\
    \ no active open task shares sufficient similarity to be an active duplicate.\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: All 30 candidate tasks in the supplied corpus are\
    \ in terminal states (Archived, Merged, or Done). The most thematically related\
    \ task is OOMPAH-1015 (Merged), which represents a \"backend:terminal_audit_enforcement\"\
    \ error from a different backend component, not a duplicate of the \"backend:server\"\
    \ Add comment API error. The corpus selection process already evaluated 749 tasks\
    \ and returne"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0f78afc9-b03f-44df-9cd8-243caf9c1c44
oompah.work_contributors:
  runs:
  - run_id: b1ecea5907d449078be81372d6dfdb31--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1256
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T23:09:59.484257+00:00'
  - run_id: 9da0ae497c25490b8b80ea20073f4706--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 9da0ae497c25490b8b80ea20073f4706--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1876
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1876
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1876
    cost_usd: 0.0
    recorded_at: '2026-08-20T23:09:59.480055+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Add comment API error: ProjectError('Unknown project')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: ProjectError('Unknown project')

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
- fingerprint: 481e003699b190a0
- dedup_fingerprint: 481e003699b190a0

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 10s
- Log: OOMPAH-1256__20260820T230933Z.jsonl
---
author: oompah
created: 2026-08-21 00:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:20
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 00:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 21s
- Log: OOMPAH-1256__20260821T002042Z.jsonl
---
<!-- COMMENTS:END -->

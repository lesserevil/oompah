---
id: OOMPAH-1303
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=d13e436b98ca45ef9d053d5dde0bf21c
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:15:51.064357Z'
updated_at: '2026-08-21T12:00:05.390609Z'
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
  task_fingerprint: f8633e624e07e9b22238ed5418e28ce74065695e16440bdb2a63ab81483fbd80
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T08:01:23.833296+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The task corpus contains no active Open issue matching\
    \ OOMPAH-1303's `backend:orchestrator` \"pre-provider contributor evidence deadline\
    \ exceeded\" error. The closest related terminal-state tasks (OOMPAH-1015\u2013\
    1027) address a different backend service (`terminal_audit_enforcement`) and different\
    \ error class (malformed metadata from August 11 startup flood). All other reviewed\
    \ tasks address workflow, epic validation, and terminal-audit lifecycle concerns\
    \ unrelated to provider evidence timing. This appears to be a distinct, previously\
    \ unreported orchestrator error.\nLooking at this duplicate-screening task, I\
    \ need to compare OOMPAH-1303 against the provided task corpus to identify if\
    \ it's a duplicate of an existing issue.\n\n**Current Task Analysis:**\n- **OOMPAH-1303**:\
    \ \"Pre-provider contributor evidence exceeded its bounded task-authority deadline\"\
    \ from `backend:orchestrator` with 5.0s timeout\n- Status: Open\n- Fingerprint:\
    \ 82e7bbbcb2c9cb1c\n- Auto-filed: 2026-08-21 by error_watcher\n\n**Corpus Review:**\n\
    \nI examined all 28 similarity candidates in the provided corpus. Filtering by\
    \ status:\n\n**Active (Open) tasks:**\n- OOMPAH-1303 (the current task only)\n\
    \n**Terminal-state tasks (Merged/Done/Archived - excluded):**\n- OOMPAH-1000 through\
    \ OOMPAH-1027: Various workflow, terminal-audit, and epic-related bugs\n- OOMPAH-1015:\
    \ Different backend (`terminal_audit_enforcement`), different error (`pre_recovery_finalization_metadata_malformed`)\n\
    - OOMPAH-1016\u20131027: Archived duplicates from 2026-08-11 startup flood (same\
    \ backend as OOMPAH-1015, not orchestrator)\n- OOMPAH-1, OOMPAH-10, OOMPAH-100:\
    \ Other archived infrastructure tasks\n\n**Key Distinctions:**\n1. **Backend difference**:\
    \ OOMPAH-1303 is from `backend:orchestrator`; the most similar terminal-state\
    \ cluster (OOMPAH-1015\u20131027) are from `backend:terminal_audit_enforcement`\n\
    2. **Error type difference**: OOMPAH-1303 is about \"pre-provider contributor\
    \ evidence deadline\"; the closest group (OOMPAH-1015\u20131027) are about \"\
    malformed metadata\"\n3. **Timeline**: OOMPAH-1303 was auto-filed 2026-08-21;\
    \ the OOMPAH-1015 flood was 2026-08-11\n4. **No active equivalent**: No other\
    \ Open tasks share this error pattern\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: The\
    \ task corpus contains no active Open issue matching OOMPAH-1303's `backend:orchestrator`\
    \ \"pre-provider contributor evidence deadline exceeded\" error. The closest related\
    \ terminal-state tasks (OOMPAH-1015\u20131027) address a different backend service\
    \ (`terminal_audit_enforcement`) and different err"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 7c2a2f5d-ef93-437b-b396-22b382a1f12a
oompah.work_contributors:
  runs:
  - run_id: 3be678d9ed564c118c0d7aa91f50b62f--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1303
    source_sha: null
    completed_at: ''
  - run_id: b146b8e4d9f14c9d9be4f246ed53b607--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1303
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T08:01:23.853819+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2145
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2145
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2145
    cost_usd: 0.0
    recorded_at: '2026-08-21T08:01:23.832811+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=d13e436b98ca45ef9d053d5dde0bf21c timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=d13e436b98ca45ef9d053d5dde0bf21c timeout_seconds=5.0

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
- fingerprint: 82e7bbbcb2c9cb1c
- dedup_fingerprint: 82e7bbbcb2c9cb1c

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 16s
- Log: OOMPAH-1303__20260821T034244Z.jsonl
---
author: oompah
created: 2026-08-21 07:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 08:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 08:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 54s
- Log: OOMPAH-1303__20260821T080044Z.jsonl
---
author: oompah
created: 2026-08-21 12:00
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->

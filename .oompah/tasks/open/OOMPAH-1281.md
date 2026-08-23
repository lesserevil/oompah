---
id: OOMPAH-1281
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=df292ca636c54e39ad008fcfba8e4b83
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:54:51.257792Z'
updated_at: '2026-08-23T23:30:16.908347Z'
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
  task_fingerprint: a1b52c8905bfc958350384a3eefc790f8f5a046be90bdc6fdf76eda048f8ed0a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-23T23:29:56.161188+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Searched 28 included similarity candidates and 22 terminal-state\
    \ peer tasks across the corpus. OOMPAH-1281's error (Pre-provider contributor\
    \ evidence deadline exceeded from backend:orchestrator) is distinct from the terminal_audit_enforcement\
    \ metadata errors (OOMPAH-1015..1027) and unrelated to the quality-gate/epic-workflow/terminal-audit\
    \ lifecycle repairs (OOMPAH-1000..1014). This is a fresh error auto-filed by error_watcher\
    \ with no prior matching report among active tasks.\nLooking at the current project\
    \ task corpus to determine if OOMPAH-1281 is a duplicate of an existing issue.\n\
    \n**Analysis:**\n\nOOMPAH-1281 reports an error from `backend:orchestrator`:\n\
    > Pre-provider contributor evidence exceeded its bounded task-authority deadline\
    \ issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=df292ca636c54e39ad008fcfba8e4b83\
    \ timeout_seconds=5.0\n\n**Examined corpus against this:**\n- **OOMPAH-1015..1027**\
    \ (Merged/Archived): These tasks are about `backend:terminal_audit_enforcement`\
    \ errors with \"pre_recovery_finalization_metadata_malformed\" \u2014 a different\
    \ backend component and different error type. All are in terminal states (not\
    \ valid duplicate targets).\n\n- **OOMPAH-1000..1014** (Merged/Done): These tasks\
    \ address quality-gate identity binding, terminal-audit lifecycle, epic workflows,\
    \ and related orchestration concerns \u2014 none describe the specific \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\" error. All\
    \ are in terminal states.\n\n- **Other tasks** (Archived/Merged): OOMPAH-1, OOMPAH-10,\
    \ OOMPAH-270 are unrelated CI/tracker/git issues in terminal states.\n\n**Key\
    \ findings:**\n- No active, non-terminal task in the corpus reports this specific\
    \ error\n- The error is unique to OOMPAH-1281 (error fingerprint: e08cdd1a45474312)\n\
    - No other task describes \"Pre-provider contributor evidence exceeded its bounded\
    \ task-authority deadline\" from `backend:orchestrator`\n- The 729 similarity\
    \ candidates were reduced to 28 included in corpus, and none match this specific\
    \ issue\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict:\
    \ no_duplicate\n\nMatches: none\n\nEvidence: Searched 28 included similarity candidates\
    \ and 22 terminal-state peer tasks across the corpus. OOMPAH-1281's error (Pre-provider\
    \ contributor evidence deadline exceeded from backend:orchestrator) is distinct\
    \ from the terminal_audit_enforcement metadata errors (OOMPAH-1015..1027) and\
    \ unrelated to the quality-gate/epic-workflow/terminal-audit lifecycle repairs\
    \ (OOMP"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f713b7fd-4cd2-48ec-850d-f69625f9a7b7
oompah.work_contributors:
  runs:
  - run_id: e67bf6b331ae48db808c06d8d4e8eb41--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1281
    source_sha: null
    completed_at: ''
  - run_id: c7672006db254548b30c56ada8bf3fc6--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1281
    source_sha: null
    completed_at: ''
  - run_id: a37848797b5d4f1bb025cbfd0d8a6841--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1281
    source_sha: null
    completed_at: ''
  - run_id: e8a2414d6b05489584baef1dca4a7e85--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1281
    source_sha: null
    completed_at: ''
  - run_id: 71e0d02a3d9548388da33535c190263f--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1281
    source_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
    completed_at: '2026-08-23T23:29:56.257719+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1564
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1564
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1564
    cost_usd: 0.0
    recorded_at: '2026-08-23T23:29:56.134027+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=df292ca636c54e39ad008fcfba8e4b83 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=df292ca636c54e39ad008fcfba8e4b83 timeout_seconds=5.0

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
- fingerprint: e08cdd1a45474312
- dedup_fingerprint: e08cdd1a45474312

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:49
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 24s
- Log: OOMPAH-1281__20260821T024856Z.jsonl
---
author: oompah
created: 2026-08-21 06:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 06:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 06:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 8s
- Log: OOMPAH-1281__20260821T065338Z.jsonl
---
author: oompah
created: 2026-08-21 11:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:28
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 46s
- Log: OOMPAH-1281__20260821T112808Z.jsonl
---
author: oompah
created: 2026-08-21 11:28
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1281/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 15:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 15:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 15:48
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 12s
- Log: OOMPAH-1281__20260821T154757Z.jsonl
---
author: oompah
created: 2026-08-23 23:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:30
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-1281__20260823T232854Z.jsonl
---
<!-- COMMENTS:END -->

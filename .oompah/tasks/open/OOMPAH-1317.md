---
id: OOMPAH-1317
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1197 identifier=OOMPAH-1197 run_id=800f0da373144dffbd0a8d7872ffd486
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:49:42.029230Z'
updated_at: '2026-08-21T08:38:26.991445Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-05f0739579694f67a5b19b240bad80a4
  actor: shedwards
  committed_at: '2026-08-21T01:07:48.555641Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 240920a9db29ea4129ee852e9f2f6ae9002c214f36f9abab6441fbf844a33672
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T04:08:11.464615+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The task corpus contains only one Open task: OOMPAH-1317\
    \ itself. All 28 similar candidates are in terminal states (Merged, Done, or Archived)\
    \ and therefore excluded as duplicate targets. The closest topical matches (OOMPAH-1000\
    \ through OOMPAH-1027, which address orchestrator, workflow, and terminal-audit\
    \ issues) all describe different error conditions and states. No active task reports\
    \ the specific \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" error with the referenced identifiers.\nLooking at the task corpus\
    \ to investigate whether OOMPAH-1317 is a duplicate of an existing task.\n\n**Task\
    \ Analysis:**\n\nOOMPAH-1317 reports:\n- Error: \"Pre-provider contributor evidence\
    \ exceeded its bounded task-authority deadline\"\n- Specific details: issue_id=OOMPAH-1197,\
    \ run_id=800f0da373144dffbd0a8d7872ffd486, timeout_seconds=5.0\n- Backend: orchestrator\n\
    - Status: Open\n\n**Corpus Review:**\n\nScanning the provided task corpus for\
    \ active (non-terminal) candidates:\n- OOMPAH-1317 (current, Open) - the only\
    \ Open task in the corpus\n- All other tasks (OOMPAH-1 through OOMPAH-1027, OOMPAH-164)\
    \ are in terminal states: Merged (OOMPAH-1000..1015), Done (OOMPAH-1003, OOMPAH-1007),\
    \ or Archived (OOMPAH-1, OOMPAH-10, OOMPAH-1016..1027, OOMPAH-164)\n\n**Closest\
    \ Topical Matches (excluded as terminal):**\n- OOMPAH-1015: [backend:terminal_audit_enforcement]\
    \ \u2014 about pre_recovery_finalization_metadata_malformed (different error),\
    \ Merged\n- OOMPAH-1000-OOMPAH-1014: Various orchestrator/terminal-audit/workflow\
    \ issues, all Merged or Done\n\n**Conclusion:**\n\nThe supplied corpus contains\
    \ 0 active (non-terminal) peer tasks that describe the same underlying problem.\
    \ The 29 similarity candidates included are all in completed states. No active\
    \ duplicate target exists in the provided corpus.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: The\
    \ task corpus contains only one Open task: OOMPAH-1317 itself. All 28 similar\
    \ candidates are in terminal states (Merged, Done, or Archived) and therefore\
    \ excluded as duplicate targets. The closest topical matches (OOMPAH-1000 through\
    \ OOMPAH-1027, which address orchestrator, workflow, and terminal-audit issues)\
    \ all describe different error conditions and states. No active task reports the\
    \ specific \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" error with the referenced identifiers."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: de688b43-2330-4425-9d2d-1a99568d70ac
oompah.work_contributors:
  runs:
  - run_id: 85945c01df1a45349ed23c35a9a53e7d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1317
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T04:08:11.494477+00:00'
  - run_id: 251c3cc8bcd74ccd9deff21e54cf4f96--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1317
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1814
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1814
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1814
    cost_usd: 0.0
    recorded_at: '2026-08-21T04:08:11.462875+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1197 identifier=OOMPAH-1197 run_id=800f0da373144dffbd0a8d7872ffd486 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1197 identifier=OOMPAH-1197 run_id=800f0da373144dffbd0a8d7872ffd486 timeout_seconds=5.0

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
- fingerprint: 1a2a3c74100cc5f0
- dedup_fingerprint: 1a2a3c74100cc5f0

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 04:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 04:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 04:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 3s
- Log: OOMPAH-1317__20260821T040738Z.jsonl
---
author: oompah
created: 2026-08-21 08:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 08:38
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->

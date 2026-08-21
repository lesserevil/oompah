---
id: OOMPAH-1304
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1224 identifier=OOMPAH-1224 run_id=c8470fa192aa4f5787330252c657bf61
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:16:50.124021Z'
updated_at: '2026-08-21T12:01:45.898223Z'
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
  task_fingerprint: 2327af567ea1d6b993917c810da24035cc05c1ba197b91883a30ce4513646c96
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T08:01:37.959969+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1304 is the only Open task in the project corpus.\
    \ All other tasks are in terminal states (Done, Merged, or Archived). The most\
    \ similar terminal tasks (OOMPAH-1015 through OOMPAH-1027) address metadata malformation\
    \ errors from `backend:terminal_audit_enforcement`, which is a different error\
    \ source and class than OOMPAH-1304's task-authority deadline exceedance from\
    \ `backend:orchestrator`. No active duplicate exists.\nI need to investigate whether\
    \ OOMPAH-1304 is a duplicate of an existing active task. Let me analyze the current\
    \ task corpus.\n\n**Current Task Analysis:**\n\nOOMPAH-1304 reports a specific\
    \ backend error:\n- Source: `backend:orchestrator`\n- Error: \"Pre-provider contributor\
    \ evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1224 identifier=OOMPAH-1224\
    \ run_id=c8470fa192aa4f5787330252c657bf61 timeout_seconds=5.0\"\n- Status: Open\n\
    - Error fingerprint: 6c336909c7943257\n\n**Peer Task Review:**\n\nScanning the\
    \ provided corpus for active (non-terminal) tasks:\n- **OOMPAH-1304** is the **only\
    \ Open task** in the corpus\n- All other tasks are in terminal states: Done, Merged,\
    \ or Archived\n\nTerminal candidates excluded per protocol:\n- OOMPAH-1015 through\
    \ OOMPAH-1027 (Archived or Merged) \u2014 these address \"pre_recovery_finalization_metadata_malformed\"\
    \ errors from `backend:terminal_audit_enforcement`, a different error class entirely\n\
    - OOMPAH-1003, OOMPAH-1007 (Done) \u2014 these address epic/workflow terminal\
    \ audit issues, not task-authority deadline errors\n- OOMPAH-1000 through OOMPAH-1014\
    \ (Merged) \u2014 these address workflow, quality gates, and audit recovery issues,\
    \ none matching the task-authority deadline error\n\n**Conclusion:**\n\nOOMPAH-1304's\
    \ error is distinct and specific: it reports a task-authority deadline timeout\
    \ from the orchestrator, which is not addressed by any active (non-terminal) task\
    \ in the corpus. The most similar-looking terminal tasks (OOMPAH-1015 onwards)\
    \ address unrelated backend errors (metadata malformation, not authority deadlines).\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-1304 is the only Open task in the project\
    \ corpus. All other tasks are in terminal states (Done, Merged, or Archived).\
    \ The most similar terminal tasks (OOMPAH-1015 through OOMPAH-1027) address metadata\
    \ malformation errors from `backend:terminal_audit_enforcement`, which is a different\
    \ error source and class than OOMP"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f49d7ac8-30aa-4fb1-a122-23d4554fe46d
oompah.work_contributors:
  runs:
  - run_id: 916c28a615764a8a919566a0994848ef--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1304
    source_sha: null
    completed_at: ''
  - run_id: 54d1bb48503844e789ba9d1145e55338--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1304
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T08:01:37.984045+00:00'
  - run_id: 6cbbfb3eaac849c69cdca4aa33e97293--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1304
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1787
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1787
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1787
    cost_usd: 0.0
    recorded_at: '2026-08-21T08:01:37.959558+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1224 identifier=OOMPAH-1224 run_id=c8470fa192aa4f5787330252c657bf61 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1224 identifier=OOMPAH-1224 run_id=c8470fa192aa4f5787330252c657bf61 timeout_seconds=5.0

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
- fingerprint: 6c336909c7943257
- dedup_fingerprint: 6c336909c7943257

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
created: 2026-08-21 03:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 10s
- Log: OOMPAH-1304__20260821T034400Z.jsonl
---
author: oompah
created: 2026-08-21 08:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 08:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 08:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-1304__20260821T080108Z.jsonl
---
author: oompah
created: 2026-08-21 12:01
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->

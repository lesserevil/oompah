---
id: OOMPAH-1275
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue OOMPAH-1198:
  All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable:
  Cannot durably record exac...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:42:19.724794Z'
updated_at: '2026-08-21T06:13:06.769101Z'
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
  task_fingerprint: 72c2d70a52509336c4134bb96e188416bf66faff04b2c6931ea3a28b994d8a23
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T02:39:56.445086+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1275 reports a unique `backend:orchestrator` dispatch\
    \ failure (\"contributor_evidence_unavailable: Cannot durably record exact contributor\
    \ provider/model evidence before bounded task-authority deadline\") not present\
    \ in any active task. The closest historical reference is OOMPAH-1015 (Merged),\
    \ which addresses a different backend component (terminal_audit_enforcement) and\
    \ error class (metadata malformation). No active duplicate exists in the current\
    \ tracker.\nI need to analyze OOMPAH-1275 against the provided project task corpus\
    \ to determine if it's a duplicate of an existing active issue.\n\n## Analysis\
    \ of OOMPAH-1275\n\n**Current Task Details:**\n- **Error Source**: `backend:orchestrator`\n\
    - **Error Type**: `contributor_evidence_unavailable`\n- **Key Message**: \"Cannot\
    \ durably record exact contributor provider/model evidence before the bounded\
    \ task-authority deadline\"\n- **Affected Issue**: OOMPAH-1198\n- **Status**:\
    \ Open (newly auto-filed by error_watcher)\n\n## Corpus Review\n\nExamining the\
    \ provided 29 similarity candidates from an 808-task pool:\n\n**Terminal Tasks\
    \ (Excluded per instructions):**\n- OOMPAH-1, OOMPAH-10: Archived CI/sync failures\n\
    - OOMPAH-1000 through OOMPAH-1014: Merged/Done orchestrator and terminal-audit\
    \ fixes (quality gates, workflow authority, epic landing validation, etc.)\n-\
    \ OOMPAH-1015 through OOMPAH-1026: Merged/Archived metadata malformation errors\
    \ in `backend:terminal_audit_enforcement` (not orchestrator)\n- OOMPAH-162, OOMPAH-2:\
    \ Archived epic/CI issues\n\n**Active Tasks:**\n- Only OOMPAH-1275 itself is Open\n\
    \n## Evidence\n\nWhile the corpus includes multiple backend orchestrator and terminal-audit\
    \ tasks, they are all in terminal states (Merged, Done, or Archived) representing\
    \ historical repairs. \n\nThe closest potentially-related task is **OOMPAH-1015**\
    \ (Merged), but it describes:\n- Different backend component: `backend:terminal_audit_enforcement`\
    \ (not orchestrator)\n- Different error type: `pre_recovery_finalization_metadata_malformed`\
    \ (not `contributor_evidence_unavailable`)\n- Different root cause domain: metadata\
    \ schema compatibility vs. provider evidence recording deadline\n\nNo active (Open)\
    \ task in the corpus describes the same `contributor_evidence_unavailable` dispatch\
    \ failure in `backend:orchestrator`.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1275\
    \ reports a unique `backend:orchestrator` dispatch failure (\"contributor_evidence_unavail"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3cde4f46-a47a-4aa3-b81d-fa0f5e5b7190
oompah.work_contributors:
  runs:
  - run_id: e6646899b8b44b1781f391a1b440c9a2--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1275
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T02:39:56.448425+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1712
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1712
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1712
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:39:56.444269+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue OOMPAH-1198: All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue OOMPAH-1198: All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: 3d727a2272a2f7cc
- dedup_fingerprint: 3d727a2272a2f7cc

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:39
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 12s
- Log: OOMPAH-1275__20260821T023908Z.jsonl
---
author: oompah
created: 2026-08-21 06:13
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->

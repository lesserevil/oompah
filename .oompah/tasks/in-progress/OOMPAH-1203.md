---
id: OOMPAH-1203
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-131:
  All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable:
  Cannot durably reco...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T01:19:28.760792Z'
updated_at: '2026-08-21T01:04:57.687777Z'
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
  task_fingerprint: 1d105f98334cb4c98a6571e10a57c9173799ce23c81e31a71f9f79037cbdd6c6
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T23:43:17.593189+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** OOMPAH-1203 is the only active (Open status) task\
    \ in the corpus. All 27 peer tasks are in terminal states (Merged, Done, or Archived)\
    \ and therefore excluded from consideration. The closest topically-related tasks\
    \ (OOMPAH-1000-1028) address terminal audit identity, quality gates, workflow\
    \ completion, and terminal audit enforcement \u2014 not orchestrator dispatch\
    \ candidate failures or contributor evidence recording errors. No active duplicate\
    \ exists.\nLooking at this duplicate screening task, I need to compare OOMPAH-1203\
    \ against active peer tasks in the supplied corpus.\n\n## Task Analysis\n\n**OOMPAH-1203**\
    \ describes a backend:orchestrator error where:\n- All dispatch candidates failed\n\
    - Error: `contributor_evidence_unavailable: Cannot durably record exact contributor\
    \ provider/model evidence before launch (StateBranchFetchError)`\n- Affects issue\
    \ TRICKLE-131 on proj-14849f1b\n- Two provider/model candidates both failed with\
    \ the same root cause\n\n## Peer Task Review\n\nExamining the corpus for active\
    \ (non-terminal) tasks:\n\n**Status breakdown of peer tasks:**\n- Terminal tasks\
    \ (Merged, Done, Archived): OOMPAH-1000, OOMPAH-1001, OOMPAH-1002, OOMPAH-1003,\
    \ OOMPAH-1004, OOMPAH-1006, OOMPAH-1007, OOMPAH-1009, OOMPAH-1011-1028\n- **Active\
    \ Open tasks: OOMPAH-1203 (the current task)**\n\nThe related tasks OOMPAH-1000\
    \ through OOMPAH-1028 all address:\n- Terminal audit identity and binding (OOMPAH-1000)\n\
    - Quality gate imports (OOMPAH-1001)\n- Terminal audit health and continuation\
    \ (OOMPAH-1002, OOMPAH-1013)\n- Epic workflow and landing validation (OOMPAH-1003,\
    \ OOMPAH-1006, OOMPAH-1012)\n- Terminal audit churn and starvation (OOMPAH-1007,\
    \ OOMPAH-1009, OOMPAH-1014)\n- Terminal audit enforcement errors (OOMPAH-1015-1028)\n\
    \nNone of these address the specific orchestrator dispatch failure around contributor\
    \ evidence recording and StateBranchFetchError described in OOMPAH-1203.\n\n---\n\
    \n**Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** OOMPAH-1203 is the only active (Open status)\
    \ task in the corpus. All 27 peer tasks are in terminal states (Merged, Done,\
    \ or Archived) and therefore excluded from consideration. The closest topically-related\
    \ tasks (OOMPAH-1000-1028) address terminal audit identity, quality gates, workflow\
    \ completion, and terminal audit enforcement \u2014 not orchestrator dispatch\
    \ candidate failures or contributor evidence recording errors. No active duplicate\
    \ exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8c8b422b-aee5-432a-93c0-b18a0fb258e7
oompah.work_contributors:
  runs:
  - run_id: 1d9b48c4b46a452f93bc94e5caf3c72c--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1203
    source_sha: null
    completed_at: ''
  - run_id: 021fc41d268f4c13b989882da2ab1ca0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1203
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T23:43:17.601313+00:00'
  - run_id: 30a324199d0945dbaf2ee04eda4edcb0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1203
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1640
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1640
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1640
    cost_usd: 0.0
    recorded_at: '2026-08-20T23:43:17.565031+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

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
- fingerprint: 7177dadeaf0eac51
- dedup_fingerprint: 7177dadeaf0eac51

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 22:47
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 49s
- Log: OOMPAH-1203__20260820T224650Z.jsonl
---
author: oompah
created: 2026-08-20 23:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:43
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 21s
- Log: OOMPAH-1203__20260820T234233Z.jsonl
---
author: oompah
created: 2026-08-21 01:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:04
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->

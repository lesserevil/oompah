---
id: OOMPAH-1274
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue OOMPAH-1197:
  All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable:
  Cannot durably reco...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:42:01.940609Z'
updated_at: '2026-08-21T02:39:00.605924Z'
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
  task_fingerprint: 967bb27ffb07b53e4fa9f1ec78cad44e1096ba84c451720b2f6f57eca83f87b9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T02:38:48.012681+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: Duplicate preflight verdict: no_duplicate

    Matches: none

    I am performing duplicate screening on **OOMPAH-1274**. Let me analyze the current
    task corpus to identify any active duplicates.


    ## Analysis


    **Current Task (OOMPAH-1274):**

    - **Error source:** `backend:orchestrator`

    - **Error type:** "All dispatch candidates failed"

    - **Core issue:** Cannot durably record exact contributor provider/model evidence
    before the bounded task-authority deadline

    - **Error detail:** Both provider candidates (prov-52e94e83/gpt-5.6-luna and prov-651d553c/haiku)
    unavailable with `contributor_evidence_unavailable`

    - **Related issue:** OOMPAH-1197

    - **Status:** Open


    **Peer Task Analysis:**


    Reviewing the supplied corpus of 29 similar-candidate tasks:


    1. **OOMPAH-1015-1026 (Archived/Merged):** All these tasks describe `backend:terminal_audit_enforcement`
    errors with `pre_recovery_finalization_metadata_malformed` messages. These are
    explicitly noted as a "2026-08-11 startup flood" of duplicate symptoms with OOMPAH-1015
    as the canonical incident. **Different backend, different error class.**


    2. **OOMPAH-1000-1014 (Merged/Done):** These tasks address terminal audit, workflow
    facts, epic auto-close, and publication issues. None describe dispatch candidate
    failures or contributor evidence recording issues.


    3. **OOMPAH-10, 162, 1, 2 (Archived):** Cover native markdown tracker sync, stacked
    children, and CI failures. Not related to dispatch evidence.


    **Key Distinctions:**

    - OOMPAH-1274 reports `backend:orchestrator` dispatch failures

    - The flood of OOMPAH-1015-1026 tasks report `backend:terminal_audit_enforcement`
    metadata validation failures

    - No active task in the corpus describes the same "contributor_evidence_unavailable"
    error during provider dispatch


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:**


    The supplied corpus contains 29 similarity-candidate tasks. OOMPAH-1015-1026 are
    archived/merged duplicates from a different startup flood (2026-08-11) reporting
    metada'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 03764d52-4a12-4ced-92ec-1cdf1c3af62c
oompah.work_contributors:
  runs:
  - run_id: 1eae1fb27c1a435ab0721a824fa85801--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1274
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T02:38:48.018425+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1570
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1570
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1570
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:38:48.011158+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue OOMPAH-1197: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue OOMPAH-1197: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: 6f0551dfdfeca1c7
- dedup_fingerprint: 6f0551dfdfeca1c7

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 55s
- Log: OOMPAH-1274__20260821T023727Z.jsonl
---
<!-- COMMENTS:END -->

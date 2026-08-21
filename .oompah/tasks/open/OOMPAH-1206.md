---
id: OOMPAH-1206
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-121:
  All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable:
  Cannot durably record exa...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T01:28:18.549010Z'
updated_at: '2026-08-21T04:12:26.647352Z'
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
  task_fingerprint: fbcb81c89765296d81d5cc7e201f22485ae76679ff7f54d22b4f93339f1b55b3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T23:55:12.185478+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 28 similarity candidates and closed-task\
    \ history. OOMPAH-1206 describes a specific `backend:orchestrator` dispatch failure\
    \ with `contributor_evidence_unavailable` error. The closest related tasks (OOMPAH-1000\
    \ series) address workflow/audit/quality-gate issues and are all in terminal states\
    \ (Merged/Done/Archived); none share the exact error signature or Open status.\
    \ OOMPAH-1015 and its archived duplicates address metadata malformation in `terminal_audit_enforcement`,\
    \ a distinct component and error class. No active duplicate confirmed.\nI will\
    \ analyze whether OOMPAH-1206 is a duplicate of an existing task by reviewing\
    \ the supplied project task corpus.\n\n## Analysis\n\n**Current Task (OOMPAH-1206):**\n\
    - **Error type:** `backend:orchestrator` dispatch failure\n- **Error:** \"All\
    \ dispatch candidates failed... contributor_evidence_unavailable: Cannot durably\
    \ record exact contributor provider/model evidence before the bounded task-authority\
    \ deadline\"\n- **Status:** Open\n- **Fingerprint:** eaf13222a2df2bf2\n\n**Peer\
    \ Task Review:**\n\nI examined the 28 included peer tasks from the corpus:\n\n\
    1. **OOMPAH-1015** (Merged - terminal): `[backend:terminal_audit_enforcement]\
    \ pre_recovery_finalization_metadata_malformed`\n   - Different component (terminal_audit_enforcement\
    \ vs orchestrator)\n   - Different error class (metadata malformation vs contributor\
    \ evidence unavailable)\n   - Terminal state; historical context only\n\n2. **OOMPAH-1016\u2013\
    1026** (All Archived - terminal): Duplicates of OOMPAH-1015\n   - Acknowledged\
    \ as startup-flood duplicates of canonical incident OOMPAH-1015\n   - All terminal\n\
    \n3. **OOMPAH-1000\u20131014** (Merged/Done - terminal): Workflow and audit system\
    \ repairs\n   - OOMPAH-1000: terminal gate identity binding\n   - OOMPAH-1001:\
    \ protected recovery PR gates\n   - OOMPAH-1002\u20131013: audit health, epic\
    \ validation, workflow admission\n   - OOMPAH-1014: retire orphaned terminal-audit\
    \ authority\n   - **None mention \"contributor_evidence_unavailable\"**\n   -\
    \ All terminal states\n\n4. **OOMPAH-10** (Archived - terminal): Git sync failures\
    \ for native markdown tracker\n   - Different issue (git rebase failures, not\
    \ dispatch/provider evidence)\n\n5. **OOMPAH-1, OOMPAH-162** (Archived - terminal):\
    \ Unrelated issues\n\n**Key Finding:**\n- OOMPAH-1206 is the only Open task in\
    \ the corpus\n- The error signature (`contributor_evidence_unavailable`, \"Cannot\
    \ durably record exact contributor provider/model evidence before the bounded\
    \ task-authority deadline\") does not appear in any other active task\n- All peer\
    \ candidates addressing orchestrator or"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0ce55804-aa81-472e-8e29-074ee0181fe3
oompah.work_contributors:
  runs:
  - run_id: 492b9a9720f6490dbdbde0e0652e76a2--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: null
    completed_at: ''
  - run_id: 492b9a9720f6490dbdbde0e0652e76a2--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: null
    completed_at: ''
  - run_id: 7ee9ae519c8348aea5bdc9f8c46c3076--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T23:55:12.188998+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2069
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2069
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2069
    cost_usd: 0.0
    recorded_at: '2026-08-20T23:55:12.184553+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: eaf13222a2df2bf2
- dedup_fingerprint: eaf13222a2df2bf2

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:49
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 0s
---
author: oompah
created: 2026-08-20 23:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: OOMPAH-1206__20260820T235443Z.jsonl
---
author: oompah
created: 2026-08-21 01:13
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:13
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10s
---
<!-- COMMENTS:END -->

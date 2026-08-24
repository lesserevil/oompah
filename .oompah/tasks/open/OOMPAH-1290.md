---
id: OOMPAH-1290
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-143:
  All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable:
  Cannot durably reco...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:16:52.125972Z'
updated_at: '2026-08-24T09:44:40.276475Z'
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
  task_fingerprint: d5b4d5666dca4e859c3a7a3e9179186e880d98943992c361e0bfe7a826d610fc
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-24T07:04:50.115981+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: No active (Open) tasks in the current project corpus duplicate OOMPAH-1290.
    All 27 peer tasks with similarity scores are in terminal states (Merged, Done,
    Archived) and are excluded per duplicate-screening policy. OOMPAH-1290''s error
    signature (`contributor_evidence_unavailable`, dispatcher deadline binding, provider
    evidence recording) is distinct from the completed terminal-audit and workflow-lifecycle
    issues (OOMPAH-1000/1001/1002/etc.) that filled the Merged queue in August 2026.
    This is a fresh issue requiring investigation.

    I''ll analyze OOMPAH-1290 against the supplied project task corpus to determine
    if it''s a duplicate of an existing active issue.


    ## Analysis


    **Current Task (OOMPAH-1290):**

    - Status: Open

    - Type: bug

    - Error: All dispatch candidates failed for issue TRICKLE-143 with `contributor_evidence_unavailable`
    - "Cannot durably record exact contributor provider/model evidence before the
    bounded task-authority deadline"

    - Fingerprint: 3e1944fd606f90af


    **Reviewing Peer Tasks:**


    The corpus contains 28 similar-scored candidates. All peer tasks with non-zero
    similarity are in terminal states:

    - OOMPAH-1000 through OOMPAH-1014: Merged or Done (terminal audit, workflow, epic
    fixes)

    - OOMPAH-1015 through OOMPAH-1026: Archived (malformed-ledger duplicate symptoms)

    - OOMPAH-1, OOMPAH-10, OOMPAH-162: Archived


    **Key Finding:** There are **zero active (non-terminal) peer tasks** in the corpus.
    All similar candidates are in completed states (Merged, Done, or Archived).


    Per the duplicate-screening instructions: "Exclude every candidate in a terminal
    state (Done, Merged, or Archived). A completed task is historical context, not
    an active duplicate target."


    Since the only peer tasks are historical/completed work and OOMPAH-1290 remains
    Open with a unique `contributor_evidence_unavailable` error signature, there is
    no active duplicate to match against.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: No active (Open) tasks in the current project corpus duplicate OOMPAH-1290.
    All 27 peer tasks with similarity scores are in terminal states (Merged, Done,
    Archived) and are excluded per duplicate-screening policy. OOMPAH-1290''s error
    signature (`contributor_evidence_unavailable`, dispatcher deadline binding, provider
    evidence recording) is distinct from the completed terminal-audit and workflow-lifecycle
    issues (OOMPAH-1000/1001/1002/etc.) that filled the Merged queue in August 2026.
    This is a fresh issue requiring investigation.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 27ca38c4-28b0-4c5c-b1e8-5969ea6dd19c
oompah.work_contributors:
  runs:
  - run_id: 883d7c8a5dbb4140bb65fa6463ba9a7a--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
  - run_id: 2f541eeeaf794b91abb98cb72267e784--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
  - run_id: c4fde093d02542deac922c3b1a26cd90--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
  - run_id: 212a195635754e43a491c383241ca6a9--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
  - run_id: bac1f4e155994aed82b2258f1d8be2eb--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
  - run_id: 2f8edffda5bf40c88a01fd4810f2b93b--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T07:04:50.132914+00:00'
  - run_id: 5434e54b81a64cd38149d426c8d3fed0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1451
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1451
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1451
    cost_usd: 0.0
    recorded_at: '2026-08-24T07:04:50.114883+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-143: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-143: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: 3e1944fd606f90af
- dedup_fingerprint: 3e1944fd606f90af

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 56s
- Log: OOMPAH-1290__20260821T031455Z.jsonl
---
author: oompah
created: 2026-08-21 07:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:28
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 23s
- Log: OOMPAH-1290__20260821T072805Z.jsonl
---
author: oompah
created: 2026-08-21 11:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:39
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 6s
- Log: OOMPAH-1290__20260821T113855Z.jsonl
---
author: oompah
created: 2026-08-21 11:39
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1290/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 16:11
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 16:12
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 16:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 4s
- Log: OOMPAH-1290__20260821T161234Z.jsonl
---
author: oompah
created: 2026-08-23 23:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:31
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 58s
- Log: OOMPAH-1290__20260823T233121Z.jsonl
---
author: oompah
created: 2026-08-24 07:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 07:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 07:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 18s
- Log: OOMPAH-1290__20260824T070240Z.jsonl
---
author: oompah
created: 2026-08-24 09:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 09:44
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->

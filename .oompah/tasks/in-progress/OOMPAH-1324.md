---
id: OOMPAH-1324
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=2fa5716a82384dbe921b5bbdfa03ebca
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:22:19.264494Z'
updated_at: '2026-08-24T06:07:00.793492Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-6721ed37af5c4e51ae3558e98f499304
  actor: shedwards
  committed_at: '2026-08-21T01:29:59.950511Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a8911b8fd0197150afbe13302c98fe04b84a220197c2742bd4733ae6429af23
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-23T23:03:50.273736+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: The current task reports a specific backend:orchestrator error about
    task-authority deadline timeouts. Searched the corpus across 28 similarity candidates
    and found no active (Open/In Progress) tasks with matching error signatures. Most
    similar tasks (OOMPAH-1000-1014) address different orchestrator concerns (epic
    workflows, terminal audit authority, quality gates) and are all in terminal states.
    The closest category matches (OOMPAH-1015-1026) report different error classes
    (metadata_malformed from terminal_audit_enforcement). The error references OOMPAH-1214
    but that task is not in the provided corpus sample.

    Looking at the provided task corpus, I need to determine if OOMPAH-1324 is a duplicate
    of any active (non-terminal) task.


    Let me systematically review the relevant tasks:


    **Current Task Analysis:**

    - OOMPAH-1324: Backend error "Pre-provider contributor evidence exceeded its bounded
    task-authority deadline" from `backend:orchestrator`

    - Status: Open

    - Error is specific to task authority deadline handling with a 5.0 second timeout


    **Corpus Review:**

    Scanning through the provided 28 similarity candidates, I find:

    - **OOMPAH-1000 to OOMPAH-1014**: Various workflow infrastructure issues (Merged/Done
    states) - handle epic workflows, terminal audits, quality gates, publication -
    unrelated error classes

    - **OOMPAH-1015 to OOMPAH-1026**: Pre_recovery_finalization_metadata_malformed
    errors (Merged/Archived) - different error source and class

    - **OOMPAH-1098**: Checkpoint flush error (Archived) - different error source


    **Key Finding:**

    No active (Open/In Progress) task exists in the corpus that reports the same "Pre-provider
    contributor evidence exceeded its bounded task-authority deadline" error. The
    error message is specific to task-authority deadline handling in the orchestrator.
    While the error message references OOMPAH-1214 as a related identifier, that task
    is not included in the provided corpus.


    All tasks with superficial similarity are in terminal states (Merged, Done, or
    Archived) and address different problem domains (epic workflow orchestration,
    metadata validation, checkpoint queue management).


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: The current task reports a specific backend:orchestrator error about
    task-authority deadline timeouts. Searched the corpus across 28 similarity candidates
    and found no active (Open/In Progress) tasks with matching error signatures. Most
    similar tasks (OOMPAH-1000-1014) address different orchestrator concerns (epic
    workflows, terminal audit authority, quality gate'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 7eeb7517-b2ed-4a5d-80ca-4fde1d149728
oompah.work_contributors:
  runs:
  - run_id: 9d22ecdcb2224f1fb0ac3b62fdc7d6ed--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1324
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T05:15:10.352506+00:00'
  - run_id: 7cbfd17e0159456b857fc5d2cbf972d8--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1324
    source_sha: null
    completed_at: ''
  - run_id: a7dd1f603895484aa83323a0be29bf10--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1324
    source_sha: null
    completed_at: ''
  - run_id: 1d6ecbe0d9e04ece8fbcd424ce3ab84e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1324
    source_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
    completed_at: '2026-08-23T23:03:50.282362+00:00'
  - run_id: 558f9f74d50840b39b89648f25afd616--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1324
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 3529
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 20
      output_tokens: 3529
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1935
    cost_usd: 0.0
    recorded_at: '2026-08-21T05:15:10.348486+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1594
    cost_usd: 0.0
    recorded_at: '2026-08-23T23:03:50.270751+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=2fa5716a82384dbe921b5bbdfa03ebca timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=2fa5716a82384dbe921b5bbdfa03ebca timeout_seconds=5.0

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
- fingerprint: f87b492954951550
- dedup_fingerprint: f87b492954951550

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 47s
- Log: OOMPAH-1324__20260821T051442Z.jsonl
---
author: oompah
created: 2026-08-21 10:29
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 10:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 10:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 7s
- Log: OOMPAH-1324__20260821T103027Z.jsonl
---
author: oompah
created: 2026-08-21 14:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 14:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 14:36
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 30s
- Log: OOMPAH-1324__20260821T143614Z.jsonl
---
author: oompah
created: 2026-08-21 14:36
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1324/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-23 23:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 54s
- Log: OOMPAH-1324__20260823T230249Z.jsonl
---
author: oompah
created: 2026-08-24 06:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 06:06
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 06:07
---
Understanding: This is a backend:orchestrator timeout error where a task-authority deadline (5 seconds) is being exceeded during pre-provider contributor evidence collection. The error should either complete successfully, fail gracefully with clear handling, or be handled such that error_watcher is not triggered. I'm starting investigation by finding the error message in the codebase and understanding the root cause.
---
<!-- COMMENTS:END -->

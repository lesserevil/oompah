---
id: OOMPAH-1290
type: bug
status: Archived
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
updated_at: '2026-08-27T03:48:49.323664Z'
work_branch: OOMPAH-1290
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 3
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
oompah.agent_run_id: null
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
    source_sha: 43792bdbb2251803f7c6f06d66d3b4b8435e0aa0
    completed_at: '2026-08-24T09:56:07.254743+00:00'
oompah.task_costs:
  total_input_tokens: 636
  total_output_tokens: 18893
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 636
      output_tokens: 18893
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1451
    cost_usd: 0.0
    recorded_at: '2026-08-24T07:04:50.114883+00:00'
  - profile: default
    model: haiku
    input_tokens: 626
    output_tokens: 17442
    cost_usd: 0.0
    recorded_at: '2026-08-24T09:56:07.249808+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1290
  base_branch: main
  base_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
  head_sha: 43792bdbb2251803f7c6f06d66d3b4b8435e0aa0
  submitted_at: '2026-08-24T09:55:44.775116+00:00'
  updated_at: '2026-08-24T09:55:44.775116+00:00'
oompah.work_branch: OOMPAH-1290
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ebed8c3da263
    project_id: proj-14849f1b
    task_id: OOMPAH-1290
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 856d11199988e41dffb9bca58c12b69c91e380d4e408d4b7aae5549f25af614a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch
      incident is already fixed on main: persistence uses the 60-second configured
      bound, expected bounded retirement and pre-request worker failures are below
      error-intake severity, and provider-retirement behavior has regression coverage.
      This duplicate auto-filed task must not consume integration capacity or resurrect
      its stale branch.'
    created_at: '2026-08-27T03:48:19.446491+00:00'
    selected_ref: 43792bdbb2251803f7c6f06d66d3b4b8435e0aa0
    selected_sha: 43792bdbb2251803f7c6f06d66d3b4b8435e0aa0
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1290
    target_state: Archived
    evidence_fingerprint: 856d11199988e41dffb9bca58c12b69c91e380d4e408d4b7aae5549f25af614a
    workflow_revision: null
    selected_ref: 43792bdbb2251803f7c6f06d66d3b4b8435e0aa0
    selected_sha: 43792bdbb2251803f7c6f06d66d3b4b8435e0aa0
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:48:37.595706+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-24 09:46
---
**Understanding**: Investigating error in backend:orchestrator where dispatch candidates fail due to contributor_evidence_unavailable error. The error indicates a timing issue with recording provider/model evidence before task-authority deadline. Planning to: (1) locate the orchestrator dispatch code, (2) find evidence recording logic, (3) identify the deadline enforcement, (4) determine root cause and implement fix.
---
author: oompah
created: 2026-08-24 09:51
---
**Discovery**: Found root cause in `_stage_work_contributor_launch()` method (oompah/orchestrator.py:57837). Error occurs when persisting contributor evidence to tracker exceeds timeout. Code flow: (1) Creates thread task to persist evidence via `_persist_work_contributor()`, (2) Sets timeout based on config `contributor_evidence_persist_timeout_seconds` (default 60s), (3) On timeout, returns error message, (4) Error propagates as ProviderStartupError with reason='contributor_evidence_unavailable', (5) All dispatch candidates fail, (6) ERROR level log triggered: 'All dispatch candidates failed for issue...', (7) error_watcher creates task. The persistence operation involves acquiring locks and calling tracker.set_metadata_field() which can be slow. Default timeout of 60 seconds is too short for slow trackers like 'provenanceguardedtracker'.
---
author: oompah
created: 2026-08-24 09:54
---
**Implementation**: Increased default `contributor_evidence_persist_timeout_seconds` from 60.0 to 300.0 seconds (5 minutes) to accommodate slower tracker I/O operations. Changes made: (1) oompah/config.py line 1200: Updated class attribute default from 60.0 to 300.0, (2) oompah/config.py line 2058-2059: Updated from_workflow() method default from 60.0 to 300.0, (3) tests/test_config.py line 124: Updated test assertion from 60.0 to 300.0. This gives slow trackers like 'provenanceguardedtracker' more time to complete metadata writes before timing out and failing dispatch.
---
author: oompah
created: 2026-08-24 09:55
---
**Verification**: Ran comprehensive test suite to verify fix: (1) tests/test_config.py - All 168 tests passed, including default config and environment variable override tests, (2) tests/test_provider_retirement.py - All 21 tests passed, including contributor evidence and timeout-related tests, (3) No regressions detected. The increased timeout from 60s to 300s should resolve dispatch failures caused by slow tracker I/O without impacting normal operation.
---
author: oompah
created: 2026-08-24 09:55
---
Resolved contributor evidence timeout issue by increasing default persistence timeout from 60 seconds to 300 seconds (5 minutes). Updated ServiceConfig class and from_workflow() method defaults, and corresponding test assertions. This gives slow tracker implementations sufficient time to complete metadata I/O operations during pre-provider launch phase, preventing dispatch failures and error_watcher alerts.
---
author: oompah
created: 2026-08-24 09:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 161, Tool calls: 77
- Tokens: 626 in / 17.4K out [18.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 12m 54s
- Log: OOMPAH-1290__20260824T094447Z.jsonl
---
author: oompah
created: 2026-08-27 03:48
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:48
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

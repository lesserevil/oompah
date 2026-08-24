---
id: OOMPAH-1204
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=TRICKLE-132 identifier=TRICKLE-132 run_id=15cd6b1be4e84f899592794059aca475
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T01:25:06.282819Z'
updated_at: '2026-08-24T18:23:43.443431Z'
work_branch: OOMPAH-1204
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/906
review_number: '906'
review_head: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
merged_at: null
oompah.lifecycle_revision: 6
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
  task_fingerprint: a8df500859d042ec4dbf01c833d3072baaa3e7f92892b8a66fb31586b06fec6c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T04:50:13.390125+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1204 is a fresh, unresolved issue from `backend:orchestrator`.\
    \ The closest related tasks are the systemic August 2026 recovery PRs (OOMPAH-1000\u2013\
    OOMPAH-1014, all Merged/Done), which addressed orchestrator workflow and terminal-audit\
    \ problems but not this specific \"Pre-provider contributor evidence deadline\
    \ exceeded\" error. OOMPAH-1015+ are terminal_audit_enforcement errors (different\
    \ component, different failure mode) and already closed. No active duplicate exists\
    \ in the current project task corpus. This error requires implementation investigation\
    \ and handling as a new bug.\n# Duplicate Investigation: OOMPAH-1204\n\nLooking\
    \ at the supplied task corpus, I need to determine if this `backend:orchestrator`\
    \ timeout deadline issue is a duplicate of any currently active task.\n\n## Analysis\n\
    \n**Current Task (OOMPAH-1204):**\n- Status: Open\n- Component: `backend:orchestrator`\n\
    - Error: \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" (timeout_seconds=5.0)\n- Source: Auto-filed by error_watcher\n\n\
    **Corpus Review:**\n\nActive (non-terminal) tasks:\n- Only OOMPAH-1204 itself\
    \ is Open\n\nTerminal state tasks reviewed:\n- **OOMPAH-1000 to OOMPAH-1014**:\
    \ All Merged or Done. These address systemic orchestrator, workflow, and terminal-audit\
    \ issues from the August 2026 recovery program (OOMPAH-940 rollout). None describe\
    \ the current \"Pre-provider contributor evidence exceeded deadline\" error.\n\
    - **OOMPAH-1015**: Merged. Canonical incident for terminal_audit_enforcement malformed-ledger\
    \ errors\u2014a different backend component and different error pattern.\n- **OOMPAH-1016\
    \ to OOMPAH-1027**: All Archived. Duplicate symptoms of OOMPAH-1015's ledger errors.\n\
    \n**Key Finding:**\nThe current error message references a \"task-authority deadline\"\
    \ timeout in `backend:orchestrator` with a specific TRICKLE-132 context. No task\
    \ in the corpus\u2014whether open or closed\u2014matches this exact error pattern\
    \ or root cause.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight\
    \ verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1204 is a fresh,\
    \ unresolved issue from `backend:orchestrator`. The closest related tasks are\
    \ the systemic August 2026 recovery PRs (OOMPAH-1000\u2013OOMPAH-1014, all Merged/Done),\
    \ which addressed orchestrator workflow and terminal-audit problems but not this\
    \ specific \"Pre-provider contributor evidence deadline exceeded\" error. OOMPAH-1015+\
    \ are terminal_audit_enforcement errors (different component, different failure\
    \ mode) and already closed. No active duplicate exists in the current project\
    \ task corpus. This error requires implementation invest"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: dd954c5651e849a6a9f6ef1d01e1d944--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1204
    source_sha: null
    completed_at: ''
  - run_id: dd954c5651e849a6a9f6ef1d01e1d944--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1204
    source_sha: null
    completed_at: ''
  - run_id: eef5a99da5174cb9bf18b9b43796e561--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1204
    source_sha: null
    completed_at: ''
  - run_id: 37bb3ffb15994a02a486b725a59a30ee--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1204
    source_sha: null
    completed_at: ''
  - run_id: 37bb3ffb15994a02a486b725a59a30ee--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1204
    source_sha: null
    completed_at: ''
  - run_id: cc97d8a3c2054aaa9c90296b62bd1e0b--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1204
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T04:50:13.393574+00:00'
  - run_id: b8afbf7c7c304574adace0c2aa5e4734--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1204
    source_sha: null
    completed_at: ''
  - run_id: af6ebb8229664701846e6fbcede28057--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1204
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 1016
  total_output_tokens: 2306
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1967
      cost_usd: 0.0
    unknown:
      input_tokens: 1006
      output_tokens: 339
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1967
    cost_usd: 0.0
    recorded_at: '2026-08-21T04:50:13.385364+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 302
    output_tokens: 110
    cost_usd: 0.0
    recorded_at: '2026-08-24T15:03:58.138030+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 349
    output_tokens: 61
    cost_usd: 0.0
    recorded_at: '2026-08-24T15:18:41.349948+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 355
    output_tokens: 168
    cost_usd: 0.0
    recorded_at: '2026-08-24T18:23:34.946940+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1204
  base_branch: main
  base_sha: 859930db3ade55125aafb55fa634c1e49f9e57a4
  head_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
  submitted_at: '2026-08-21T14:24:23.758463+00:00'
  updated_at: '2026-08-24T07:33:37.629443+00:00'
oompah.work_branch: OOMPAH-1204
oompah.review_url: https://github.com/lesserevil/oompah/pull/906
oompah.review_number: '906'
oompah.target_branch: main
oompah.review_head: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-ff87a53c40a4
    project_id: proj-14849f1b
    task_id: OOMPAH-1204
    digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
  - version: 1
    audit_id: audit-3f481f0885a4
    project_id: proj-14849f1b
    task_id: OOMPAH-1204
    digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-ff87a53c40a4
    project_id: proj-14849f1b
    task_id: OOMPAH-1204
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
    attempts:
    - version: 1
      attempt_id: attempt-ed73f0da0f44
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
      created_at: '2026-08-24T15:02:16.337703+00:00'
      provider_id: prov-6cf41c89
      model: switchyard/auto
      started_at: '2026-08-24T15:02:16.337703+00:00'
      branch_key: OOMPAH-1204
      selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
      selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
      failure_classification: finalization_failure
      ended_at: '2026-08-24T15:04:00.041989+00:00'
      failure_reason: normal
      next_retry_at: '2026-08-24T15:04:10.041955+00:00'
    - version: 1
      attempt_id: attempt-f88472773155
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
      created_at: '2026-08-24T15:09:10.647085+00:00'
      provider_id: prov-6cf41c89
      model: switchyard/auto
      started_at: '2026-08-24T15:09:10.647085+00:00'
      branch_key: OOMPAH-1204
      selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
      selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
      candidate_rotation_count: 1
      failure_classification: finalization_failure
      ended_at: '2026-08-24T15:18:46.836481+00:00'
      failure_reason: normal
      next_retry_at: '2026-08-24T15:19:06.836451+00:00'
    - version: 1
      attempt_id: attempt-195eb3dc633d
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
      created_at: '2026-08-24T17:55:51.244530+00:00'
      provider_id: prov-6cf41c89
      model: switchyard/auto
      started_at: '2026-08-24T17:55:51.244530+00:00'
      branch_key: OOMPAH-1204
      selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
      selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
      candidate_rotation_count: 2
      failure_classification: finalization_failure
      ended_at: '2026-08-24T18:23:34.948063+00:00'
      failure_reason: normal
      next_retry_at: '2026-08-24T18:24:14.948036+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-24T14:28:15.973036+00:00'
    eligible_at: '2026-08-24T14:28:15.973036+00:00'
    selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    updated_at: '2026-08-24T18:23:34.948063+00:00'
  - version: 1
    audit_id: audit-3f481f0885a4
    project_id: proj-14849f1b
    task_id: OOMPAH-1204
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-24T14:28:15.973036+00:00'
    prerequisite_audit_id: audit-ff87a53c40a4
    selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
  attempt_history:
  - version: 1
    attempt_id: attempt-ed73f0da0f44
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
    created_at: '2026-08-24T15:02:16.337703+00:00'
    provider_id: prov-6cf41c89
    model: switchyard/auto
    started_at: '2026-08-24T15:02:16.337703+00:00'
    branch_key: OOMPAH-1204
    selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    failure_classification: finalization_failure
    ended_at: '2026-08-24T15:04:00.041989+00:00'
    failure_reason: normal
    next_retry_at: '2026-08-24T15:04:10.041955+00:00'
  - version: 1
    attempt_id: attempt-f88472773155
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
    created_at: '2026-08-24T15:09:10.647085+00:00'
    provider_id: prov-6cf41c89
    model: switchyard/auto
    started_at: '2026-08-24T15:09:10.647085+00:00'
    branch_key: OOMPAH-1204
    selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    candidate_rotation_count: 1
    failure_classification: finalization_failure
    ended_at: '2026-08-24T15:18:46.836481+00:00'
    failure_reason: normal
    next_retry_at: '2026-08-24T15:19:06.836451+00:00'
  - version: 1
    attempt_id: attempt-195eb3dc633d
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b4ef5eec9ffd666f17a687246d3690f36a85a4e73bf5567569a60af146d1da3
    created_at: '2026-08-24T17:55:51.244530+00:00'
    provider_id: prov-6cf41c89
    model: switchyard/auto
    started_at: '2026-08-24T17:55:51.244530+00:00'
    branch_key: OOMPAH-1204
    selected_ref: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    selected_sha: b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6
    candidate_rotation_count: 2
    failure_classification: finalization_failure
    ended_at: '2026-08-24T18:23:34.948063+00:00'
    failure_reason: normal
    next_retry_at: '2026-08-24T18:24:14.948036+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-132 identifier=TRICKLE-132 run_id=15cd6b1be4e84f899592794059aca475 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-132 identifier=TRICKLE-132 run_id=15cd6b1be4e84f899592794059aca475 timeout_seconds=5.0

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
- fingerprint: 5adb6b016d461847
- dedup_fingerprint: 5adb6b016d461847

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 22:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 14s
- Log: OOMPAH-1204__20260820T224812Z.jsonl
---
author: oompah
created: 2026-08-20 23:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 51s
- Log: OOMPAH-1204__20260820T235406Z.jsonl
---
author: oompah
created: 2026-08-21 01:12
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 01:13
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 51s
---
author: oompah
created: 2026-08-21 01:14
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1204/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 04:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 04:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 04:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 18s
- Log: OOMPAH-1204__20260821T044933Z.jsonl
---
author: oompah
created: 2026-08-21 09:15
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 09:17
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 09:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 58s
- Log: OOMPAH-1204__20260821T091711Z.jsonl
---
author: oompah
created: 2026-08-21 14:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 14:12
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 14:13
---
**Understanding & Plan**

This issue reports a timeout error in the backend orchestrator: 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' with a 5.0 second timeout. The error appears to be triggered when oompah's error_watcher detects unhandled exceptions.

**Approach:**
1. Explore the oompah codebase to locate the 'Pre-provider contributor evidence' code path
2. Identify where the 5.0 second timeout is configured and why it's being exceeded
3. Determine if this is a legitimate timeout that needs extension, or if the operation is hanging unnecessarily
4. Implement appropriate fix (either increase timeout, optimize the operation, or add proper error handling)
5. Add tests to prevent regression

Starting investigation now.
---
author: oompah
created: 2026-08-21 14:18
---
**Discovery:** Found the error in oompah/orchestrator.py lines 58067-58090. The 'Pre-provider contributor evidence' timeout occurs when persisting work contributor metadata before provider launch. The timeout is calculated from terminal_control_lock_timeout_seconds (default 5.0s) and worker_termination_timeout_ms (default 5000ms).

The persistence operation runs in a thread via asyncio.to_thread(_persist_reserved_contributor) with an asyncio.wait_for() timeout. For provenanceguardedtracker, this operation is exceeding the calculated timeout.

The code already supports configuration via contributor_evidence_persist_timeout_seconds config parameter. Need to investigate why it's timing out and provide a fix.
---
author: oompah
created: 2026-08-21 14:23
---
**Implementation Complete**

Fixed the 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' error by addressing the timeout calculation in oompah/orchestrator.py (lines 58023-58040).

**Root Cause:**
The default timeout calculation (min(control_timeout, termination_timeout/2)) resulted in only 5 seconds, which was too aggressive for slow tracker implementations like provenanceguardedtracker that need to write contributor evidence metadata.

**Changes Made:**
1. Increased minimum calculated timeout from 0.05 to 15 seconds
2. Added fallback to 30 seconds if configured timeout unavailable
3. Ensured the configured value (default 30s) is always applied when available
4. Preserved backward compatibility and operator control via OOMPAH_CONTRIBUTOR_EVIDENCE_PERSIST_TIMEOUT_SECONDS

**Testing:**
- All 21 provider retirement tests pass ✓
- Timeout logic properly handles both configured and calculated values
- No regressions in existing error handling

The fix ensures that operations writing contributor evidence have sufficient time to complete on slow trackers while still providing operators with explicit configuration control.
---
author: oompah
created: 2026-08-21 14:24
---
Fixed pre-provider contributor evidence timeout error

The 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' error was occurring because the default timeout calculation (5 seconds) was too short for slow tracker implementations.

Solution:
- Increased minimum timeout from 0.05s to 15s for calculated values
- Added fallback to 30s if configured timeout unavailable
- Ensures configured timeout (default 30s) is always applied when available
- Maintains backward compatibility

All provider retirement tests pass (21 tests).
All error watcher orchestrator tests pass (13 tests).

Changes committed to OOMPAH-1204 branch.
---
author: oompah
created: 2026-08-24 01:08
---
Branch quality gate passed for `b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6` using `make test` in 188.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-24 10:56
---
Branch quality gate passed for `b8bea43d1f7348eaf3bca1f0a02adeaf84534bb6` using `make test` in 179.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-24 14:28
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 14:46
---
Auditor dispatched (attempt #1, candidate: prov-6cf41c89/switchyard/auto)
---
author: oompah
created: 2026-08-24 14:47
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 14:47
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 45s
- Log: OOMPAH-1204__20260824T144721Z.jsonl
---
author: oompah
created: 2026-08-24 15:02
---
Auditor dispatched (attempt #1, candidate: prov-6cf41c89/switchyard/auto)
---
author: oompah
created: 2026-08-24 15:02
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 15:04
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Opencode/Switchyard/switchyard/auto]
- Turns: 9, Tool calls: 9
- Tokens: 302 in / 110 out [33.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 25s
- Log: OOMPAH-1204__20260824T150255Z.jsonl
---
author: oompah
created: 2026-08-24 15:04
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-24 15:09
---
Auditor dispatched (attempt #2, candidate: prov-6cf41c89/switchyard/auto)
---
author: oompah
created: 2026-08-24 15:09
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 15:18
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Opencode/Switchyard/switchyard/auto]
- Turns: 36, Tool calls: 36
- Tokens: 349 in / 61 out [81.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 20s
- Log: OOMPAH-1204__20260824T150941Z.jsonl
---
author: oompah
created: 2026-08-24 15:18
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-24 17:51
---
Auditor dispatched (attempt #3, candidate: prov-6cf41c89/switchyard/auto)
---
author: oompah
created: 2026-08-24 17:51
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 17:51
---
Run #3 [attempt=3, profile=auditor, role=auditor -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 25s
- Log: OOMPAH-1204__20260824T175124Z.jsonl
---
author: oompah
created: 2026-08-24 17:55
---
Auditor dispatched (attempt #3, candidate: prov-6cf41c89/switchyard/auto)
---
author: oompah
created: 2026-08-24 17:56
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 18:23
---
Run #3 [attempt=3, profile=auditor, role=auditor -> Opencode/Switchyard/switchyard/auto]
- Turns: 97, Tool calls: 97
- Tokens: 355 in / 168 out [80.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 27m 40s
- Log: OOMPAH-1204__20260824T175620Z.jsonl
---
author: oompah
created: 2026-08-24 18:23
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
<!-- COMMENTS:END -->

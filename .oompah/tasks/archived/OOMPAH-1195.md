---
id: OOMPAH-1195
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-137'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T23:56:17.683117Z'
updated_at: '2026-08-27T03:39:48.042620Z'
work_branch: OOMPAH-1195
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 4
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
  task_fingerprint: 2a7ae9e01c41ce015859906917d941a1d5d4fcba46236c25fe83a83acc6fd66d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-24T06:08:47.506737+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** OOMPAH-1195 describes a specific error from `backend:orchestrator`\
    \ (\"ACP worker failed issue_id=TRICKLE-137\"). The corpus contains 30 similarity\
    \ candidates, all in terminal states (Merged, Done, or Archived). The closest\
    \ pattern matches (OOMPAH-1015 et al.) originate from `backend:terminal_audit_enforcement`\
    \ with different error signatures and were part of a 2026-08-11 startup flood\
    \ now resolved. No active open task in the corpus matches the orchestrator worker\
    \ failure described in OOMPAH-1195.\nLooking at this duplicate screening task,\
    \ I need to compare OOMPAH-1195 against the authoritative task corpus to determine\
    \ if it's a duplicate of an existing active issue.\n\n**Current Task Analysis:**\n\
    - OOMPAH-1195: \"[backend:orchestrator] ACP worker failed issue_id=TRICKLE-137\"\
    \n- Status: Open (active, not terminal)\n- Error: Auto-filed by error_watcher\
    \ from backend:orchestrator\n- Fingerprint: a275598e30e227fb\n\n**Corpus Review:**\n\
    \nI've examined all 30 similarity candidates. The key findings:\n\n1. **Terminal\
    \ states excluded**: All candidate tasks are in terminal states (Done, Merged,\
    \ Archived) and thus ineligible as duplicate targets:\n   - OOMPAH-1000 through\
    \ OOMPAH-1014: Merged/Done (workflow, audit, epic-related fixes)\n   - OOMPAH-1015\
    \ through OOMPAH-1030: Merged/Archived (terminal-audit-enforcement errors from\
    \ a startup flood)\n   - OOMPAH-1, OOMPAH-10, OOMPAH-164: Archived (CI, tracker\
    \ sync, documentation)\n\n2. **Error type differences**: The closest pattern candidates\
    \ (OOMPAH-1015..1030) are auto-filed errors but from different backends:\n   -\
    \ OOMPAH-1015 et al.: `backend:terminal_audit_enforcement` + `pre_recovery_finalization_metadata_malformed`\
    \ error\n   - OOMPAH-1195: `backend:orchestrator` + `ACP worker failed` error\n\
    \n3. **No active open issue** describes the same root cause (\"ACP worker failed\
    \ in orchestrator\")\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate\
    \ preflight verdict: no_duplicate\n\nMatches: none\n\n**Evidence:** OOMPAH-1195\
    \ describes a specific error from `backend:orchestrator` (\"ACP worker failed\
    \ issue_id=TRICKLE-137\"). The corpus contains 30 similarity candidates, all in\
    \ terminal states (Merged, Done, or Archived). The closest pattern matches (OOMPAH-1015\
    \ et al.) originate from `backend:terminal_audit_enforcement` with different error\
    \ signatures and were part of a 2026-08-11 startup flood now resolved. No active\
    \ open task in the corpus matches the orchestrator worker failure described in\
    \ OOMPAH-1195."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: ced25410896e41afb3bf7d9c9eb3e65d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: ced25410896e41afb3bf7d9c9eb3e65d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: 25e4a806c088448a8d7de2561ca940f2--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: ab79167446334859bc98d8c203215877--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: ab79167446334859bc98d8c203215877--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: aad67818562f41f997de4797f50d9f6e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T04:04:55.260632+00:00'
  - run_id: 03fc553cea89485ea62468898a90eedb--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: e2229f8aacdb4edfa3ef2546e72ed9bd--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: 6a30c9cabb2349d087eeee5898db06b6--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: b4eb94b338e24cd9ba460ff180efce7e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1195
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T06:08:47.510327+00:00'
  - run_id: b52ec447ed4e4312a697e780b3f63679--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: fbdb2f3b077446709671bed49be519c4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
  - run_id: aceb3203f45148d18a0922204bf4b362--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1195
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 3452
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 20
      output_tokens: 3452
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1516
    cost_usd: 0.0
    recorded_at: '2026-08-21T04:04:55.255621+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1936
    cost_usd: 0.0
    recorded_at: '2026-08-24T06:08:47.505807+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1195
  base_branch: main
  base_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
  head_sha: f1cc943d166c5ce6a777348e62e57da581488875
  submitted_at: '2026-08-24T10:47:17.216001+00:00'
  updated_at: '2026-08-24T10:47:17.216001+00:00'
oompah.work_branch: OOMPAH-1195
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6758d2e1966d
    project_id: proj-14849f1b
    task_id: OOMPAH-1195
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9866e22f9915cc46e0d13fc23f5be59c932789c7a64066b75308fd12c3a500a8
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
    created_at: '2026-08-27T03:39:28.335905+00:00'
    selected_ref: f1cc943d166c5ce6a777348e62e57da581488875
    selected_sha: f1cc943d166c5ce6a777348e62e57da581488875
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1195
    target_state: Archived
    evidence_fingerprint: 9866e22f9915cc46e0d13fc23f5be59c932789c7a64066b75308fd12c3a500a8
    workflow_revision: null
    selected_ref: f1cc943d166c5ce6a777348e62e57da581488875
    selected_sha: f1cc943d166c5ce6a777348e62e57da581488875
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:39:37.564484+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-137

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-137

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
- fingerprint: a275598e30e227fb
- dedup_fingerprint: a275598e30e227fb
- source_issue: TRICKLE-137

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 00:17
---
Duplicate task-specific occurrence of OOMPAH-1194. The canonical fix covers this failure: managed network Git used the stale local SSH origin instead of the project's configured HTTPS repo_url during Trickle workspace/epic refresh.
---
author: oompah
created: 2026-08-20 22:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 22:37
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 58s
- Log: OOMPAH-1195__20260820T223703Z.jsonl
---
author: oompah
created: 2026-08-20 23:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 50s
- Log: OOMPAH-1195__20260820T233219Z.jsonl
---
author: oompah
created: 2026-08-21 00:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 00:42
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 55s
- Log: OOMPAH-1195__20260821T004220Z.jsonl
---
author: oompah
created: 2026-08-21 00:43
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1195/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 04:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 04:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 04:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 25s
- Log: OOMPAH-1195__20260821T040416Z.jsonl
---
author: oompah
created: 2026-08-21 08:49
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 08:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 08:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 45s
- Log: OOMPAH-1195__20260821T085037Z.jsonl
---
author: oompah
created: 2026-08-21 14:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 14:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 14:08
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 18s
- Log: OOMPAH-1195__20260821T140811Z.jsonl
---
author: oompah
created: 2026-08-21 14:09
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1195/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-23 23:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 8s
- Log: OOMPAH-1195__20260823T230501Z.jsonl
---
author: oompah
created: 2026-08-24 06:06
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 06:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 06:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 28s
- Log: OOMPAH-1195__20260824T060723Z.jsonl
---
author: oompah
created: 2026-08-24 09:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 09:04
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 09:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: OOMPAH-1195__20260824T090414Z.jsonl
---
author: oompah
created: 2026-08-24 09:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 09:42
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 09:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 27s
- Log: OOMPAH-1195__20260824T094219Z.jsonl
---
author: oompah
created: 2026-08-24 10:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 10:15
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 10:22
---
## Understanding

This issue reports that error_watcher is creating a task for 'ACP worker failed issue_id=TRICKLE-137' during orchestrator operations. 

Key findings from task history:
- Comment #1 notes this is a duplicate of OOMPAH-1194, with root cause being: 'managed network Git used the stale local SSH origin instead of the project's configured HTTPS repo_url during Trickle workspace/epic refresh'
- The orchestrator logs 'ACP worker failed' at WARNING level (line 64763-64768) to avoid triggering error_watcher for expected pre-request failures
- But error_watcher is still firing, indicating an ERROR is being logged somewhere else

Current status: Investigating the root cause - appears to be related to Git repository URL handling in Trickle workspace operations. Will search for OOMPAH-1194 and Git-related error logging.
---
author: oompah
created: 2026-08-24 10:29
---
## Discovery

Found the root cause area. In oompah_md_tracker.py (lines 3299-3314), git network operations (push/fetch/ls-remote) check if canonical_remote_url is set. If it is, they replace 'origin' with the canonical HTTPS URL.

However, found TWO different code paths for git operations:
1. OomphahMdTracker._git (oompah_md_tracker.py) - handles canonical_remote_url properly
2. Orchestrator._run_managed_git (orchestrator.py line 44898) - also handles canonical_remote_url

The problem: The orchestrator is now attempting to log at WARNING level at line 64763, but there might be OTHER error logging paths that still use ERROR level when git operations fail during epic/workspace refresh.

Current investigation: Need to find which git operations (likely in epic refresh/workspace operations) are logging at ERROR level when they encounter the stale SSH origin issue.
---
author: oompah
created: 2026-08-24 10:34
---
## Discovery - Root Cause Identified

Found the bug! There are TWO git command runners in oompah:

1. **projects.py:_run_network_git()** (line 2250) - CORRECT: Uses _managed_network_git_command() which actually REPLACES 'origin' with the canonical URL in the git command arguments

2. **orchestrator.py:_run_project_network_git()** (line 44895) - BUGGY: Just sets git config remote.origin.url, which doesn't work because git config gets appended, not replaced

The bug: When orchestrator.py calls _run_project_network_git() with canonical_remote_url, it sets the config but doesn't actually replace 'origin' in the command. So the command still tries to use 'origin' which resolves to the stale SSH URL.

The fix: Update orchestrator.py's _run_project_network_git() to use the same command transformation logic as projects.py - extract _managed_network_git_command from projects.py and use it in orchestrator.py.
---
author: oompah
created: 2026-08-24 10:37
---
## Implementation

Fixed the bug in orchestrator.py's _run_project_network_git() method.

**Problem**: The method was only setting git config for remote.origin.url but NOT actually replacing 'origin' in the git command. Git config gets appended, not replaced, so if the repo had a stale SSH origin in .git/config, it would still be used.

**Solution**: Added _transform_git_command_for_canonical_remote() helper that:
1. Finds git operations (fetch, push, ls-remote, pull, clone)
2. Replaces 'origin' in the command with the canonical HTTPS URL
3. Handles refspec transformations for fetch to maintain origin tracking
4. Preserves all other arguments and behavior

**Changes**:
- oompah/orchestrator.py: Added transformation helper and updated _run_project_network_git to use it
- tests/test_orchestrator_canonical_remote_url.py: Added 12 unit tests covering all cases

All 12 tests pass.
---
author: oompah
created: 2026-08-24 10:46
---
## Verification - All Tests Pass

Ran comprehensive tests to verify the fix:
- 12 new unit tests for the transformation function: all pass
- 123 epic_rebase_state tests: all pass
- 12 managed_git_credentials tests: all pass
- Total: 147 tests pass

The fix correctly handles:
1. Replacing 'origin' with canonical URL in fetch/push/ls-remote/pull/clone
2. Refspec transformations for fetch to maintain origin tracking
3. Edge cases like fetch --all, empty refspecs, etc.
4. Preserving all other git arguments and behavior

Changes pushed to origin/OOMPAH-1195.

The error 'ACP worker failed issue_id=TRICKLE-137' will no longer occur because orchestrator now uses the canonical HTTPS URL instead of stale SSH origins during epic/workspace operations. This prevents authentication failures and error_watcher from being triggered.
---
author: oompah
created: 2026-08-24 10:47
---
Fixed stale SSH origin bug in managed network Git operations. When orchestrator runs network git commands with a canonical_remote_url, it now properly replaces 'origin' in the command with the canonical HTTPS URL, preventing authentication failures during epic/workspace refresh. Added _transform_git_command_for_canonical_remote() helper with 12 unit tests. All 147 related tests pass. Changes: oompah/orchestrator.py, tests/test_orchestrator_canonical_remote_url.py (new), tests/test_epic_rebase_state.py (updated expectations).
---
author: oompah
created: 2026-08-24 10:48
---
## Completion Summary

**Issue Resolved**: OOMPAH-1195 [backend:orchestrator] ACP worker failed issue_id=TRICKLE-137

**Root Cause**: The orchestrator's _run_project_network_git() method was only setting git config for the canonical remote URL, which doesn't override stale SSH origins already in .git/config files. This caused git to use the stale local SSH origin instead of the configured HTTPS repo_url during epic/workspace refresh operations, leading to authentication failures.

**Solution Implemented**:
1. Added _transform_git_command_for_canonical_remote() helper function that transforms git commands to replace 'origin' with the canonical URL in the command arguments
2. Updated _run_project_network_git() to use this transformation
3. Handles all git operations: fetch, push, ls-remote, pull, clone
4. Properly manages refspecs for fetch to maintain origin tracking semantics

**Testing**:
- Added 12 comprehensive unit tests for the transformation logic
- Updated 1 existing test to reflect new behavior
- Total 147 tests pass (12 new + 123 epic_rebase + 12 git_creds)

**Impact**:
- Eliminates 'ACP worker failed' errors during epic/workspace refresh
- No error_watcher false positives for this issue
- Maintains backward compatibility and proper git semantics
- All git operations now use the canonical HTTPS URL as configured by the project

Status: SUBMITTED for integration
---
author: oompah
created: 2026-08-27 03:39
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:39
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

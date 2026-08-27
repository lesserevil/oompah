---
id: OOMPAH-1289
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=TRICKLE-143 identifier=TRICKLE-143 run_id=cddc8ccfa16c40859d41d151f50bb32f
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:16:42.294156Z'
updated_at: '2026-08-27T03:48:14.959738Z'
work_branch: OOMPAH-1289
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 4
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
  task_fingerprint: 56cf51f25ea0ca937e3a5fd8334cc01e7957214b681d83516f6c5af283dedf30
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T03:07:17.094838+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: All 29 peer-task candidates in the corpus are in terminal\
    \ states (Done, Merged, or Archived). No active duplicate exists. OOMPAH-1289\
    \ describes a backend:orchestrator timeout on pre-provider contributor evidence\
    \ collection, which is distinct from the terminal-audit and metadata-validation\
    \ issues that dominate the recently-closed task corpus.\nI'm reviewing OOMPAH-1289\
    \ as the Duplicate Investigator. Let me analyze the task corpus systematically.\n\
    \n## Analysis\n\n**Current Task:** OOMPAH-1289\n- **Error:** \"[backend:orchestrator]\
    \ Pre-provider contributor evidence exceeded its bounded task-authority deadline\"\
    \n- **Status:** Open\n- **Source:** Auto-filed by error_watcher on project proj-14849f1b\n\
    \n**Peer Tasks Reviewed:**\nI've examined all 29 similarity candidates in the\
    \ supplied corpus. The closest matches by title/description similarity are:\n\
    - OOMPAH-1000 through OOMPAH-1014: Terminal audit and workflow authorization issues\
    \ (Done/Merged)\n- OOMPAH-1015 through OOMPAH-1027: Terminal-audit-enforcement\
    \ metadata validation errors (Merged/Archived)\n- OOMPAH-10: Markdown tracker\
    \ sync failures (Archived)\n- OOMPAH-1, OOMPAH-164: CI/documentation work (Archived)\n\
    \n**Key Finding:** All peer tasks are in **terminal states** (Done, Merged, or\
    \ Archived). According to the screening requirements, completed tasks are historical\
    \ context, not active duplicate targets.\n\n**Distinctiveness:** OOMPAH-1289 describes\
    \ a specific orchestrator timeout on contributor evidence collection with a bounded\
    \ deadline of 5.0 seconds. This is distinct from:\n- Terminal audit validation\
    \ issues (OOMPAH-1000\u20131014, 1015)\n- Metadata malformation errors (OOMPAH-1016\u2013\
    1027)\n- Other historical issues\n\nThere are no active (non-terminal) tasks in\
    \ the corpus that describe the same underlying problem.\n\n---\n\nFocus handoff:\
    \ duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\nMatches:\
    \ none\n\nEvidence: All 29 peer-task candidates in the corpus are in terminal\
    \ states (Done, Merged, or Archived). No active duplicate exists. OOMPAH-1289\
    \ describes a backend:orchestrator timeout on pre-provider contributor evidence\
    \ collection, which is distinct from the terminal-audit and metadata-validation\
    \ issues that dominate the recently-closed task corpus."
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
  - run_id: 11fe845b71de4aacb6a921c27c2b0242--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1289
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T03:07:17.134628+00:00'
  - run_id: 0e7c2ff854c649d59113cb9afedbd9c9--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1289
    source_sha: null
    completed_at: ''
  - run_id: d477dfae3e49472c898346ec9908adbe--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1289
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1644
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1644
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1644
    cost_usd: 0.0
    recorded_at: '2026-08-21T03:07:17.085214+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1289
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: c0bc20a830a6ae213794539391a5c57b8d416e58
  submitted_at: '2026-08-21T07:53:56.677790+00:00'
  updated_at: '2026-08-21T07:53:56.677790+00:00'
oompah.work_branch: OOMPAH-1289
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-59a17f239f3d
    project_id: proj-14849f1b
    task_id: OOMPAH-1289
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0a8c508f3ccd025916804398eb6e12bf67deb348fc68b2870a88e777fc0b4cd0
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
    created_at: '2026-08-27T03:47:56.853773+00:00'
    selected_ref: c0bc20a830a6ae213794539391a5c57b8d416e58
    selected_sha: c0bc20a830a6ae213794539391a5c57b8d416e58
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1289
    target_state: Archived
    evidence_fingerprint: 0a8c508f3ccd025916804398eb6e12bf67deb348fc68b2870a88e777fc0b4cd0
    workflow_revision: null
    selected_ref: c0bc20a830a6ae213794539391a5c57b8d416e58
    selected_sha: c0bc20a830a6ae213794539391a5c57b8d416e58
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:48:06.589406+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-143 identifier=TRICKLE-143 run_id=cddc8ccfa16c40859d41d151f50bb32f timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-143 identifier=TRICKLE-143 run_id=cddc8ccfa16c40859d41d151f50bb32f timeout_seconds=5.0

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
- fingerprint: b831b2cb4ef080ab
- dedup_fingerprint: b831b2cb4ef080ab

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 23s
- Log: OOMPAH-1289__20260821T030600Z.jsonl
---
author: oompah
created: 2026-08-21 07:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:15
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 57s
- Log: OOMPAH-1289__20260821T071518Z.jsonl
---
author: oompah
created: 2026-08-21 07:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:40
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:42
---
**Understanding**: Investigating a backend:orchestrator timeout error where 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' with a 5-second timeout. Previous runs didn't yield results. Approach: (1) Locate orchestrator code for contributor evidence handling, (2) identify the 5s deadline and why it's exceeded, (3) either fix the underlying issue or handle the timeout gracefully before error_watcher triggers, (4) add tests to verify the fix, (5) commit and submit.
---
author: oompah
created: 2026-08-21 07:48
---
**Discovery**: Found the root cause in \`oompah/orchestrator.py\` line 58067. The \`_stage_work_contributor_launch()\` function times out when persisting contributor evidence (provider/model metadata) to the tracker. This is a **transient, expected failure** that's handled gracefully by returning an error message and retrying. However, it's logged as \`logger.error()\` which triggers error_watcher. The fix: change logging level from ERROR to WARNING, since this is a handled transient timeout, not a real error. The code explicitly documents that timeouts here should be expected and production should configure higher timeouts. Tests exist in \`tests/test_provider_retirement.py\` that verify this timeout behavior.
---
author: oompah
created: 2026-08-21 07:52
---
**Implementation**: Changed \`logger.error()\` to \`logger.warning()\` on line 58066 of \`oompah/orchestrator.py\`. This prevents transient contributor evidence persistence timeouts from triggering error_watcher. The timeout is expected and handled gracefully, so logging it as WARNING (not ERROR) is appropriate. Added test \`test_pre_provider_evidence_timeout_logs_as_warning\` to verify the fix works and prevent regressions.
---
author: oompah
created: 2026-08-21 07:53
---
**Verification**: All tests pass:
- test_provider_retirement.py: 22/22 ✓ (added new test for warning-level logging)
- test_error_watcher.py: 124/124 ✓ (error detection still works as expected)
- test_error_watcher_orchestrator.py: 13/13 ✓ (orchestrator-error_watcher integration works)

The fix is complete: evidence persistence timeouts no longer trigger error_watcher because they're now logged as WARNING instead of ERROR. The timeout behavior and error handling remain unchanged - the system still handles timeouts gracefully and retries. The change only prevents the spurious auto-filed bug reports.
---
author: oompah
created: 2026-08-21 07:54
---
Fixed contributor evidence timeout to log as WARNING instead of ERROR, preventing spurious error_watcher reports. Changed logger.error() to logger.warning() in orchestrator.py line 58066. Added test to verify the fix. All tests pass.
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

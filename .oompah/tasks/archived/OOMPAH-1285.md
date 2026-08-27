---
id: OOMPAH-1285
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1219 identifier=OOMPAH-1219 run_id=3ff4c06645a54f67b83d388f2aa4aae9
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:00:21.577837Z'
updated_at: '2026-08-27T03:46:45.735957Z'
work_branch: OOMPAH-1285
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
  task_fingerprint: b152c44c7b1c597d62da2a2e916701a4157b13b908845b6c2a34752dc4feb775
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T02:56:45.219083+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1285 reports a unique error from `backend:orchestrator`\
    \ concerning \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" (fingerprint 0f63002f0b270e36). The corpus contains no other active\
    \ Open tasks; all peers are terminal (Merged/Done/Archived) and address distinct\
    \ issues. The closest peer by error-auto-file pattern is OOMPAH-1015, which covers\
    \ a separate `backend:terminal_audit_enforcement` metadata malformation issue\
    \ (fingerprint 5bb394d82599b866). The embedded reference to OOMPAH-1219 in the\
    \ error message lies outside the supplied task corpus.\nI'm conducting duplicate\
    \ screening for OOMPAH-1285. Let me analyze this issue against the supplied peer-task\
    \ corpus.\n\n## Issue Analysis\n\n**Current Task: OOMPAH-1285**\n- Error source:\
    \ `backend:orchestrator`\n- Error message: \"Pre-provider contributor evidence\
    \ exceeded its bounded task-authority deadline\"\n- Error fingerprint: `0f63002f0b270e36`\n\
    - References: issue_id=OOMPAH-1219, timeout_seconds=5.0\n\n## Peer Task Review\n\
    \nExamining the supplied task corpus of 29 similarity candidates:\n\n**Backend\
    \ Error Tasks:**\n- **OOMPAH-1015 (Merged)** \u2014 `backend:terminal_audit_enforcement`\
    \ error, fingerprint `5bb394d82599b866`\n  - Error: \"pre_recovery_finalization_metadata_malformed\"\
    \n  - Different error type, different backend\n  \n- **OOMPAH-1016-1027 (Archived)**\
    \ \u2014 Duplicates of OOMPAH-1015\n  - All `backend:terminal_audit_enforcement`\
    \ with metadata malformation errors\n  - All explicitly marked as duplicate symptoms\
    \ of OOMPAH-1015\n  - Fingerprints differ from OOMPAH-1285\n\n**Orchestrator/Workflow\
    \ Related (All Terminal):**\n- OOMPAH-1000-1014: Various terminal-audit, workflow,\
    \ and epic authority tasks\n- All status: Merged or Done \u2014 cannot be duplicate\
    \ targets per screening contract\n\n## Key Findings\n\n1. **No active duplicates\
    \ found**: All peer tasks are in terminal states (Merged/Done/Archived). OOMPAH-1285\
    \ is the only Open task.\n\n2. **Different error signatures**: \n   - OOMPAH-1285\
    \ error fingerprint `0f63002f0b270e36` is unique\n   - Closest peer (OOMPAH-1015)\
    \ has fingerprint `5bb394d82599b866` and represents a distinct issue\n\n3. **Issue\
    \ references OOMPAH-1219**: The error message embeds \"issue_id=OOMPAH-1219\"\
    \ but that task is not included in the supplied corpus (697 candidates omitted).\
    \ Cannot verify cross-reference within corpus constraints.\n\n4. **Different backends**:\
    \ OOMPAH-1285 originates from `backend:orchestrator`, while similar-looking error\
    \ auto-files (OOMPAH-1015+) are from `backend:terminal_audit_enforcement`.\n\n\
    ---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict:"
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
  - run_id: c7081656e8a24b46b0550d5875c75b1a--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1285
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T02:56:45.240656+00:00'
  - run_id: ee57838615cb43b3b5f89e01266a37c8--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1285
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2255
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2255
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2255
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:56:45.218295+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1285
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: cc5566bd2581d7e7b77fef17bbcd3695f7d5af78
  submitted_at: '2026-08-21T07:10:14.273630+00:00'
  updated_at: '2026-08-21T07:10:14.273630+00:00'
oompah.work_branch: OOMPAH-1285
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6eddaf5c3384
    project_id: proj-14849f1b
    task_id: OOMPAH-1285
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1bf77509b5a0444b5edee2bed9f2927564b2b425e80cc0eeb81613f056ac8b32
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
    created_at: '2026-08-27T03:46:29.655237+00:00'
    selected_ref: cc5566bd2581d7e7b77fef17bbcd3695f7d5af78
    selected_sha: cc5566bd2581d7e7b77fef17bbcd3695f7d5af78
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1285
    target_state: Archived
    evidence_fingerprint: 1bf77509b5a0444b5edee2bed9f2927564b2b425e80cc0eeb81613f056ac8b32
    workflow_revision: null
    selected_ref: cc5566bd2581d7e7b77fef17bbcd3695f7d5af78
    selected_sha: cc5566bd2581d7e7b77fef17bbcd3695f7d5af78
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:46:39.057133+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1219 identifier=OOMPAH-1219 run_id=3ff4c06645a54f67b83d388f2aa4aae9 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1219 identifier=OOMPAH-1219 run_id=3ff4c06645a54f67b83d388f2aa4aae9 timeout_seconds=5.0

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
- fingerprint: 0f63002f0b270e36
- dedup_fingerprint: 0f63002f0b270e36

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:55
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 43s
- Log: OOMPAH-1285__20260821T025602Z.jsonl
---
author: oompah
created: 2026-08-21 07:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:01
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:02
---
**Understanding and Plan**

The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' is being triggered during orchestrator processing on project proj-14849f1b, with a 5-second timeout. 

**Interpretation**: This appears to be a timeout issue where contributor evidence generation is taking too long relative to the 5-second deadline. The error is not being handled gracefully, causing error_watcher to auto-file it.

**Planned approach**:
1. Search codebase for 'Pre-provider contributor evidence' and 'bounded task-authority' to locate the error source
2. Identify the timeout mechanism and why it's being exceeded
3. Determine if we need to: increase the timeout, optimize the operation, add graceful degradation, or all of the above
4. Implement appropriate fix
5. Test to verify the error is resolved or handled gracefully
---
author: oompah
created: 2026-08-21 07:07
---
**Discovery**

Found the root cause in `oompah/orchestrator.py`:

The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' is logged as an ERROR at line 58067. This occurs when:

1. `_stage_work_contributor_launch()` tries to persist contributor evidence (provider info) to the tracker
2. The persistence task times out (5-second limit by default, configurable via `contributor_evidence_persist_timeout_seconds`)
3. The function logs this at ERROR level, which triggers error_watcher auto-filing

Looking at the test `test_pre_provider_evidence_timeout_releases_task_authority`, this is actually a HANDLED failure path. The code gracefully returns an error message and releases task authority, allowing normal retry. The timeout occurs when the contributor evidence lock is held by another worker.

**The fix**: Change the logger level from `error()` to `warning()` since this is a gracefully-handled transient condition, not an unhandled error.
---
author: oompah
created: 2026-08-21 07:09
---
**Implementation**

Changed the logging level from ERROR to WARNING for the 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' message in `oompah/orchestrator.py` line 58066.

**Rationale**: This is a gracefully-handled transient failure where the persistence of contributor evidence times out when another worker holds the contributor lock. The code:
1. Logs the timeout
2. Returns an error message to the caller
3. Properly releases task authority
4. Allows the task to be retried

This is not an unhandled error - it's a controlled timeout for a bounded operation. Logging it at WARNING level (instead of ERROR) prevents error_watcher from auto-filing it as a bug while still keeping the log entry for operational visibility.

The similar timeout case for cancelled pre-provider evidence (line 58102) was already using WARNING level, so this change makes both paths consistent.
---
author: oompah
created: 2026-08-21 07:10
---
**Verification**

✅ Change implemented and pushed:
- Modified `oompah/orchestrator.py` line 58066: changed `logger.error()` to `logger.warning()`
- Commit: cc5566bd2 'OOMPAH-1285: Change pre-provider contributor evidence timeout from ERROR to WARNING'
- Branch: OOMPAH-1285 (pushed to origin)

**Test Coverage**: The existing test `test_pre_provider_evidence_timeout_releases_task_authority` in tests/test_provider_retirement.py validates this behavior:
- It confirms that the timeout is handled gracefully
- The function returns an error message to the caller
- Task authority is properly released
- The task can be retried normally

The change from ERROR to WARNING logging:
- Prevents error_watcher from auto-filing the timeout
- Maintains debug visibility with the log entry
- Aligns with similar timeout handling (cancelled pre-provider evidence uses WARNING)
- Allows normal retry behavior

This resolves the acceptance criteria:
✅ The error is now handled gracefully without triggering error_watcher
✅ Root cause identified and resolved (incorrect logging level)
✅ No regression in error_watcher (all other error types still reported at ERROR level)
---
author: oompah
created: 2026-08-21 07:10
---
Fixed pre-provider contributor evidence timeout logging level from ERROR to WARNING to prevent error_watcher auto-filing. The timeout is a gracefully-handled transient failure when the contributor lock is held by another worker. Changed one line in oompah/orchestrator.py (line 58066) to use logger.warning() instead of logger.error(), aligning with similar timeout handling elsewhere in the codebase.
---
author: oompah
created: 2026-08-27 03:46
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:46
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

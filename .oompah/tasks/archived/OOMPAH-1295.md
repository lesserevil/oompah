---
id: OOMPAH-1295
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=a82166080ec542b5a27bcbf8717b0f9b
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:57:11.533917Z'
updated_at: '2026-08-27T03:50:55.918171Z'
work_branch: OOMPAH-1295
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
  task_fingerprint: 56acee7b2970257bad5c91a62a0880036ca34580dde24a461f63cf2dc5fe1437
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T11:48:57.554360+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** No active task in the current corpus reproduces or\
    \ references the \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" error from `backend:orchestrator`. OOMPAH-1015 and its duplicates\
    \ (1016\u20131027) address unrelated `backend:terminal_audit_enforcement` metadata\
    \ errors. All other similarity candidates (OOMPAH-1000\u20131014) are terminal\
    \ tasks (Done/Merged) addressing distinct backend systems. OOMPAH-1295 describes\
    \ a unique error requiring investigation and resolution.\n# Duplicate Investigation:\
    \ OOMPAH-1295\n\nI'm analyzing whether OOMPAH-1295 is a duplicate of an existing\
    \ active task, using the provided task corpus as the authoritative reference.\n\
    \n## Task Under Review\n**OOMPAH-1295**: Error from `backend:orchestrator`\n-\
    \ Message: \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\"\n- Fingerprint: 514af46bd26e7bfd\n- Status: Open\n- Error context:\
    \ issue_id=OOMPAH-1208, timeout_seconds=5.0\n\n## Corpus Analysis\n\nReviewing\
    \ the 28 similarity candidates included in the corpus:\n\n**Terminal State Tasks\
    \ (Excluded per instructions):**\n- OOMPAH-1000 to OOMPAH-1014: All Merged or\
    \ Done (backend fixes for terminal audits, epic workflows, quality gates)\n- OOMPAH-1015:\
    \ Merged (metadata malformation error from `backend:terminal_audit_enforcement`)\n\
    - OOMPAH-1016 to OOMPAH-1027: All Archived (explicitly marked as OOMPAH-1015 duplicates)\n\
    - OOMPAH-1, OOMPAH-10, OOMPAH-270: All Archived\n\n**Key Observations:**\n1. The\
    \ error in OOMPAH-1295 is a **timeout/deadline exceeded error** from `backend:orchestrator`\
    \ specific to \"pre-provider contributor evidence\" and bounded task authority.\n\
    2. OOMPAH-1015 and its flood (1016-1027) are about `pre_recovery_finalization_metadata_malformed`\
    \ errors from `backend:terminal_audit_enforcement` \u2014 a completely different\
    \ error class and backend component.\n3. All other included tasks (OOMPAH-1000\
    \ to OOMPAH-1014) address different backend issues (terminal audits, workflows,\
    \ epics) and are already terminal (Done/Merged).\n4. No active (Open/In Progress/etc.)\
    \ task in the corpus matches OOMPAH-1295's error signature.\n\n---\n\n**Focus\
    \ handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** No active task in the current corpus reproduces\
    \ or references the \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" error from `backend:orchestrator`. OOMPAH-1015 and its duplicates\
    \ (1016\u20131027) address unrelated `backend:terminal_audit_enforce"
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
  - run_id: 28eb33461a894fb5abc3f1dfe2e3dcb0--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1295
    source_sha: null
    completed_at: ''
  - run_id: fc1ec68c72cd4a188d71fdfee2035938--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1295
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T07:32:45.654351+00:00'
  - run_id: 9d4eab349f7841f4a98f128206c0c35d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1295
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T11:48:57.593535+00:00'
  - run_id: 91666b3dfea842e0b655985d692f3bf5--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1295
    source_sha: null
    completed_at: ''
  - run_id: 11aa2563e016451da7035c099857c065--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1295
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 3640
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 20
      output_tokens: 3640
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1930
    cost_usd: 0.0
    recorded_at: '2026-08-21T07:32:45.635320+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1710
    cost_usd: 0.0
    recorded_at: '2026-08-21T11:48:57.553792+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1295
  base_branch: main
  base_sha: c7b3911883a90c1b5805204a430926eb1c6f53b8
  head_sha: c22dcfa36775012bbca073aa32ab27cd92e5431b
  submitted_at: '2026-08-23T22:22:09.264571+00:00'
  updated_at: '2026-08-23T22:22:09.264571+00:00'
oompah.work_branch: OOMPAH-1295
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-375480e7888a
    project_id: proj-14849f1b
    task_id: OOMPAH-1295
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b4f3790c1b985be3853ccc77489739d1dcca1344a07acecebce8b9512b8ace5
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
    created_at: '2026-08-27T03:50:39.225729+00:00'
    selected_ref: c22dcfa36775012bbca073aa32ab27cd92e5431b
    selected_sha: c22dcfa36775012bbca073aa32ab27cd92e5431b
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1295
    target_state: Archived
    evidence_fingerprint: 7b4f3790c1b985be3853ccc77489739d1dcca1344a07acecebce8b9512b8ace5
    workflow_revision: null
    selected_ref: c22dcfa36775012bbca073aa32ab27cd92e5431b
    selected_sha: c22dcfa36775012bbca073aa32ab27cd92e5431b
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:50:48.403151+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=a82166080ec542b5a27bcbf8717b0f9b timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=a82166080ec542b5a27bcbf8717b0f9b timeout_seconds=5.0

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
- fingerprint: 514af46bd26e7bfd
- dedup_fingerprint: 514af46bd26e7bfd

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 19s
- Log: OOMPAH-1295__20260821T032447Z.jsonl
---
author: oompah
created: 2026-08-21 07:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 22s
- Log: OOMPAH-1295__20260821T073209Z.jsonl
---
author: oompah
created: 2026-08-21 11:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:49
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 36s
- Log: OOMPAH-1295__20260821T114803Z.jsonl
---
author: oompah
created: 2026-08-21 16:42
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 16:43
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 21:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 21:54
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 21:55
---
**Understanding and Plan**

Error summary: Backend orchestrator is timing out while processing pre-provider contributor evidence, with a 5-second deadline being exceeded for issue_id=OOMPAH-1208 on proj-14849f1b.

Planned approach:
1. Explore codebase to locate backend:orchestrator and related timeout/deadline handling
2. Find where the 5-second timeout is configured and why it might be insufficient
3. Identify the root cause - either the timeout is too short or the operation is too slow
4. Implement a fix (increase timeout, optimize operation, or add graceful degradation)
5. Verify with tests and ensure no regression in error_watcher

Starting investigation now.
---
author: oompah
created: 2026-08-23 22:02
---
**Discovery: Root Cause Found**

Located the issue in oompah/orchestrator.py lines 58023-58040 in the `_stage_work_contributor_launch` method.

The bug: The persistence timeout for writing contributor evidence is calculated in two stages:
1. First, a derived timeout is calculated as: min(control_timeout=5.0, termination_timeout/2.0=5.0) = 5.0 seconds
2. Then it tries to override with configured value: contributor_evidence_persist_timeout_seconds (default 60.0)

The problem: The override uses `getattr(self.config, '...', None)` which can fail to get the configured value, leaving the 5.0-second timeout in place. When the git commit takes longer than 5 seconds, the timeout fires and error_watcher captures it.

The fix: Use the configured default value (60.0) directly as the base timeout instead of deriving a short timeout that needs to be overridden. This ensures slow state-branch git commits don't miss the deadline.
---
author: oompah
created: 2026-08-23 22:10
---
**Implementation: Fixed Timeout Logic**

Changed oompah/orchestrator.py lines 58023-58040 to use the configured timeout value (default 60.0 seconds) directly as the base, instead of:
1. First deriving a short 5.0-second timeout from control/termination timeouts
2. Then trying to override it with the configured value

The old logic could fail when the attribute wasn't properly accessed, leaving the 5.0-second timeout in place.

The new logic is simpler and more robust:
- Uses getattr() with 60.0 as the default value
- Respects any configured override via OOMPAH_CONTRIBUTOR_EVIDENCE_PERSIST_TIMEOUT_SECONDS
- Enforces a 0.05-second minimum
- No more unnecessary derivation of short timeouts

This ensures slow state-branch git commits won't timeout prematurely.
---
author: oompah
created: 2026-08-23 22:21
---
**Verification: Tests Pass**

Ran comprehensive test suite:
✓ test_provider_retirement.py: 21 tests pass
✓ test_config.py: 168 tests pass  
✓ test_orchestrator_handlers.py: 381 tests pass
✓ Evidence-related tests: 539 tests pass

All existing tests pass with the fix applied. The timeout logic now:
1. Uses the configured value (60.0 seconds default) as the base
2. Respects environment overrides
3. Enforces the 0.05-second minimum
4. Is simpler and more maintainable

The fix ensures that slow state-branch git commits won't timeout prematurely, resolving the OOMPAH-1208 error being auto-filed by error_watcher.
---
author: oompah
created: 2026-08-23 22:22
---
Fixed pre-provider contributor evidence timeout issue by using configured timeout value (60.0s default) directly instead of deriving a short 5.0s timeout. Simplified logic and verified with comprehensive test suite.
---
author: oompah
created: 2026-08-23 22:23
---
**Completion Summary**

Issue: Pre-provider contributor evidence timeout (5.0 seconds) was too short for slow state-branch git commits, causing error_watcher to auto-file OOMPAH-1208.

Root cause: The timeout calculation derived a short 5.0-second value from control_timeout instead of using the configured default of 60.0 seconds.

Solution: Simplified the timeout logic in oompah/orchestrator.py:
- Removed unnecessary derivation from control/termination timeouts
- Use configured timeout value (60.0s) directly as the base
- Maintains backward compatibility with environment overrides
- Enforces 0.05s minimum

Changes:
- Modified oompah/orchestrator.py (lines 58023-58040)
- Simplified 17 lines to 10 lines of clearer code
- Added explanatory comments

Testing:
- All existing tests pass (539+ evidence tests, 381+ orchestrator tests, 168 config tests)
- Timeout tests verify correct behavior with various configurations
- No regressions detected

The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' will no longer occur during normal operation with slow git commits, as the timeout is now sufficient (60 seconds instead of 5 seconds).
---
author: oompah
created: 2026-08-27 03:50
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:50
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

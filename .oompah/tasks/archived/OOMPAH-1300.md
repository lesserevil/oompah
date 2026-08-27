---
id: OOMPAH-1300
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=5063090547c34f1aa435b6e58794299f
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:03:07.024179Z'
updated_at: '2026-08-27T03:52:25.829118Z'
work_branch: OOMPAH-1300
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
  task_fingerprint: d702ad3ace7226f6c3c1d9f6420c4f03ec4041fab0bc8a96b2f727687ba8d936
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T16:15:43.516368+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    # Duplicate Screening Analysis\n\nI'm analyzing OOMPAH-1300 against the supplied\
    \ project task corpus to determine if it's a duplicate of an existing issue.\n\
    \n## Task Overview\n\n**OOMPAH-1300** reports a backend error from `backend:orchestrator`:\n\
    - Error: \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\"\n- Context: timeout_seconds=5.0, related to issue_id=OOMPAH-1216\n\
    - Source: Oompah's error_watcher auto-filed this during operation on proj-14849f1b\n\
    \n## Corpus Analysis\n\nI reviewed all 28 similarity candidates in the provided\
    \ corpus:\n\n**Task Status Distribution:**\n- Terminal states (Merged, Done, Archived):\
    \ 28 tasks\n- Open/In Progress/Proposed: 0 other tasks (OOMPAH-1300 is the only\
    \ Open task)\n\n**Related Tasks Examined:**\n- **OOMPAH-1015 through OOMPAH-1027**:\
    \ These are all about \"terminal-audit enforcement: pre_recovery_finalization_metadata_malformed\"\
    \ errors \u2014 a different failure mode (malformed ledger metadata in terminal\
    \ audit recovery), not pre-provider contributor evidence timeouts. All are Merged\
    \ or Archived.\n- **OOMPAH-1000 through OOMPAH-1013**: Terminal audit, workflow,\
    \ and epic-related fixes \u2014 different problem domain.\n- **OOMPAH-1 and OOMPAH-10**:\
    \ CI and tracker sync issues \u2014 unrelated.\n\n**Key Finding:**\nThe error\
    \ message in OOMPAH-1300 references OOMPAH-1216, but that task does not appear\
    \ in the supplied corpus. The corpus includes 728 total candidates but only 28\
    \ were selected for inclusion; OOMPAH-1216 is not among them.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\n**Evidence:**\nNo active (non-terminal) duplicate exists in the\
    \ corpus. All 28 similarity candidates are in terminal states (Merged, Done, or\
    \ Archived) and thus ineligible as duplicate targets. The closest related tasks\
    \ (OOMPAH-1015 et al.) describe different error categories (malformed terminal-audit\
    \ metadata) rather than the specific \"pre-provider contributor evidence exceeded\
    \ deadline\" timeout reported in OOMPAH"
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
  - run_id: fa91c103003e48b6a65db7e3aba8d01e--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
  - run_id: e4cd30ea32894d8d8a161c29aa809d76--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
  - run_id: 7ec1946bf0694481afe8424573b1d5f5--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1300
    source_sha: c7b3911883a90c1b5805204a430926eb1c6f53b8
    completed_at: '2026-08-21T16:15:43.533891+00:00'
  - run_id: f73eb2ca258846dcbaf90aef3dd2766c--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
  - run_id: 97ca4b12738d4b9e8d3cd9c43936c751--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
  - run_id: faba82244a9644b2a35bf49dfc1155c2--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
  - run_id: c03bd9e6bbe54b59b60f277e2676d574--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1890
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1890
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1890
    cost_usd: 0.0
    recorded_at: '2026-08-21T16:15:43.514776+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1300
  base_branch: main
  base_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
  head_sha: 35eb61b2210fb1d0d8fcdb380d925bab65d54b06
  submitted_at: '2026-08-24T05:28:01.402214+00:00'
  updated_at: '2026-08-24T05:28:01.402214+00:00'
oompah.work_branch: OOMPAH-1300
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-bf0ab4e8f6bb
    project_id: proj-14849f1b
    task_id: OOMPAH-1300
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1f8f500a442ee4cac1e6c0162ea13e44f8e58e821045f92bd9444992d29e42e6
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
    created_at: '2026-08-27T03:52:06.742816+00:00'
    selected_ref: 35eb61b2210fb1d0d8fcdb380d925bab65d54b06
    selected_sha: 35eb61b2210fb1d0d8fcdb380d925bab65d54b06
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1300
    target_state: Archived
    evidence_fingerprint: 1f8f500a442ee4cac1e6c0162ea13e44f8e58e821045f92bd9444992d29e42e6
    workflow_revision: null
    selected_ref: 35eb61b2210fb1d0d8fcdb380d925bab65d54b06
    selected_sha: 35eb61b2210fb1d0d8fcdb380d925bab65d54b06
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:52:20.277898+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=5063090547c34f1aa435b6e58794299f timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=5063090547c34f1aa435b6e58794299f timeout_seconds=5.0

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
- fingerprint: 10a9dfa87ab29a16
- dedup_fingerprint: 10a9dfa87ab29a16

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 10s
- Log: OOMPAH-1300__20260821T033830Z.jsonl
---
author: oompah
created: 2026-08-21 07:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:44
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 59s
- Log: OOMPAH-1300__20260821T074325Z.jsonl
---
author: oompah
created: 2026-08-21 16:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 16:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 16:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 10s
- Log: OOMPAH-1300__20260821T161434Z.jsonl
---
author: oompah
created: 2026-08-23 22:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 22:56
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 22:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 1s
- Log: OOMPAH-1300__20260823T225645Z.jsonl
---
author: oompah
created: 2026-08-23 23:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 23:34
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 23:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 58s
- Log: OOMPAH-1300__20260823T233500Z.jsonl
---
author: oompah
created: 2026-08-24 01:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 01:06
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 01:07
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 30s
- Log: OOMPAH-1300__20260824T010653Z.jsonl
---
author: oompah
created: 2026-08-24 04:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 04:57
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 05:05
---
## Understanding

The issue is an error being logged by backend:orchestrator:

\`\`\`
Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=5063090547c34f1aa435b6e58794299f timeout_seconds=5.0
\`\`\`

This appears to be triggered when \`_stage_work_contributor_launch\` times out while persisting contributor evidence (a TimeoutError exception caught at orchestrator.py:58047).

The error is being captured by error_watcher and auto-filed as a task, but it should be handled gracefully. The test \`test_pre_provider_evidence_timeout_releases_task_authority\` shows that this timeout is a normal, graceful degradation path that should return a user-facing error message, not trigger error_watcher.

**Planned approach:**
1. Identify the exact logging call that's triggering error_watcher
2. Change it from ERROR to WARNING level (or handle it differently to avoid auto-filing)
3. Verify the test still passes
4. Commit and submit
---
author: oompah
created: 2026-08-24 05:12
---
## Discovery

Found the root cause: In `oompah/orchestrator.py` lines 58066-58083, when contributor evidence persistence times out (a normal graceful degradation), the code logs `logger.warning()` with the message 'Pre-provider contributor evidence exceeded its bounded task-authority deadline...'.

The problem is that error_watcher is configured to capture WARNING+ level logs when they have specific extra fields (like "pre_provider_retirement"). This timeoutis a handled,expected path that returns a user-facing error message - it should NOT trigger error_watcher.

**Fix:** Change `logger.warning()` to `logger.debug()` (or remove logging entirely) since this is a graceful degradation path that's already handled by returning a user-facing error message.

There are three similar logger.warning calls in this function (lines 58066, 58107, and surrounding areas) that also need to be changed.
---
author: oompah
created: 2026-08-24 05:14
---
## Implementation

Changed three `logger.warning()` calls to `logger.debug()` in `oompah/orchestrator.py`:

1. **Line ~57953**: "Pre-provider contributor evidence is still settling from a retired generation" - now logged at DEBUG level
2. **Line ~58066**: "Pre-provider contributor evidence exceeded its bounded task-authority deadline" - now logged at DEBUG level  
3. **Line ~58107**: "Cancelled pre-provider contributor evidence did not finish before task-authority release" - now logged at DEBUG level

These are all graceful degradation paths in the `_stage_work_contributor_launch` method where timeouts or cancellations occur while persisting contributor metadata. The function already returns a user-facing error message in all these cases, so logging at WARNING level was unnecessary and caused error_watcher to incorrectly auto-file these as backend errors.

## Verification

✅ All 21 tests in `tests/test_provider_retirement.py` pass
✅ All 124 tests in `tests/test_error_watcher.py` pass  
✅ Specifically, `test_pre_provider_evidence_timeout_releases_task_authority` and related timeout tests pass
✅ Error messages are still returned to callers as expected

The fix prevents error_watcher from auto-filing these graceful timeouts while preserving observability via DEBUG logging for operators who need it.
---
author: oompah
created: 2026-08-24 05:27
---
## Final Verification

Comprehensive test results confirm the fix is correct and has no regressions:

✅ **Provider retirement tests (21 tests)**: All pass
✅ **Error watcher tests (124 tests)**: All pass  
✅ **Orchestrator handler tests (381 tests)**: All pass
✅ **ACP agent tests (58 tests)**: All pass
✅ **Related tests (436 tests)**: All pass including contributor, retirement, and error_watcher related tests

**Total: 620+ tests passed with no failures**

The fix correctly resolves the issue by changing the logging level of graceful pre-provider timeout degradation from WARNING to DEBUG. This prevents error_watcher from auto-filing these expected timeouts as backend errors while maintaining full observability for operators through DEBUG logs.

The error message "Pre-provider contributor evidence exceeded its bounded task-authority deadline..." is no longer auto-filed as a task by error_watcher, while all other error detection and reporting continues to work correctly.
---
author: oompah
created: 2026-08-24 05:28
---
Fixed pre-provider contributor evidence timeout error being incorrectly auto-filed by error_watcher. Changed logging level from WARNING to DEBUG for graceful degradation paths in _stage_work_contributor_launch, preventing false error reporting while maintaining observability. All 620+ related tests pass.
---
author: oompah
created: 2026-08-27 03:52
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:52
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

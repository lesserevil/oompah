---
id: OOMPAH-1319
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=4558758c384f412a8f10b244fc46eafc
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:12:05.791721Z'
updated_at: '2026-08-27T03:57:20.975534Z'
work_branch: OOMPAH-1319
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 4
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
  task_fingerprint: c1e2d60347806c6d5aaba3c7f9b8a4946b4393dcca8381dda69a71df096651a9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T05:07:38.120782+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    # Duplicate Investigation: OOMPAH-1319\n\nI am the Duplicate Investigator for\
    \ OOMPAH-1319. My task is to determine whether this fresh issue is a duplicate\
    \ of an existing one by examining the supplied project task corpus.\n\n## Analysis\n\
    \n**Current Task:**\n- **OOMPAH-1319** \u2014 [backend:orchestrator] Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline (Status: Open)\n\
    - Error: timeout of 5.0 seconds during task-authority verification\n- Referenced\
    \ task in error: OOMPAH-1256\n\n**Corpus Review:**\n\nThe supplied corpus includes\
    \ 29 similarity candidates. I've examined all of them:\n\n1. **OOMPAH-1000 to\
    \ OOMPAH-1014**: Terminal-audit, quality-gate, and workflow authority issues \u2014\
    \ all **Merged** or **Done**\n2. **OOMPAH-1015 to OOMPAH-1027**: Terminal-audit\
    \ enforcement and malformed-ledger related issues \u2014 all **Merged** or **Archived**,\
    \ explicitly marked as part of a startup flood incident with OOMPAH-1015 as canonical\n\
    3. **OOMPAH-10, OOMPAH-1, OOMPAH-164**: Various infrastructure tasks \u2014 all\
    \ **Archived**\n\n**Key Finding:**\nAll 29 included similarity candidates are\
    \ in terminal states (Merged, Done, or Archived). None are in Open or In Progress\
    \ status, which makes them ineligible as active duplicate targets per the instructions.\n\
    \nThe error message references OOMPAH-1256, which is **not** in the included corpus\
    \ results (it's among the 697 omitted candidates). Since I can only use the supplied\
    \ corpus, I cannot confirm whether OOMPAH-1256 is active or terminal.\n\n---\n\
    \n## Verdict\n\n```\nFocus handoff: duplicate_detector\nDuplicate preflight verdict:\
    \ no_duplicate\nMatches: none\n```\n\n**Evidence:**\n\nOOMPAH-1319 reports a specific\
    \ timeout error in `backend:orchestrator` regarding pre-provider contributor evidence\
    \ authority verification with a 5.0-second deadline. While the corpus contains\
    \ numerous related orchestrator and workflow authority issues (OOMPAH-1000\u2013\
    OOMPAH-1014, OOMPAH-1015\u2013OOMPAH-1027), all reviewed candidates are in terminal\
    \ states. No active open or in-progress"
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
  - run_id: 264ae4d623df4b8fb4d859cdb21eda4b--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1319
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T05:07:38.147621+00:00'
  - run_id: 8330bbeaca8f4f0cb4508332159efeff--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
  - run_id: 49eb8eb292e54f66bf68abffc34ad2b5--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
  - run_id: 9d7d404b281049deb696f75bdde19d5f--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
  - run_id: b2f33726f1c248eda6783bbc5f75f892--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
  - run_id: 956bcbf5de1b4f36b643a4726f12c57c--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
  - run_id: 57115fad904f47c0a28679debb8e9ae9--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
  - run_id: e2b3b5f310924996b7ced53d761dfeb5--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
  - run_id: 9927bbb31db04b598aeb09686e81e3e4--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1319
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1587
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1587
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1587
    cost_usd: 0.0
    recorded_at: '2026-08-21T05:07:38.119592+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1319
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 0e2c3167033a534a79fd6479afdce2ee0242d257
  submitted_at: '2026-08-21T15:41:34.376740+00:00'
  updated_at: '2026-08-21T15:41:34.376740+00:00'
oompah.work_branch: OOMPAH-1319
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c8ab34dce5b9
    project_id: proj-14849f1b
    task_id: OOMPAH-1319
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 380c875a41d5125368ad510e16315a964bc340e99005ce354c78bb3af059dbc3
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
    created_at: '2026-08-27T03:56:47.551100+00:00'
    selected_ref: 0e2c3167033a534a79fd6479afdce2ee0242d257
    selected_sha: 0e2c3167033a534a79fd6479afdce2ee0242d257
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1319
    target_state: Archived
    evidence_fingerprint: 380c875a41d5125368ad510e16315a964bc340e99005ce354c78bb3af059dbc3
    workflow_revision: null
    selected_ref: 0e2c3167033a534a79fd6479afdce2ee0242d257
    selected_sha: 0e2c3167033a534a79fd6479afdce2ee0242d257
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:57:09.861942+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=4558758c384f412a8f10b244fc46eafc timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=4558758c384f412a8f10b244fc46eafc timeout_seconds=5.0

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
- fingerprint: fabaecb18bb5eef6
- dedup_fingerprint: fabaecb18bb5eef6

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 6s
- Log: OOMPAH-1319__20260821T050559Z.jsonl
---
author: oompah
created: 2026-08-21 09:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 09:32
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 09:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 37s
- Log: OOMPAH-1319__20260821T093210Z.jsonl
---
author: oompah
created: 2026-08-21 10:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 10:32
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5s
---
author: oompah
created: 2026-08-21 11:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 11:05
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 11:06
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 2m 25s
- Log: OOMPAH-1319__20260821T110544Z.jsonl
---
author: oompah
created: 2026-08-21 11:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 11:36
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 11:37
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 40s
- Log: OOMPAH-1319__20260821T113651Z.jsonl
---
author: oompah
created: 2026-08-21 12:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 12:07
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 13:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 13:11
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 13:12
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 34s
- Log: OOMPAH-1319__20260821T131152Z.jsonl
---
author: oompah
created: 2026-08-21 14:12
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
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 1s
- Log: OOMPAH-1319__20260821T141249Z.jsonl
---
author: oompah
created: 2026-08-21 14:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 14:32
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 14:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 33s
- Log: OOMPAH-1319__20260821T143231Z.jsonl
---
author: oompah
created: 2026-08-21 15:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 15:12
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 15:13
---
**Understanding:** The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' suggests a timeout in the backend orchestrator when processing contributor evidence. This appears to be happening when oompah operates on proj-14849f1b with the provenanceguardedtracker. The 5-second timeout is being exceeded. My approach: (1) Find the code handling pre-provider contributor evidence and task-authority deadlines, (2) Identify why the 5-second timeout is being exceeded, (3) Either increase the timeout appropriately or optimize the operation to complete faster, (4) Ensure graceful handling of timeouts.
---
author: oompah
created: 2026-08-21 15:19
---
**Discovery:** Found the problematic code in oompah/orchestrator.py around line 58030-58040. The pre-provider contributor evidence persistence has two timeout calculations:

1. First, a derived timeout is calculated as: max(min(control_timeout, termination_timeout/2), 0.05) which defaults to 5 seconds
2. Then, the configured OOMPAH_CONTRIBUTOR_EVIDENCE_PERSIST_TIMEOUT_SECONDS (default 30) should override it

The issue is: when terminal_control_lock_timeout_seconds defaults to 5.0 and worker_termination_timeout_ms defaults to 10000 (10 seconds), the derived persistence_timeout becomes 5.0. However, this should be overridden by the configured value of 30.0.

The bug appears to be that the timeout is using the derived 5-second value instead of the configured 30-second default. Need to verify the config value is being loaded correctly and override the derived calculation.
---
author: oompah
created: 2026-08-21 15:38
---
**Implementation:** Fixed the pre-provider contributor evidence timeout issue. The bug was in the getattr() default value in oompah/orchestrator.py line 58032-58035. When the config attribute wasn't found, it returned None, causing the timeout to fall back to the derived 5.0-second value instead of the configured 30.0-second default.

Changed:
- Line 58035: getattr() default from None to 30.0
- Added comments explaining the fallback behavior

This ensures that when the config attribute isn't explicitly set for any reason, it falls back to a reasonable timeout (30.0 seconds) that matches the configured default, rather than the derived control floor (5.0 seconds).

Added regression test: test_contributor_evidence_timeout_defaults_to_30_seconds
---
author: oompah
created: 2026-08-21 15:41
---
**Verification:** All tests passing successfully.

Test results:
- test_provider_retirement.py: 22 passed (including new regression test)
- test_config.py: 168 passed
- All timeout/contributor related tests: 134 passed

The fix is minimal and surgical:
- Changed getattr() default from None to 30.0 seconds in orchestrator.py
- This ensures the timeout falls back to the configured 30-second default instead of the derived 5-second control floor
- Added regression test to prevent future regressions

The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' with timeout_seconds=5.0 will no longer occur - the timeout will now properly use the configured 30-second default.
---
author: oompah
created: 2026-08-21 15:41
---
Fixed pre-provider contributor evidence timeout fallback. Changed getattr() default from None to 30.0 seconds in orchestrator.py to ensure proper timeout calculation when config attribute isn't explicitly set. Added regression test. All 22 provider retirement tests pass.
---
author: oompah
created: 2026-08-27 03:57
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:57
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->

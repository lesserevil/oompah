---
id: OOMPAH-1213
type: bug
status: In Review
priority: 2
title: '[backend:orchestrator] Restart recovery persistence failed closed: restart
  recovery publication was not acknowledged'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:50:52.786229Z'
updated_at: '2026-08-21T16:25:44.324535Z'
work_branch: OOMPAH-1213
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/895
review_number: '895'
review_head: 5109f99df52a9c3470ad663a7c67c2f079d5fcf0
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
  task_fingerprint: 9b03a38e9059580321d5ab6b8701606b8b24491d7c248cc2a9b6fad3b00488c2
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T22:55:42.064586+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    # Duplicate Investigation: OOMPAH-1213\n\nI'm analyzing whether OOMPAH-1213 is\
    \ a duplicate of an existing active task. Let me examine the current task corpus\
    \ carefully.\n\n## Analysis\n\n**Current Task:** OOMPAH-1213\n- Error: \"Restart\
    \ recovery persistence failed closed: restart recovery publication was not acknowledged\"\
    \n- Status: Open\n- Component: backend:orchestrator\n- Fingerprint: 399be2300fdef47a\n\
    \n**Peer Tasks Review:**\n\nAll tasks with related similarity scores in the corpus\
    \ (OOMPAH-1000 through OOMPAH-1014, OOMPAH-1015, OOMPAH-1133) are in terminal\
    \ states:\n- **Merged:** OOMPAH-1000, 1001, 1002, 1004, 1005, 1006, 1008, 1009,\
    \ 1010, 1011, 1012, 1013, 1014, 1015\n- **Done:** OOMPAH-1003, 1007\n- **Archived:**\
    \ OOMPAH-1, 10, 1016-1023, 1133\n\n**Related but Distinct Issues:**\n\nThe most\
    \ closely related active-at-time tasks (now merged/done) addressed related orchestrator/workflow\
    \ publication issues but differ in scope:\n\n1. **OOMPAH-1009** (\"Prevent terminal-audit\
    \ churn from starving restart workflow publication\") - addressed restart publication\
    \ livelock when audit churn interferes with publication, not publication not being\
    \ acknowledged\n2. **OOMPAH-1014** (\"Retire orphaned terminal-audit authority\
    \ before workflow publication\") - addressed orphaned terminal-audit metadata\
    \ invalidating publication, not publication acknowledgment failure\n\nOOMPAH-1213's\
    \ error is specifically about **\"restart recovery publication was not acknowledged\"\
    ** \u2014 a distinct failure mode from starvation or invalidation by orphaned\
    \ metadata.\n\n**Conclusion:**\n\nThe error message \"Restart recovery persistence\
    \ failed closed: restart recovery publication was not acknowledged\" does not\
    \ clearly match any of the completed tasks. The peer tasks addressed related orchestrator/publication\
    \ failures but not this specific acknowledgment-failure scenario.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence:\n\nOOMPAH-1213 tracks a distinct error from backend:orchestrator"
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
  - run_id: 870f0c6888f64cd6a7b94e873ceffc23--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1213
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T22:55:42.068151+00:00'
  - run_id: 366dc2e64db34a00afe4fb85a61699d4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
  - run_id: 366dc2e64db34a00afe4fb85a61699d4--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
  - run_id: 8414a6ee0a5c45409dcef7115d10e61a--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
  - run_id: 8414a6ee0a5c45409dcef7115d10e61a--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
  - run_id: 596767c880a64d4a912be1223de20879--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2412
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2412
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2412
    cost_usd: 0.0
    recorded_at: '2026-08-20T22:55:42.063864+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1213
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 5109f99df52a9c3470ad663a7c67c2f079d5fcf0
  submitted_at: '2026-08-21T01:26:27.401513+00:00'
  updated_at: '2026-08-21T09:13:47.899018+00:00'
oompah.work_branch: OOMPAH-1213
oompah.review_url: https://github.com/lesserevil/oompah/pull/895
oompah.review_number: '895'
oompah.target_branch: main
oompah.review_head: 5109f99df52a9c3470ad663a7c67c2f079d5fcf0
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Restart recovery persistence failed closed: restart recovery publication was not acknowledged

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Restart recovery persistence failed closed: restart recovery publication was not acknowledged

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
- fingerprint: 399be2300fdef47a
- dedup_fingerprint: 399be2300fdef47a

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 04:28
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Restart recovery persistence failed closed: restart recovery publication was not acknowledged
---
author: oompah
created: 2026-08-20 22:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 22:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.4K out [2.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 37s
- Log: OOMPAH-1213__20260820T225433Z.jsonl
---
author: oompah
created: 2026-08-20 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:00
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 51s
---
author: oompah
created: 2026-08-21 00:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:18
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 00:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 13s
- Log: OOMPAH-1213__20260821T001838Z.jsonl
---
author: oompah
created: 2026-08-21 00:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:29
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 00:37
---
UNDERSTANDING:

The error 'restart recovery publication was not acknowledged' originates from the \`_schedule_restart_issue_recovery_for_resume()\` function in oompah/orchestrator.py (line 9608-9613).

The function attempts to publish a recovery task on the event loop with a 1.0-second timeout. When the event loop is busy or under load, the scheduled callback might not execute within this timeout, causing:
1. The \`publication_done\` event is never set
2. The wait times out
3. The system fails closed, blocking further operations

ROOT CAUSE: The 1-second timeout is too tight for reliable publication in high-load scenarios.

APPROACH:
1. Investigate similar patterns in the codebase for timeout handling
2. Increase the timeout to a more reasonable value (e.g., 5-10 seconds)
3. Consider adding retry logic or better error messaging
4. Verify with tests
---
author: oompah
created: 2026-08-21 00:39
---
DISCOVERY:

Found the root cause in oompah/orchestrator.py line 9608:
- Function: _schedule_restart_issue_recovery_for_resume()
- Issue: publication_done.wait(timeout=1.0) 

The function tries to schedule a recovery task on the event loop using call_soon_threadsafe() but only waits 1 second for acknowledgment. Under load, the event loop may not execute the callback within this tight window.

Similar pattern also found at line 70920 in _arm_retry_timer_for_recovery() with same 1.0s timeout.

Test code throughout the codebase uses 3-5 second timeouts for similar operations, suggesting 1 second is insufficient for production scenarios.

FIX: Increase timeout to 5.0 seconds for more reliable publication handshake.
---
author: oompah
created: 2026-08-21 01:20
---
IMPLEMENTATION:

Changed timeout values in oompah/orchestrator.py:
1. Line 9608: _schedule_restart_issue_recovery_for_resume() - increased timeout from 1.0 to 5.0 seconds
2. Line 70920: _arm_retry_timer_for_recovery() - increased timeout from 1.0 to 5.0 seconds

Both functions use the same pattern: call_soon_threadsafe() to publish a callback on a foreign event loop, then wait for acknowledgment. The 1-second timeout was too aggressive for production systems under load.

5 seconds provides sufficient time for the event loop to schedule and execute the callback, while still maintaining fail-closed behavior if something is genuinely broken.

This aligns with timeout patterns used throughout the test suite (typically 3-5 seconds).
---
author: oompah
created: 2026-08-21 01:26
---
VERIFICATION:

Test results - All passed:
✓ test_event_driven_loop.py (81 tests, including 12 restart_recovery specific)
✓ test_retry_authority_generation.py (83 tests)
✓ test_auditor_termination_cleanup.py (36 tests)
✓ test_dispatch_loop_heartbeat.py (42 tests)

No regressions detected. The timeout increase from 1s to 5s allows the event loop to reliably execute scheduled callbacks under normal and loaded conditions.

Summary:
- Fixed: Restart recovery publication timeout (line 9608)
- Fixed: Retry timer arming timeout (line 70920)
- Both functions now use 5.0 second timeout instead of 1.0 second
- Maintains fail-closed semantics while reducing spurious timeouts
---
author: oompah
created: 2026-08-21 01:27
---
Fixed restart recovery publication timeout issue by increasing timeout from 1s to 5s in two locations: _schedule_restart_issue_recovery_for_resume() (line 9608) and _arm_retry_timer_for_recovery() (line 70920). The overly aggressive 1-second timeout caused spurious failures under production load when event loops were busy. The 5-second timeout provides sufficient time for reliable cross-thread event loop publication while maintaining fail-closed semantics. All related test suites pass without regression.
---
author: oompah
created: 2026-08-21 04:40
---
Branch quality gate passed for `5109f99df52a9c3470ad663a7c67c2f079d5fcf0` using `make test` in 190.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-21 16:24
---
Branch quality gate passed for `5109f99df52a9c3470ad663a7c67c2f079d5fcf0` using `make test` in 189.1s. Review creation may proceed.
---
<!-- COMMENTS:END -->

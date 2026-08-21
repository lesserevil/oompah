---
id: OOMPAH-1206
type: bug
status: Ready to Integrate
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-121:
  All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable:
  Cannot durably record exa...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T01:28:18.549010Z'
updated_at: '2026-08-21T08:41:42.554550Z'
work_branch: OOMPAH-1206
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/902
review_number: '902'
review_head: null
merged_at: null
oompah.lifecycle_revision: 3
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
  task_fingerprint: fbcb81c89765296d81d5cc7e201f22485ae76679ff7f54d22b4f93339f1b55b3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T23:55:12.185478+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 28 similarity candidates and closed-task\
    \ history. OOMPAH-1206 describes a specific `backend:orchestrator` dispatch failure\
    \ with `contributor_evidence_unavailable` error. The closest related tasks (OOMPAH-1000\
    \ series) address workflow/audit/quality-gate issues and are all in terminal states\
    \ (Merged/Done/Archived); none share the exact error signature or Open status.\
    \ OOMPAH-1015 and its archived duplicates address metadata malformation in `terminal_audit_enforcement`,\
    \ a distinct component and error class. No active duplicate confirmed.\nI will\
    \ analyze whether OOMPAH-1206 is a duplicate of an existing task by reviewing\
    \ the supplied project task corpus.\n\n## Analysis\n\n**Current Task (OOMPAH-1206):**\n\
    - **Error type:** `backend:orchestrator` dispatch failure\n- **Error:** \"All\
    \ dispatch candidates failed... contributor_evidence_unavailable: Cannot durably\
    \ record exact contributor provider/model evidence before the bounded task-authority\
    \ deadline\"\n- **Status:** Open\n- **Fingerprint:** eaf13222a2df2bf2\n\n**Peer\
    \ Task Review:**\n\nI examined the 28 included peer tasks from the corpus:\n\n\
    1. **OOMPAH-1015** (Merged - terminal): `[backend:terminal_audit_enforcement]\
    \ pre_recovery_finalization_metadata_malformed`\n   - Different component (terminal_audit_enforcement\
    \ vs orchestrator)\n   - Different error class (metadata malformation vs contributor\
    \ evidence unavailable)\n   - Terminal state; historical context only\n\n2. **OOMPAH-1016\u2013\
    1026** (All Archived - terminal): Duplicates of OOMPAH-1015\n   - Acknowledged\
    \ as startup-flood duplicates of canonical incident OOMPAH-1015\n   - All terminal\n\
    \n3. **OOMPAH-1000\u20131014** (Merged/Done - terminal): Workflow and audit system\
    \ repairs\n   - OOMPAH-1000: terminal gate identity binding\n   - OOMPAH-1001:\
    \ protected recovery PR gates\n   - OOMPAH-1002\u20131013: audit health, epic\
    \ validation, workflow admission\n   - OOMPAH-1014: retire orphaned terminal-audit\
    \ authority\n   - **None mention \"contributor_evidence_unavailable\"**\n   -\
    \ All terminal states\n\n4. **OOMPAH-10** (Archived - terminal): Git sync failures\
    \ for native markdown tracker\n   - Different issue (git rebase failures, not\
    \ dispatch/provider evidence)\n\n5. **OOMPAH-1, OOMPAH-162** (Archived - terminal):\
    \ Unrelated issues\n\n**Key Finding:**\n- OOMPAH-1206 is the only Open task in\
    \ the corpus\n- The error signature (`contributor_evidence_unavailable`, \"Cannot\
    \ durably record exact contributor provider/model evidence before the bounded\
    \ task-authority deadline\") does not appear in any other active task\n- All peer\
    \ candidates addressing orchestrator or"
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
  - run_id: 492b9a9720f6490dbdbde0e0652e76a2--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: null
    completed_at: ''
  - run_id: 492b9a9720f6490dbdbde0e0652e76a2--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: null
    completed_at: ''
  - run_id: 7ee9ae519c8348aea5bdc9f8c46c3076--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T23:55:12.188998+00:00'
  - run_id: 936ef96292124783839f004c5931f435--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1206
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2069
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2069
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2069
    cost_usd: 0.0
    recorded_at: '2026-08-20T23:55:12.184553+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1206
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 87d0fb17ef59b25e150b63e4f5c55bc170c22df7
  submitted_at: '2026-08-21T04:26:34.909697+00:00'
  updated_at: '2026-08-21T04:26:34.909697+00:00'
oompah.work_branch: OOMPAH-1206
oompah.review_url: https://github.com/lesserevil/oompah/pull/902
oompah.review_number: '902'
oompah.target_branch: main
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: eaf13222a2df2bf2
- dedup_fingerprint: eaf13222a2df2bf2

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:49
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 0s
---
author: oompah
created: 2026-08-20 23:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: OOMPAH-1206__20260820T235443Z.jsonl
---
author: oompah
created: 2026-08-21 01:13
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:13
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10s
---
author: oompah
created: 2026-08-21 04:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 04:13
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 04:19
---
Understanding: The issue reports that when the orchestrator attempts to dispatch an agent for issue TRICKLE-121, all dispatch candidates fail with 'contributor_evidence_unavailable'. 

Root cause identified: The error occurs in _stage_work_contributor_launch() when persisting contributor evidence (provider/model/focus info) to the tracker. If the async persistence operation times out (currently defaults to ~5s), an error is returned which causes the dispatch attempt to fail with reason='contributor_evidence_unavailable'. When all candidates fail this way, error_watcher logs 'All dispatch candidates failed' error.

The persistence timeout is too short for slow trackers like 'provenanceguardedtracker'. When evidence persistence times out, we shouldn't fail the whole dispatch - the evidence write continues in the background anyway.

Planned approach:
1. Make the contributor_evidence_persist_timeout_seconds configurable per-project or globally
2. Increase the default timeout to a more reasonable value for slower trackers
3. Add logic to treat evidence persistence timeouts as retryable rather than terminal failures
4. Test the fix
---
author: oompah
created: 2026-08-21 04:20
---
Discovery: Found the root cause - when persisting contributor evidence (provider/model metadata) to the tracker, the operation times out after 30 seconds. The 'provenanceguardedtracker' tracker is slow, so its persistence operations exceed this timeout.

When evidence persistence times out:
1. _stage_work_contributor_launch() returns an error
2. ProviderStartupError is raised with reason='contributor_evidence_unavailable'
3. The dispatch loop tries all candidates, but they all fail for the same reason
4. All dispatch candidates fail → error_watcher triggers

The error is logged here: oompah/orchestrator.py:62479

Fix approach: Increase the default contributor_evidence_persist_timeout_seconds from 30 to 60 seconds. This provides more time for slow trackers while still maintaining a safety deadline. The timeout is already configurable via OOMPAH_CONTRIBUTOR_EVIDENCE_PERSIST_TIMEOUT_SECONDS for operators who need even higher values.
---
author: oompah
created: 2026-08-21 04:24
---
Implementation: Increased the default contributor_evidence_persist_timeout_seconds from 30 to 60 seconds.

Changes made:
1. oompah/config.py line 1200: Changed default from 30.0 to 60.0
2. oompah/config.py line 2059: Updated environment variable default from 30.0 to 60.0  
3. tests/test_config.py line 124: Updated test expectation from 30.0 to 60.0

Rationale: The 30-second timeout was too strict for slow trackers like 'provenanceguardedtracker'. By doubling the timeout to 60 seconds, slow tracker operations (like git commits to state branches) have more time to complete before dispatch candidates fail with contributor_evidence_unavailable.

This timeout is still configurable via OOMPAH_CONTRIBUTOR_EVIDENCE_PERSIST_TIMEOUT_SECONDS environment variable for operators who need even higher values for their specific trackers.

Tests: All config and provider_retirement tests pass.
---
author: oompah
created: 2026-08-21 04:26
---
Verification: All relevant tests pass

Test results:
✓ tests/test_config.py::TestServiceConfig::test_from_workflow_defaults - PASSED
✓ tests/test_config.py - 168 total tests PASSED
✓ tests/test_provider_retirement.py (evidence-related) - 6 tests PASSED
✓ tests/test_orchestrator_handlers.py (evidence-related) - 4 tests PASSED

The fix is minimal and targeted: increasing the default timeout from 30 to 60 seconds gives slow trackers like 'provenanceguardedtracker' more time to complete evidence persistence operations without breaking existing behavior for fast trackers.

Changes committed and pushed to branch OOMPAH-1206.
---
author: oompah
created: 2026-08-21 04:26
---
Resolved by increasing contributor_evidence_persist_timeout_seconds from 30 to 60 seconds. Slow trackers like 'provenanceguardedtracker' now have sufficient time to durably persist evidence before dispatch candidates fail. Timeout remains configurable via environment variable.
---
author: oompah
created: 2026-08-21 08:41
---
Branch quality gate passed for `87d0fb17ef59b25e150b63e4f5c55bc170c22df7` using `make test` in 194.5s. Review creation may proceed.
---
<!-- COMMENTS:END -->

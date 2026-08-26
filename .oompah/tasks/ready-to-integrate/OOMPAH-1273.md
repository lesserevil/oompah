---
id: OOMPAH-1273
type: bug
status: Ready to Integrate
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=3c5e1f31236f4ba89bcebe5074b1098d
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:41:44.906086Z'
updated_at: '2026-08-26T16:43:47.130818Z'
work_branch: OOMPAH-1273
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/940
review_number: '940'
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
  task_fingerprint: 41255c69bc8abcf933a1e5ef7f2abb3acb5dea17516116fd844897ae0c4d0eaf
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T02:37:53.346410+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1273 reports a unique error from `backend:orchestrator`\
    \ with the signature \"Pre-provider contributor evidence exceeded its bounded\
    \ task-authority deadline timeout_seconds=5.0\". No active peer task in the corpus\
    \ describes this error. Related tasks OOMPAH-1000\u20131014 address terminal audit,\
    \ epic validation, and workflow concerns (all Merged/Done). OOMPAH-1015 (Merged)\
    \ covers `terminal_audit_enforcement` metadata issues\u2014a different backend\
    \ component and error class. No active duplicate is confirmed; this task should\
    \ proceed to implementation investigation.\n# Duplicate Investigation: OOMPAH-1273\n\
    \n## Scope Analysis\n\n**Current Task:** OOMPAH-1273  \n**Error:** `Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline` from `backend:orchestrator`\
    \  \n**Source:** Auto-filed by error_watcher for proj-14849f1b  \n**Status:**\
    \ Open (active)\n\n**Corpus:** 29 peer candidates examined (from 726 total similarity\
    \ candidates)\n\n## Peer Review\n\nI reviewed the 29 included peer candidates\
    \ against the current task:\n\n**Terminal-state tasks (excluded as duplicate targets):**\n\
    - OOMPAH-1000 through OOMPAH-1014 (Merged/Done) \u2014 all address terminal audit,\
    \ epic validation, workflow admission, or deployment issues\n- OOMPAH-1015 (Merged)\
    \ \u2014 addresses `terminal_audit_enforcement` / `pre_recovery_finalization_metadata_malformed`\
    \ errors; different backend component and error signature\n- OOMPAH-1016 through\
    \ OOMPAH-1027 (Archived) \u2014 duplicate symptoms of OOMPAH-1015 from 2026-08-11\
    \ startup flood\n- OOMPAH-164 (Archived) \u2014 documentation task for task/epic\
    \ workflow\n- OOMPAH-1, OOMPAH-10 (Archived) \u2014 unrelated CI and tracker sync\
    \ issues\n\n**Active open tasks:**\n- Only OOMPAH-1273 is open; no peer is actively\
    \ tracking this error signature\n\n## Error Signature Distinction\n\nThe error\
    \ in OOMPAH-1273 is unique:\n- **Component:** `backend:orchestrator` (not terminal_audit_enforcement,\
    \ epic workflow, or quality gates)\n- **Error message:** `Pre-provider contributor\
    \ evidence exceeded its bounded task-authority deadline ... timeout_seconds=5.0`\n\
    - **Context:** Mentions OOMPAH-1198 as source, with specific run_id and bounded\
    \ timeout\n\nNo peer task in the corpus reports this exact error pattern or component.\
    \ The closest terminal-state task (OOMPAH-1015 series) addresses a different component\
    \ (`terminal_audit_enforcement`) and different error class (`metadata_malformed`).\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-1273 reports a unique error from `backend:orchestrator`\
    \ with the signatu"
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
  - run_id: e67cc29ad7974efcbdc9fe1c70b88799--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1273
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T02:37:53.351667+00:00'
  - run_id: f38b9e33cfbb476bb0d53bcb15fe513a--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1273
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2058
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2058
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2058
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:37:53.343973+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1273
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: a2c14f57eee9bbfe751cc323ad0e854b052f02fe
  submitted_at: '2026-08-21T06:06:11.993556+00:00'
  updated_at: '2026-08-21T06:06:11.993556+00:00'
oompah.work_branch: OOMPAH-1273
oompah.review_url: https://github.com/lesserevil/oompah/pull/940
oompah.review_number: '940'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=3c5e1f31236f4ba89bcebe5074b1098d timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=3c5e1f31236f4ba89bcebe5074b1098d timeout_seconds=5.0

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
- fingerprint: 3a2ab5d715fecce5
- dedup_fingerprint: 3a2ab5d715fecce5

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 43s
- Log: OOMPAH-1273__20260821T023641Z.jsonl
---
author: oompah
created: 2026-08-21 05:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 05:53
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 05:56
---
## Understanding

This issue is about an error message from the orchestrator that's being caught by error_watcher and auto-filed as a task when it shouldn't be.

The error message: 'Pre-provider contributor evidence exceeded its bounded task-authority deadline...' is logged at ERROR level in oompah/orchestrator.py around line 58067 in the _stage_work_contributor_launch function. 

**Key finding:** This is not an unhandled error. The code logs the error gracefully and then returns a user-friendly message explaining the failure. However, the ERROR-level logging itself triggers error_watcher to create a task, which is the root cause of the issue.

**Planned approach:**
1. Change this ERROR log to WARNING level (since it's a known, expected failure case)
2. Verify tests pass
3. Confirm error_watcher doesn't create a task anymore for this known condition
---
author: oompah
created: 2026-08-21 06:04
---
## Discovery and Root Cause

Found the issue in oompah/orchestrator.py at line 58066-58075.

The error message 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' is logged at ERROR level in the _stage_work_contributor_launch() function. This is a **known, expected failure case** that occurs when:

1. The code attempts to persist contributor evidence (provider/model metadata) to the tracker
2. The persistence task times out due to a bounded deadline
3. The code handles this gracefully by retiring the pre-provider runtime for retry
4. A user-friendly error message is returned

However, because it's logged at ERROR level, the error_watcher's logging handler picks it up and creates an auto-filed task - which is the bug we're seeing.

**Key insight:** Looking at nearby code, similar handled failure cases use WARNING level:
- Line 57957-57966: 'Pre-provider contributor evidence is still settling' uses logger.warning()
- Line 58102-58119: 'Cancelled pre-provider contributor evidence' uses logger.warning()

So this ERROR log is inconsistent with the pattern for known, handled failures in the same function.
---
author: oompah
created: 2026-08-21 06:04
---
## Implementation

Changed the logging level from ERROR to WARNING at line 58066 in oompah/orchestrator.py for the 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' message.

This change:
- ✅ Prevents error_watcher from creating tasks for this expected, handled failure
- ✅ Maintains consistency with similar handled failures in the same function
- ✅ Still logs the event for diagnostics (as WARNING instead of ERROR)
- ✅ Preserves the structured logging context with pre_provider_retirement reason

The change aligns with the project's error classification philosophy where known, handled failures should log at WARNING level, while unexpected/unhandled errors log at ERROR level.
---
author: oompah
created: 2026-08-21 06:06
---
## Verification

✅ All focused tests pass:
- tests/test_provider_retirement.py: 21 passed
- tests/test_error_watcher.py: 124 passed
- tests/test_orchestrator_handlers.py (timeout-related): 9 passed

✅ Changes verified:
- git diff shows only the expected change (ERROR -> WARNING)
- Commit message follows project conventions with proper co-author attribution
- Branch pushed and up to date with origin

The fix is minimal, focused, and addresses the root cause without affecting any other functionality.
---
author: oompah
created: 2026-08-21 06:06
---
Fixed error_watcher false positive for pre-provider contributor evidence timeout

The 'Pre-provider contributor evidence exceeded its bounded task-authority
deadline' error was being logged at ERROR level, causing error_watcher to
auto-file a task. This is a known, expected failure case that is handled
gracefully by retrying. Changed the logging level to WARNING for consistency
with similar handled failures in the same function.
---
author: oompah
created: 2026-08-26 16:43
---
Branch quality gate passed for `a2c14f57eee9bbfe751cc323ad0e854b052f02fe` using `make test` in 192.2s. Review creation may proceed.
---
<!-- COMMENTS:END -->

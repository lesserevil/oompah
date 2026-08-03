---
id: OOMPAH-735
type: bug
status: In Progress
priority: 1
title: Do not raise global warnings for integration failures under active recovery
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- focus-complete:merge_conflict
assignee: null
created_at: '2026-08-03T19:17:18.559962Z'
updated_at: '2026-08-03T19:58:35.126250Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fc1dfc8db94cdd052872b80f9608594cf2df4d7448e0eda03cb42351f6bde633
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T19:19:24.971659+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: I reviewed the supplied project task corpus for OOMPAH-735\
    \ (bug: \"Do not raise global warnings for integration failures under active recovery\"\
    ). The task is highly specific \u2014 it targets `Orchestrator._route_integration_failure`,\
    \ the `integration_retry:{project_id}:{task_id}` global alert source, alert severity/actionability\
    \ reconciliation against live recovery state (fresh authorized repair agent, scheduled\
    \ retry, staleness, authority revocation, retry exhaustion), and dashboard operator-alert\
    \ rendering.\nFocus handoff: duplicate_detector\nDuplicate preflight verdict:\
    \ no_duplicate\nMatches: none\n\nEvidence: I reviewed the supplied project task\
    \ corpus for OOMPAH-735 (bug: \"Do not raise global warnings for integration failures\
    \ under active recovery\"). The task is highly specific \u2014 it targets `Orchestrator._route_integration_failure`,\
    \ the `integration_retry:{project_id}:{task_id}` global alert source, alert severity/actionability\
    \ reconciliation against live recovery state (fresh authorized repair agent, scheduled\
    \ retry, staleness, authority revocation, retry exhaustion), and dashboard operator-alert\
    \ rendering.\n\nThe corpus contains OOMPAH-1 through OOMPAH-175 and every one\
    \ of them is in a terminal state (Archived) \u2014 per the duplicate-investigator\
    \ contract these are excluded as duplicate candidates. Even setting terminal state\
    \ aside, none of the visible tasks describe the integration-retry warning pipeline\
    \ or alert reconciliation semantics addressed here. The closest reviewed tasks\
    \ were:\n- OOMPAH-162 (\"Tolerate stacked children merged to default branch\"\
    ) \u2014 about landing detection, unrelated to global alert lifecycle for integration\
    \ failures.\n- OOMPAH-163 (\"Allow generated epic target branches through dispatch\"\
    ) \u2014 dispatch/target-branch validation, not alert reconciliation.\n- OOMPAH-165\
    \ (\"Fix shared epic landed detection before main merge\") \u2014 epic landing/rollup\
    \ logic, not integration-retry alert routing.\n- OOMPAH-156 (\"Deduplicate auto-filed\
    \ internal error tasks\") \u2014 error_watcher task dedup, not orchestrator alert\
    \ emission.\n\nNo active peer task addresses the same underlying problem (global\
    \ alert reconciliation for integration_retry under active recovery), so the correct\
    \ verdict is no_duplicate."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e8819ade-af2c-4ae3-b21c-74afd250da81
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 1347
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 6
      output_tokens: 1347
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 6
    output_tokens: 1347
    cost_usd: 0.0
    recorded_at: '2026-08-03T19:19:24.969979+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-735__20260803T191823Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: duplicate_detector
    source_branch: OOMPAH-735
    source_sha: 806bf1feee8ac46220c8ec750a5167017834b176
    completed_at: '2026-08-03T19:19:24.988478+00:00'
---
## Summary

Triggered by: EXOCOMP-164

Production behavior observed on EXOCOMP-164: a task rebase conflict created an integration_retry warning, then Oompah successfully assigned a repair agent that continued producing fresh events. The global warning remained visible throughout normal recovery even though no operator action was required. This conflates workflow activity with actionable service alerts.

Root cause context:
- Orchestrator._route_integration_failure unconditionally appends a warning with source integration_retry:{project_id}:{task_id}.
- The success path removes that alert only after integration completes.
- Alert reconciliation does not consider a fresh authorized repair run, a scheduled automatic retry, authority revocation, staleness, or retry exhaustion.

Implementation scope:
- Preserve integration failure diagnostics on the task and integration metadata regardless of global alert presentation.
- Reconcile the global alert severity/actionability against live recovery state.
- While an authorized repair agent is assigned and fresh, or a bounded automatic retry is scheduled normally, suppress the global operator warning or expose it only as informational workflow activity.
- Raise or restore a warning when recovery has no owner or retry, becomes stale, exits without resolving the condition, loses authority, or approaches/exhausts its retry budget.
- Keep error severity for integrity, authentication, transport, or policy failures that actually prevent recovery.
- Make transitions race-safe across failure recording, repair dispatch, agent exit, resubmission, successful integration, restart recovery, and websocket snapshot publication.
- Prefer explicit structured fields such as action_required and recovery_state over deriving actionability from message text.
- Ensure the dashboard operator-alert area renders only actionable warning/error conditions while task details retain the diagnostic and recovery progress.

Required tests:
- A rebase failure followed by a fresh active repair agent is absent from global warnings or downgraded to informational activity.
- The same failure with no assigned repair and no scheduled retry is an actionable warning.
- Scheduled bounded retry/backoff is normal activity until stale or exhausted.
- Stale, failed, authority-revoked, and retry-exhausted repairs re-arm the warning deterministically.
- Successful resubmission/integration clears both actionable and informational recovery state.
- Dispatch/exit/restart races cannot leave a permanently suppressed real warning or a stale warning during healthy recovery.
- State API and websocket snapshots publish each severity/actionability transition without requiring a page refresh.
- Existing terminal-audit, auth, repository-hygiene, and other genuinely actionable alerts retain their behavior.
- Run focused orchestrator, integration retry, state API, websocket, and dashboard tests, followed by make test.

Acceptance criteria:
- Normal automatic recovery is represented as task-local progress, not a global operator warning.
- Every global warning states a condition requiring attention or indicating recovery is no longer progressing normally.
- If active recovery stops making progress, the warning reappears automatically within the configured freshness threshold.
- No failure diagnostics, retry history, authority fencing, or task-state evidence is lost.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 19:18
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-03 19:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 19:19
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 2, Tool calls: 0
- Tokens: 6 in / 1.3K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 8s
- Log: OOMPAH-735__20260803T191823Z.jsonl
---
author: oompah
created: 2026-08-03 19:20
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-03 19:20
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-08-03 19:21
---
Understanding: resolving this review branch only. I will fetch origin, rebase OOMPAH-735 onto origin/main without dropping or squashing commits, resolve conflicts by preserving both intended changes, run focused affected tests, then force-push with lease and verify the review diff.
---
author: oompah
created: 2026-08-03 19:22
---
Discovery: the OOMPAH-735 branch was created from origin/main and has no issue commits, no remote OOMPAH-735 ref, no reflog history beyond branch creation, and an empty diff versus its creation point. The first required rebase was clean; origin/main advanced concurrently by two commits, so I am refreshing and rebasing once more before handoff. There are no conflicts or implementation changes to resolve.
---
author: oompah
created: 2026-08-03 19:22
---
Implementation: no source or test files were modified because the branch contains no OOMPAH-735 implementation commits and the rebase had no conflicts. The only change was advancing the local branch base to the latest origin/main, preserving the complete (empty) issue commit set.
---
author: oompah
created: 2026-08-03 19:23
---
Verification: force-push succeeded. HEAD, origin/OOMPAH-735, and origin/main all resolve to fae232ee614a74a9565f4fc6bfbbcf86333f0255; ahead/behind counts are 0/0; git diff --check and the review diff are empty; the worktree is clean and up to date. No focused tests were run because no code or conflict resolution changed behavior.
---
author: oompah
created: 2026-08-03 19:23
---
Focus handoff: merge_conflict

Outcome: completed the required fetch/rebase and force-push; both rebases were conflict-free. The review branch now exists remotely and exactly matches current origin/main.

Evidence: git fetch origin && git rebase origin/main; git push --force-with-lease -u origin HEAD; HEAD/origin-OOMPAH-735/origin-main all fae232ee614a74a9565f4fc6bfbbcf86333f0255; clean worktree; zero review commits and empty diff.

Remaining work/risks: OOMPAH-735 has no implementation or tests at all, so the described warning-recovery bug remains unresolved. Submitting this empty branch would incorrectly claim completion.

Recommended next focus: feature, to implement the backend/state/dashboard behavior and required tests from the task description.
---
author: oompah
created: 2026-08-03 19:23
---
Completion (merge-conflict focus): delivered a clean, current, force-pushed review branch with verified zero diff. Conflict-resolution work is complete; feature implementation remains and is being handed off rather than submitted as an empty fix.
---
author: oompah
created: 2026-08-03 19:24
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 16
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 19s
- Log: OOMPAH-735__20260803T192055Z.jsonl
---
author: oompah
created: 2026-08-03 19:24
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-03 19:24
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 19:43
---
Understanding: The current OOMPAH-735 branch is empty (previous merge_conflict focus confirmed no implementation exists). The task requires end-to-end backend + frontend changes to reconcile integration_retry alerts against live recovery state. Plan: (1) Add structured 'action_required' and 'recovery_state' fields to the integration_retry alert schema (backend, oompah/orchestrator.py::_route_integration_failure). (2) Add a pure classifier _classify_integration_retry_recovery(alert, running, queue_items, revoked, now, freshness) that returns (recovery_state, action_required, level) so it can be unit-tested. (3) Add a reconciliation pass _reconcile_integration_retry_alerts() invoked from get_snapshot() so the state API and WS snapshots always reflect current recovery state without a page refresh. (4) Add config integration_recovery_freshness_seconds (default 300s). (5) Frontend (oompah/templates/dashboard.html): filter otherAlerts by action_required !== false so informational recovery activity is not surfaced in the global operator banner or inline agent warnings. Task-level integration diagnostics are unchanged. (6) Tests exercising each severity/actionability transition: fresh repair agent absent from banner, no repair/no retry actionable, scheduled retry informational, stale/exhausted/revoked re-arms warning, successful integration clears both actionable and informational alerts. Since I am the frontend specialist but the change fundamentally couples backend structured fields with frontend filtering, I will implement both — pure filter-only changes would be untestable without the backend fields.
---
author: oompah
created: 2026-08-03 19:58
---
Discovery: root cause is in oompah/orchestrator.py::_route_integration_failure._record_failure_diagnostic (line 9203) which unconditionally appended a warning-level alert with source integration_retry:{project_id}:{task_id}. Success path at line ~9990 removed the alert only after integration completed. Alerts flow to the dashboard via Orchestrator.get_snapshot()['alerts'] (line 34741) which is consumed by handleStateUpdate() in oompah/templates/dashboard.html: alerts are split into cred/auth/other groups and the 'other' group is rendered both inline in agent-warnings and in the alerts-banner. Since dashboard filtering must key off an explicit signal (not message text), the fix requires structured backend fields (action_required + recovery_state) plus a reconciliation pass so the state API and WS snapshots publish current recovery classification without a page refresh.
---
author: oompah
created: 2026-08-03 19:58
---
Implementation: (1) oompah/config.py — added integration_recovery_freshness_seconds (default 300s, env OOMPAH_INTEGRATION_RECOVERY_FRESHNESS_SECONDS). (2) oompah/orchestrator.py::_route_integration_failure — the _record_failure_diagnostic closure now takes recovery_state + action_required + optional level and stamps recorded_at. Route classifies the initial state as scheduled_retry (retryable), retry_exhausted (needs_human), awaiting_repair (conflict/generated_helper/needs_rebase/ci_failure — a repair worker will be dispatched), no_recovery (task_push_race/stale_head/missing_head/missing_epic/epic_merge_failure — owner must resubmit), or unrecoverable (integrity/auth/transport/policy — level=error). (3) Added Orchestrator._classify_integration_retry_recovery — a pure @staticmethod classifier that returns (recovery_state, action_required, level) from observable facts (running focus + last event, authority_revoked, queue state + next_retry_at + attempts, integration state, now, freshness). (4) Added Orchestrator._reconcile_integration_retry_alerts, invoked from get_snapshot() so every state API/WS snapshot publishes the current classification. Diagnostics (task_id, error, failing_step, attempts, max_attempts, next_retry_at, repair_action, recorded_at) are preserved; only level, recovery_state, action_required, updated_at are rewritten. (5) Added Orchestrator._clear_integration_retry_alert so successful integration clears both actionable and informational rows. (6) oompah/templates/dashboard.html — otherAlerts filter now drops alerts with action_required===false so informational recovery activity does not surface in the global operator banner or inline agent warnings. Missing/undefined field is treated as actionable for legacy compatibility. Task-level detail rendering is unchanged.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-735
type: bug
status: Open
priority: 1
title: Do not raise global warnings for integration failures under active recovery
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T19:17:18.559962Z'
updated_at: '2026-08-03T19:17:23.882087Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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


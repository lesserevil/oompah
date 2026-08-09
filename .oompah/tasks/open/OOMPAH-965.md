---
id: OOMPAH-965
type: bug
status: Open
priority: 2
title: '[backend:workflow_runtime] Durable workflow publication failed for proj-14849f1b'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T16:25:26.622591Z'
updated_at: '2026-08-09T17:14:41.167547Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:workflow_runtime`:

> Durable workflow publication failed for proj-14849f1b

### Steps to Reproduce
1. Run oompah with `backend:workflow_runtime` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:workflow_runtime` and is recorded by oompah's `error_watcher`:

> Durable workflow publication failed for proj-14849f1b

### Expected Behavior
The operation in `backend:workflow_runtime` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:workflow_runtime` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: fe9cb767e4524d9b
- dedup_fingerprint: fe9cb767e4524d9b

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 16:27
---
Root cause captured at 2026-08-09T16:25:25 while direct owner audit overrides changed terminal-audit disposition during a full publication: publish_after_terminal_proof deliberately raised WorkflowRuntimeError('terminal-audit disposition changed before publication') as a stale-snapshot fence. The publication was correctly rejected and retryable; treating this expected authority race as an unhandled ERROR caused error_watcher to file this task. Scope should distinguish expected stale/fenced publication invalidation from genuine durable-store/publication failure, reschedule/coalesce a fresh reconcile, emit bounded informational telemetry, and retain ERROR/error_watcher behavior for unexpected failures. Add an exact disposition-change-before-publication regression proving no task is auto-filed and fresh publication converges.
---
author: oompah
created: 2026-08-09 16:27
---
Project owner promotes the confirmed expected-publication-fence misclassification for direct implementation.
---
author: oompah
created: 2026-08-09 16:39
---
Direct repair implemented on branch OOMPAH-965: terminal-audit proof invalidation now uses an explicit expected supersession type, restores the unpublished authority checkpoint, reports INFO-level bounded telemetry with requires_reconcile, and the orchestrator posts one fenced/coalesced ordinary full-scan continuation. Genuine publication failures retain ERROR behavior. Tests prove disposition/authority races reject stale publication without error logging, a fresh pass converges, continuation respects pause/quiesce/drain fences, and architecture bounds remain intact. 286 affected tests plus terminal mutation, secret, critical lint, and diff checks pass.
---
author: oompah
created: 2026-08-09 16:41
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-965`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-09 17:07
---
Final correction pushed at f8ebb383e on PR #774. False terminal-audit authority proofs remain an expected publication-supersession retry at INFO, while a missing proof provider remains a genuine WorkflowRuntimeError at ERROR. Validation: 432 affected tests, 10 focused proof tests, terminal-audit mutation scan, secret scan, critical Ruff, and diff checks pass; exact-head independent re-review and hosted 3.11/3.12/3.13 are pending.
---
author: oompah
created: 2026-08-09 17:14
---
Independent-review blocker corrected at exact head c17eba9b28 on PR #774: a required terminal-audit authority proof provider absent before initial projection now raises WorkflowRuntimeError before any publication; callable false proofs retain authority-change non-materialization/supersession behavior. Regression covers initial absence, removal before publication, and ordinary authority change. 438 broader tests plus lint, diff, terminal-audit, and secret scans pass; independent re-review and hosted exact matrix are running.
---
<!-- COMMENTS:END -->

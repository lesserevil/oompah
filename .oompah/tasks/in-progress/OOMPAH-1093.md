---
id: OOMPAH-1093
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Orchestrator shutdown attempt failed; retaining process
  and retrying'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:04:30.156611Z'
updated_at: '2026-08-11T16:33:32.122145Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Orchestrator shutdown attempt failed; retaining process and retrying

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Orchestrator shutdown attempt failed; retaining process and retrying

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
- fingerprint: 9984037ce1db983d
- dedup_fingerprint: 9984037ce1db983d

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 16:09
---
Live reproduction during normal make restart at 2026-08-11T16:04Z: shutdown quiesced while a terminal auditor was between durable claim/worktree preparation and provider admission. Orchestrator._drain_background_work raised RuntimeError('lifecycle publication snapshot did not drain; refusing to close lifecycle stores'); stop_until_safe retained the process and its next attempt succeeded, then os.execv completed. The interrupted auditor lease recovered as abandoned/retry_wait. Repair scope: make the graceful shutdown publication drain converge deterministically when terminal-audit/provider admission loses the quiesce race, without reporting a backend error for a safely retryable internal drain; retain fail-closed refusal to close stores while true writers remain. Add a deterministic barrier regression around audit claim/provider-admission versus quiesce, prove bounded retry reaches a fully published snapshot and clean shutdown with no orphan workflow lease/attempt/worktree, and preserve error reporting when progress is genuinely impossible.
---
author: oompah
created: 2026-08-11 16:16
---
Implemented and pushed exact head 8031e7f74b6836ec0480fb3065961995fbfa28a8 (based current main 3264da678). Added LifecyclePublicationDrainPending so direct background drain remains fail-closed, while stop() classifies an already-revoked snapshot worker's bounded join timeout as safely retained authority and returns False for stop_until_safe's retry instead of logging an error. Deterministic regression blocks a real lifecycle snapshot beyond the join timeout, proves stores remain open, no 'shutdown attempt failed' error is emitted, then release causes bounded retry, clean store close, and completed shutdown. Checks: 33 restart API tests + 110 event-loop/resource/granian tests passed; terminal mutation scan 21/21; diff/secret hooks clean. Awaiting independent exact-head review; not submitted.
---
author: oompah
created: 2026-08-11 16:24
---
Normalized the commit message to the required canonical attribution trailer without changing the patch and force-pushed with an exact lease. Current review candidate is 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb; diff versus prior 8031e7f74b6836ec0480fb3065961995fbfa28a8 is commit metadata only. Existing verification remains valid: 33 restart API tests, 110 adjacent lifecycle/resource tests, terminal mutation scan 21/21, clean diff and secret hooks. Awaiting independent review; not submitted.
---
author: oompah
created: 2026-08-11 16:33
---
Fresh independent review ACCEPTED exact head 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb. Reviewer verified only LifecyclePublicationDrainPending is normalized to a bounded stop retry; lifecycle callback/snapshot authority prevents store teardown; direct drain and unrelated exceptions remain fail-closed; no observer recursion or false backend-error alert occurs; and the retry converges after authority exits. Independent evidence: 33 restart API tests, 111 supporting lifecycle/event/IPC tests and negative-path probes, clean diff. Holding submission only until the current OOMPAH-1085 canonical gate has the sole validation slot; not merged.
---
<!-- COMMENTS:END -->

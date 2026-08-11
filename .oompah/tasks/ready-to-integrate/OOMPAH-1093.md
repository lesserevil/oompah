---
id: OOMPAH-1093
type: bug
status: Ready to Integrate
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
updated_at: '2026-08-11T16:54:50.608224Z'
work_branch: OOMPAH-1093
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/829
review_number: '829'
review_head: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1093
  base_branch: main
  base_sha: 3264da6780e35b10f759de8aade7b3509977bbb9
  head_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
  submitted_at: '2026-08-11T16:42:50.783268+00:00'
  updated_at: '2026-08-11T16:54:34.019821+00:00'
  wait_reason: review_generation_requeue
  wait_generation: review:11cdb9605742f739e42a6eb488eaf11ecd0395bb54ef1f086b0e9301eeb3c183
oompah.work_branch: OOMPAH-1093
oompah.review_url: https://github.com/lesserevil/oompah/pull/829
oompah.review_number: '829'
oompah.target_branch: main
oompah.review_head: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
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
author: oompah
created: 2026-08-11 16:43
---
Treat retained lifecycle-publication drain authority as a bounded graceful-stop retry while keeping stores open and unrelated failures fail-closed.
---
author: oompah
created: 2026-08-11 16:52
---
Branch quality gate passed for `4c6de3f056fcec98fa1e0118e7fe683c76b71ceb` using `make test` in 180.2s. Review creation may proceed.
---
<!-- COMMENTS:END -->

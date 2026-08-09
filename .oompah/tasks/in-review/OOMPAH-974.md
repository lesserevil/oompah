---
id: OOMPAH-974
type: bug
status: In Review
priority: 1
title: Keep lifecycle control recoverable when workflow reconciliation deadlocks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T21:05:01.679955Z'
updated_at: '2026-08-09T21:55:16.851137Z'
work_branch: OOMPAH-974
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/783
review_number: '783'
review_head: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-974
  head_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
  submitted_at: '2026-08-09T21:50:33.423286+00:00'
  updated_at: '2026-08-09T21:50:33.423286+00:00'
oompah.work_branch: OOMPAH-974
oompah.review_url: https://github.com/lesserevil/oompah/pull/783
oompah.review_number: '783'
oompah.target_branch: main
oompah.review_head: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
---
## Summary

Triggered by: OOMPAH-737

Regression of OOMPAH-737/OOMPAH-350 observed live on 2026-08-09 while the 1,776-issue workflow reconciliation was active. The service kept PID 2715559 and port 8090 but /api/v1/state and /healthz returned no bytes; make graceful and make status timed out. After scheduler CPU stopped, the sole process remained indefinitely blocked in futex_do_wait. The documented emergency make force-restart also could not recover because canonical_cli_cutover required a responsive old /healthz, and identity-checked make stop sent SIGTERM but the process did not exit within 30 seconds. No worker child processes existed; recovery required verifying PID/cwd/process-group identity, SIGKILLing that exact service group, and make start. Implementation scope: reproduce a large/current workflow reconciliation that wedges scheduler/control-plane shutdown; identify and remove the remaining cross-thread/event-loop/GIL/deadlock path; keep /healthz, /api/v1/state, quiesce, restart-claim/cancel, and graceful/force lifecycle control responsive; and provide an identity-safe bounded emergency recovery when the old HTTP control plane is unresponsive. Preserve agent draining and never kill unverified processes. Relevant areas: scheduler thread isolation, workflow reconciliation/state publication, server shutdown, scripts/canonical_cli_cutover.py, Makefile lifecycle targets, and process identity. Required tests: blocked reconciliation cannot delay health/state/quiesce; graceful restart cuts over; emergency force-restart can recover a verified unresponsive old service without an HTTP precondition; SIGTERM shutdown is bounded; reused/wrong PID identity is refused; active-agent normal drain semantics remain intact. Acceptance: deterministic regressions pass, focused scheduler/restart/workflow suites and full gate pass, and a live large-corpus reconciliation remains controllable and restarts cleanly.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 21:05
---
Direct owner recovery/implementation claimed after live reproduction. Exact incident: verified service PID 2715559, no worker children, all HTTP lifecycle calls timed out, force-restart could not pass old-health precondition, SIGTERM stop exceeded 30 seconds, exact process group required SIGKILL, and make start recovered exact build 312c18ae3.
---
author: oompah
created: 2026-08-09 21:19
---
Additional post-restart liveness evidence: after generation 852 finished, SQLite had zero running jobs, but /api/v1/state continued to report workflow_runtime.worker active=3, retained=3, shared active lanes=3 and last admission repeatedly processed/scheduled zero. A priority-0 direct_owner_claim for OOMPAH-975 remained queued despite two explicit POST /api/v1/refresh requests. All worker/reconcile threads were sleeping; no new full tick published after 21:14:24. The fix must reconcile retained in-memory calls with terminal/exhausted durable rows and preserve the reserved control slot so priority-0 owner/lifecycle control cannot be starved by orphaned shared effects.
---
author: oompah
created: 2026-08-09 21:38
---
Implementation checkpoint: removed the large-corpus O(n^2) native detail-read amplification with a generation-scoped ID index and bounded cold-scan GIL yields; added cooperative pre-publication drain checkpoints across distinct implementation/review/integration/epic collectors; reserved direct_owner_claim in the control lane while preserving stale adapter calls until real settlement. Reworked make force-restart as a fully HTTP-independent exact-identity transaction: capture, stage/verify, bounded TERM then identity-rechecked SIGKILL, activate, then Make start. Wrong/stale PID remains refused. Focused new/reviewer regressions currently pass (14 tests); broader and full gates are next.
---
author: oompah
created: 2026-08-09 21:49
---
Implementation and review complete on exact base 312c18ae3. Validation: independent 399-test relevant suite passed; focused combined regression suite passed 335 tests; git diff --check and compileall passed (one unrelated pre-existing SyntaxWarning). A duplicate local make test run reached 8,580 passed, 7 skipped, 2 xfailed with no failures before all workers stalled in jbd2 filesystem journal waits; it was interrupted after 9m56s per operator direction because the protected exact-head gate runs once. Changes add indexed/cooperatively yielding native reads, drain-aware reconciliation checkpoints across all collector families, a reserved direct-owner control lane with retained-call safety, and identity-rechecked HTTP-independent emergency force restart escalation.
---
author: oompah
created: 2026-08-09 21:50
---
Implemented and pushed as 8526a01bfb741eb58c267e7f4b649b75f8bdc882. Native Markdown reads now use indexed cache lookup plus cooperative GIL checkpoints; workflow reconciliation is drain-aware across implementation, review, integration, and epic collectors; direct owner claims use the reserved control lane while stale non-cancellable effects remain retained; emergency force restart is HTTP-independent with exact process identity rechecks before bounded SIGKILL escalation. Validation: independent 399 relevant tests passed, focused combined suite 335 passed, diff check and compileall passed; duplicate full run reached 8,580 passed with no failures before operator-directed interruption during filesystem journal stalls.
---
author: oompah
created: 2026-08-09 21:54
---
Branch quality gate passed for `8526a01bfb741eb58c267e7f4b649b75f8bdc882` using `make test` in 160.7s. Review creation may proceed.
---
<!-- COMMENTS:END -->

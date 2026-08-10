---
id: OOMPAH-989
type: bug
status: In Progress
priority: 1
title: Keep graceful restart responsive while quiesce drains workflow work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T06:19:44.763738Z'
updated_at: '2026-08-10T06:49:32.777012Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-986

Live regression on 2026-08-10 while deploying OOMPAH-986: make graceful acquired the restart claim against healthy revision 148db44a97e42140160a428bd11eed2c50f75381, then POST /api/v1/orchestrator/quiesce timed out. The server stopped answering /healthz and /api/v1/state for several minutes, logged no progress after 06:08:42 UTC, and slept on futex_do_wait. The cutover could not cancel its restart claim because that POST also timed out, requiring the identity-checked make force-restart recovery. The last authoritative snapshot had zero agents and auditors; only durable workflow jobs existed. Diagnose and eliminate any event-loop blocking/deadlock across the quiesce/restart-claim path, workflow publication, issue snapshot refresh, and webhook handling. Relevant code: server lifecycle endpoints, orchestrator quiesce/drain, scripts/canonical_cli_cutover.py, workflow_runtime publication/drain coordination, and lifecycle tests. Add a deterministic regression that holds slow/full-project workflow or snapshot work while a graceful restart claims and quiesces; prove /healthz and lifecycle control requests remain responsive, the quiesce request returns within its HTTP budget, cancellation/resume remains possible after a pre-cutover failure, no agent is interrupted before drain authority permits it, and restart reaches the exact new build without force. Also cover a dropped/timed-out response after server-side acceptance so the client and server converge without an orphaned restart fence. Acceptance: make graceful cannot wedge the HTTP control plane; bounded failures leave the old service responsive and unquiesced or complete an exactly identified cutover; focused lifecycle/runtime/server tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 06:49
---
Implementation is complete and pushed for independent review at 53b413fbfd6975d007fbf5c04711db2a666b20d4 on branch OOMPAH-989, rebased onto origin/main 6c6f55220f61149fc15e73f18fbf7fdc2445f146. The fix keeps quiesce/restart provider-fence acquisition cooperative and bounded, moves issue snapshot authority reads plus resume recovery off the HTTP event loop, makes graceful-restart admission cooperative, and retries exact idempotent restart-claim cancellation after an accepted-but-dropped response. Deterministic regressions cover quiesce and restart contention with responsive health, a blocked snapshot authority probe with responsive health, and dropped quiesce/cancel responses converging without an orphan restart fence. Validation: combined OOMPAH-989 plus OOMPAH-987/OOMPAH-988 adjacent orchestrator/gate suites 1455 passed, 3 non-failing warnings; compileall passed; git diff --check passed; terminal-audit scan passed; secret checks and commit hooks passed. Task intentionally remains In Progress and unsubmitted pending independent review.
---
<!-- COMMENTS:END -->

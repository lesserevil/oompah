---
id: OOMPAH-737
type: task
status: Open
priority: null
title: Keep health and graceful cutover responsive during terminal lifecycle reconciliation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T20:06:54.610285Z'
updated_at: '2026-08-03T20:07:05.274540Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression observed during make restart on 2026-08-03 after deploying fae232ee6. The graceful cutover drained all workers and the service exec reached the new revision, but resume synchronously reconciled dozens of lifecycle-incompatible shared-epic children from Merged to Done. Each tracker mutation took roughly 5–6 seconds; for more than four minutes the listening service returned no bytes even from /healthz or /api/v1/state. scripts/canonical_cli_cutover.py therefore timed out POST /api/v1/orchestrator/resume and reported that cutover failed, even though the new instance later became healthy at the intended revision. This regresses OOMPAH-350's HTTP-loop isolation guarantee and makes OOMPAH-676's safe cutover result ambiguous.\n\nImplementation scope:\n- Move bulk terminal lifecycle reconciliation off the HTTP request/event-loop path used by resume and startup readiness.\n- Make reconciliation bounded, resumable, idempotent, and observable, with progress persisted between batches.\n- Keep /healthz and /api/v1/state responsive while reconciliation runs; expose degraded/migrating progress without misreporting the build identity.\n- Make the cutover wrapper distinguish an accepted candidate exec plus busy migration from an unchanged old service, and prevent a resume transport timeout from falsely reporting rollback/failure when the candidate is authoritative.\n- Preserve exact lifecycle fencing, tracker comments, audit metadata, state-branch writes, and per-record failure isolation.\n\nRelevant code: oompah/terminal_audit_enforcement.py lifecycle reconciliation, orchestrator resume/startup scheduling, oompah/server.py lifecycle endpoints and health, scripts/canonical_cli_cutover.py resolution logic, and Makefile restart tests.\n\nRequired tests:\n- Seed dozens of incompatible shared-epic children with a deliberately slow tracker; resume must return promptly and /healthz plus /api/v1/state must stay responsive while batches drain.\n- Prove every row converges exactly once across restart mid-batch, tracker failure, duplicate resume, and concurrent state reads.\n- Reproduce the live cutover: candidate exec succeeds, resume response times out or is delayed by migration, and the wrapper must identify the candidate revision/instance without false rollback or error.\n- Preserve OOMPAH-350 scheduler isolation and OOMPAH-676 graceful worker-drain semantics; run focused lifecycle, terminal enforcement, cutover, health, and Makefile restart suites plus make test.\n\nAcceptance criteria:\n- No terminal-reconciliation workload can make health/state endpoints unresponsive.\n- make restart reports success when the intended candidate is healthy, even if post-exec migration is still progressing.\n- Reconciliation remains fail-closed, durable, bounded, and restart-safe, with actionable diagnostics only for rows that cannot converge.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


---
id: OOMPAH-1007
type: task
status: Ready to Integrate
priority: null
title: Fence completed terminal-audit recurrence to current workflow completion authority
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T23:19:04.544332Z'
updated_at: '2026-08-11T01:24:19.196864Z'
work_branch: OOMPAH-1007
target_branch: main
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 9dc1401e-893a-4d78-b780-e075b80e6ca4
  request_fingerprint: c095f7baf028623fb2e3b627aeb5c1d76005844bc667a2b87478b4a5a96db285
oompah.target_branch: main
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  post_landed_parent_id: OOMPAH-940
  task_branch: OOMPAH-1007
  base_branch: main
  base_sha: 74e68a020357615c81cf7c7b5cff808763dc34d3
  head_sha: 5e46c8a06c3d8e98eeb0f4b5f9896d5c0ad67654
  submitted_at: '2026-08-11T01:23:58.775600+00:00'
  updated_at: '2026-08-11T01:23:58.775600+00:00'
oompah.work_branch: OOMPAH-1007
---
## Summary

Live reproduction on deployed main 74e68a020: OOMPAH-940 naturally completed epic auto-close and staged fresh Done/Merged audits after all systemic descendants landed and the protected full gate passed. The new audit records audit-9ac757c7ad64/audit-47936c819189 nevertheless reused issue evidence fingerprint 0a8f66cc from the August 9 root-branch audit at 2dd74be2. TerminalTransitionCoordinator.reconcile_completed_recurrence_sync therefore replayed the historical ci_failure as workflow-recurrence:audit-9ac757c7ad64 without a new attempt and moved OOMPAH-940 from In Validation to Needs CI Fix. The canonical workflow terminal decision/evidence had advanced through later protected descendant deliveries, but recurrence authority observed only the unchanged root issue fingerprint.\n\nImplementation scope: bind completed terminal-audit recurrence to the complete current terminal workflow authority, not merely a root issue fingerprint that can remain unchanged while canonical child/descendant landing and quality evidence advances. A prior completed PASS or FAIL may be reused only when both the task fingerprint and the authoritative workflow terminal eligibility/quality revision are identical. When workflow completion authority advances, supersede/retire the obsolete recurrence source and queue one fresh exact audit (or reuse an exact current authoritative passing gate through the existing policy) without applying the old result. Preserve immutable audit history, identical-evidence idempotency, Done→Merged ordering, project/task/fingerprint CAS, stale-worker rejection, fail-closed behavior for missing/ambiguous authority, pause/restart semantics, and owner-override safety. Relevant code: oompah/terminal_transition_coordinator.py completed recurrence, terminal transition request fingerprint/binding, durable workflow transition/effect plumbing in oompah/workflow_runtime.py and epic auto-close paths, and terminal audit persistence/dispatch.\n\nRequired tests: reproduce OOMPAH-940 with an old completed ci_failure at root head E0, then a fresh workflow auto-close whose root issue fingerprint is still E0 but whose canonical completion authority has advanced; prove the old failure is not replayed, exactly one fresh chain is admitted, and the task does not return to Needs CI Fix. Controls must prove truly identical workflow authority still replays PASS and FAIL idempotently; changed/absent/ambiguous authority fails closed; Done/Merged chain ordering, restart between stage/reconcile, concurrent recurrence/result CAS, and project isolation remain correct. Run focused coordinator/workflow/epic tests, terminal mutation scan, and make test. Acceptance: after deployment, OOMPAH-940 can re-enter the natural terminal path without reusing audit-fddacbaa91fb solely because 0a8f66cc is unchanged; current authoritative evidence decides the audit, current exhausted/divergence stay zero, and workflow-rollout-check passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 23:48
---
Implementation milestone: the durable audit record and workflow ledger now bind the mutation-revalidated workflow revision, same-evidence authority advances create a fresh audit generation, recurrence/result/rearm/override paths require exact revision and repository binding, and legacy workflow recurrences without a revision fail closed. The production-shaped restart regression (old completed CI failure at revision A, same root evidence at revision B) launches a fresh auditor instead of replaying Needs CI Fix. Focused suite: 485 passed; broader terminal/workflow checks and independent review are in progress.
---
author: oompah
created: 2026-08-11 00:07
---
Combined patch milestone: workflow_revision is now a bounded, secret-safe durable identity; evidence-drift restaging, dispatch duplicate selection, Done-to-Merged prerequisites, completed recurrence, rearm proofs, overrides, retirement rows, workflow jobs, and stale callback/CAS paths all require the exact fingerprint + workflow revision + selected ref/SHA authority. Rearm proof schema v2 retains restart compatibility for legacy v1 records only when workflow_revision is absent. Regression gates are green: 603 focused tests, 1,530 broader workflow/audit integration tests (2 expected xfails), terminal mutation scan 20/20, and git diff check. Independent final review and the complete Makefile gate are still in progress.
---
author: oompah
created: 2026-08-11 00:41
---
Final hardening milestone: adversarial review exposed and the branch now fixes four upgrade-path blockers: pre-cutover workflow records migrate through a durable restart-safe intent instead of deadlocking; oversized launch checkpoints consume a redacted bounded retry budget; unbound audit jobs atomically acquire exact ref/SHA authority without replaying completed legacy results; and review-terminal staging forwards freshly verified completion authority. The combined current regression set is green (839 audit/transition tests plus 376 review/integration/runtime tests), the terminal mutation scan passes 21/21 after documenting the exact coordinator migration boundary, secret scan passes, and git diff is clean. A fresh independent whole-diff review is running before the one authoritative full make test gate.
---
author: oompah
created: 2026-08-11 01:23
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-1007`
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
created: 2026-08-11 01:23
---
Implementation pushed at 5e46c8a06 and PR #805 opened. Final evidence: 1,238 focused tests passed after integration hardening; exact authority/race regressions passed; mutation scan 21/21 allowlisted; paranoid secret scan and commit hooks passed. Full make test completed with 19,729 passed, 7 skipped, 2 xfailed and one unrelated load-sensitive late-effect quarantine timeout; that test passed 20/20 isolated and follow-up OOMPAH-1008 tracks making it deterministic. Protected PR CI is now authoritative for the review-ready head.
---
author: oompah
created: 2026-08-11 01:24
---
Implemented exact workflow-revision/ref/SHA fencing for terminal audits, restart-safe legacy migration, CAS-safe binding promotion, bounded payload convergence, and review-runtime authority propagation. PR #805; focused and security checks pass. OOMPAH-1008 tracks an unrelated full-suite timing flake.
---
<!-- COMMENTS:END -->

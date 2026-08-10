---
id: OOMPAH-990
type: bug
status: In Progress
priority: 1
title: Retire late interrupted quality-gate alerts after terminal task reconciliation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T06:46:32.018670Z'
updated_at: '2026-08-10T07:25:20.788951Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-987

Live regression on 2026-08-10: OOMPAH-987 was reconciled Merged after exact full gate and protected CI, but a duplicate server gate terminated with SIGTERM/owner_cancellation and wrote _quality_gate_outcomes after terminal reconciliation. /api/v1/state continued to project quality_gate:proj-14849f1b:OOMPAH-987:dcfb... as active info/scheduled_retry even though the task was Merged, quality_gates.active was empty, validation capacity was free, and no retry could run. Current outcomes are timestamp-less and clear only on PASS, a narrow Ready-reconcile path, or >128 later entries; terminal maintenance has no bounded retirement. OOMPAH-642 fenced terminal gate outcome mutations but only clears standalone_ready_delivery:* and did not cover this late result race. Implement race-safe producer/consumer retirement or suppression so a non-pass gate outcome cannot remain active once exact task authority is terminal/revoked. Preserve observable legitimate retries for nonterminal exact heads and do not hide current failures. Relevant code: orchestrator quality-gate outcome recording, state alert projection, terminal reconciliation, and quality-gate tests. Required tests: deterministically order terminal Merged persistence before a late interrupted result and prove no active quality_gate alert; prove reversed order is cleared during terminal reconciliation; prove nonterminal interrupted gates still show scheduled-retry info; prove stale old-head outcomes cannot suppress a current-head failure; prove restart/state rebuild converges. Acceptance: terminal tasks have no active retry alert for work that cannot retry, cleanup is bounded/idempotent across the race, focused state/orchestrator/gate tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 06:58
---
Implemented the race fence in the dedicated OOMPAH-990 worktree: standalone quality-gate outcome publication now serializes with delivery-authority revocation, rejects obsolete authority/head results, and terminal revocation retires any already-published outcome. Added deterministic coverage for terminal-first and result-first ordering, preserved nonterminal scheduled-retry visibility, protected a current-head failure from a late old-head PASS, and verified restart rebuild convergence. Focused quality-gate/standalone coverage currently passes: 221 passed, 74 deselected. Independent lock/test review and repository checks are still in progress; not submitted.
---
author: oompah
created: 2026-08-10 07:06
---
Implementation is committed and pushed for independent review at exact head 847c6b595262b08678672e53a770abbedfc0e8c0 on origin/OOMPAH-990. Focused evidence: 223 quality-gate/standalone tests passed; delivery restart recovery regression passed; terminal task mutation scan passed 20/20; commit hooks including paranoid secret scans passed. Worktree is clean and synchronized. Full make test is starting now. Task intentionally remains In Progress and unsubmitted pending independent review.
---
author: oompah
created: 2026-08-10 07:25
---
Re-review replacement is pushed at exact head 46cc659bb485c6b81f556c1141e0807a23897b06. This supersedes invalid head 847c6b595. The replacement fences authority-less production publishers with exact project/task/head/branch/target/command identity plus project-serialized fresh tracker/evidence/head validation; an old producer PASS cannot clear a current producer failure. The real standalone Ready consumer now retains bounded interrupted scheduled-retry state until the exact retry passes or authority changes. Deterministic production terminal-first/result-first, authority-less review, old-head/current-failure, and real interrupted-then-pass standalone tests are included. Focused evidence: 358 passed across quality gate, standalone delivery, and delivery recovery modules; compile clean; terminal mutation scan 20/20; secret scans/hooks passed. Worktree is clean/synchronized. Full gate intentionally not restarted pending re-review; task remains In Progress and unsubmitted.
---
<!-- COMMENTS:END -->

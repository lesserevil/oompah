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
updated_at: '2026-08-10T06:46:52.902312Z'
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


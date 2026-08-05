---
id: OOMPAH-840
type: task
status: Open
priority: null
title: Recover ready children whose terminal parent branch was pruned
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T18:21:39.670324Z'
updated_at: '2026-08-05T18:23:53.963510Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: OOMPAH-523 was re-submitted at unchanged verified head 9ea2b5523 after OOMPAH-838 deployed. IntegrationQueueStore atomically consumed the one-shot retry_forced flag, then the integration executor blocked before the gate because parent epic OOMPAH-521 is already Merged and remote epic-OOMPAH-521 was correctly pruned. The exact task head is reachable from origin/main, so asking an operator to recreate or resubmit a deleted terminal container is wrong and consumes explicit retry authority without progress. OOMPAH-526 is another Ready child of the same terminal parent.\n\nImplementation scope:\n- Before requiring a live epic target branch, reconcile a Ready/blocked child whose parent/container is Merged or Archived using authoritative parent target/merge metadata, the task work branch/head, durable integration history, terminal audit evidence, and Git ancestry.\n- If the exact child head is already reachable from the parent landed target (for example origin/main), bypass integration and durably stage the correct terminal child transition through TaskTransitionService/terminal-audit workflow. Never recreate a pruned terminal epic branch.\n- If the head is not landed but recoverable, create/route an explicit recovery container or target rather than repeatedly blocking against the deleted branch. Fail closed with one actionable reason when evidence is ambiguous or unreachable.\n- Do not consume one-shot retry_forced authority until all non-gate preconditions that can be validated first (including target selection/existence) are satisfied, or persist a retry receipt that can be safely restored when no gate attempt occurred.\n- Coordinate with OOMPAH-696/699 landing-evidence reconciliation and OOMPAH-836 durable integration actions; no legacy direct status writer.\n\nRequired tests:\n- Merged parent with pruned epic branch + Ready child exact head reachable from origin/main converges to audited terminal state without gate/recreated branch.\n- Same with a blocked integration row after claim/preflight restarts idempotently and retires the warning.\n- One-shot retry authority is not lost when target preflight fails before a gate runs.\n- A truly unlanded child gets a named recovery target or one fail-closed action, not a resubmit loop.\n- Archived parent, unreachable Git evidence, multi-project identical identifiers, and OOMPAH-523/OOMPAH-526 sibling ordering are covered.\n\nAcceptance criteria: a late/reopened child of a terminal pruned epic either converges from exact landing proof or receives one explicit recovery path; it never blocks forever on a branch that lifecycle cleanup intentionally deleted, and forced-gate retry authority is consumed exactly once only by an actual gate attempt.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


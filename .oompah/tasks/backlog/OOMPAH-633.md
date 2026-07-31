---
id: OOMPAH-633
type: bug
status: Backlog
priority: 1
title: Repair stale integration queues in nested epics
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T00:54:49.391955Z'
updated_at: '2026-07-31T00:54:49.391955Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: extend integration-queue stale-ancestry repair to nested epics whose target is a parent epic branch. The current _detect_and_repair_integration_queue_staleness_block returns False whenever target_branch starts with epic-, leaving OOMPAH-587 Ready rows at attempts=0 while completed sibling dependency OOMPAH-593 is reachable from origin/epic-OOMPAH-584 but not origin/epic-OOMPAH-587. Use the existing synchronization policy and rebase-task lifecycle to synchronize a nested epic only with its authoritative parent target, never an unrelated epic; preserve duplicate/cooldown fencing, finish dependencies, private heads, and terminal audits. Expose the same actionable rebase state. Relevant code: oompah/orchestrator.py stale queue detection, epic target resolution/synchronization, and tests/test_parallel_epic_children.py. Tests: nested parent target with terminal sibling dependency triggers exactly one repair; unrelated epic target remains denied; already reachable/nonterminal dependencies do not rebase; successful parent sync lets claim_next advance. Acceptance criteria: nested Ready queues cannot remain permanently attempts=0 solely because their parent advanced; focused queue/rebase tests and complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


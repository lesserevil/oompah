---
id: OOMPAH-633
type: bug
status: Open
priority: 1
title: Repair stale integration queues in nested epics
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T00:54:49.391955Z'
updated_at: '2026-07-31T01:01:55.913830Z'
work_branch: epic-OOMPAH-584--task-OOMPAH-633
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7828bd1be746e4dde6dc75e4afa947bd7d9a0f751c049d830782b73da2650fed
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 153c41f9-e15d-428c-803a-cb5cbd56f86c
  claim_owner: b1126b43-a708-4576-a58f-88442a7059a7
  claimed_at: '2026-07-31T01:01:46.218783+00:00'
  claim_expires_at: '2026-07-31T01:31:46.218783+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: a2ec708b-6be1-4f1d-aa98-be0be72eda11
oompah.work_branch: epic-OOMPAH-584--task-OOMPAH-633
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-584--task-OOMPAH-633
  base_branch: epic-OOMPAH-584
  base_sha: d62dd4cff702ae2b818418407d7d15b7a643213e
  updated_at: '2026-07-31T01:01:53.144332+00:00'
---
## Summary

Implementation scope: extend integration-queue stale-ancestry repair to nested epics whose target is a parent epic branch. The current _detect_and_repair_integration_queue_staleness_block returns False whenever target_branch starts with epic-, leaving OOMPAH-587 Ready rows at attempts=0 while completed sibling dependency OOMPAH-593 is reachable from origin/epic-OOMPAH-584 but not origin/epic-OOMPAH-587. Use the existing synchronization policy and rebase-task lifecycle to synchronize a nested epic only with its authoritative parent target, never an unrelated epic; preserve duplicate/cooldown fencing, finish dependencies, private heads, and terminal audits. Expose the same actionable rebase state. Relevant code: oompah/orchestrator.py stale queue detection, epic target resolution/synchronization, and tests/test_parallel_epic_children.py. Tests: nested parent target with terminal sibling dependency triggers exactly one repair; unrelated epic target remains denied; already reachable/nonterminal dependencies do not rebase; successful parent sync lets claim_next advance. Acceptance criteria: nested Ready queues cannot remain permanently attempts=0 solely because their parent advanced; focused queue/rebase tests and complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 00:54
---
Project-owner-approved live deadlock repair. Let the oompah server perform duplicate screening and implementation. The operator will separately reconcile the currently stale OOMPAH-587/588 branches so this code task does not circularly depend on its own deployment.
---
author: oompah
created: 2026-07-31 01:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 01:01
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

---
id: OOMPAH-846
type: bug
status: Open
priority: 1
title: Enforce validation-resource leases for every spawned worker command path
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:12:19.034116Z'
updated_at: '2026-08-06T04:16:54.443566Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-846
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b1eb4300e6f8f1f1f6ebbfef7a4c528408e31166bab0ca036707120e840ffa9f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: fd1b41b6-d205-406b-8ead-eb60b749d520
  claim_owner: 11468835-7c49-48df-a46d-b143af3a940a
  claimed_at: '2026-08-06T04:13:12.118732+00:00'
  claim_expires_at: '2026-08-06T04:43:12.118732+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 969feec9-63de-4079-b0d6-448f45f52875
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-846
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-846
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T04:13:38.002933+00:00'
---
## Summary

Live regression on 2026-08-06 after OOMPAH-816 reached Done: while the exact OOMPAH-831 gate owned the sole validation-resource slot, the OOMPAH-808 worker launched raw focused pytest and the OOMPAH-844 worker launched a raw make test process outside the durable lease. OOMPAH-844 make test remained alive when the scheduler started OOMPAH-791 exact gate, recreating the host saturation that OOMPAH-816 promised to prevent. OOMPAH-784/O845 commands used the mediated path and waited, proving command-path-dependent enforcement. Implementation scope: trace every spawned provider/native worker shell path (Codex/Claude/OpenCode/API/ACP) and install one fail-closed validation-resource guard before process launch; classify full Make targets and substantial pytest commands consistently; ensure exact gates own priority, queue time does not consume runtime deadline, cancellation/restart/fencing are preserved, and no environment/path variation can bypass the guard. Reuse OOMPAH-816 validation_resource_lease rather than building a parallel lock. Surface normal waits as informational and make bypass attempts observable without leaking command contents. Required tests: provider-native command execution from every backend while an exact gate owns capacity; raw make test, python -m pytest, uv run pytest, multi-file and compound commands; bounded node/small-file policy; cancellation/restart/owner death; prove at the process table boundary that no heavyweight child is spawned until lease acquisition; exact gate begins immediately after an earlier worker release. Acceptance: at configured capacity 1, no combination of server-spawned worker/auditor commands and exact gates can produce two concurrent heavyweight pytest trees, and all existing OOMPAH-816 security, timeout, fairness, and evidence-reuse tests remain green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 04:16
---
Second live reproduction at 04:14-04:17 UTC: OOMPAH-808 provider-native command spawned PYTHONPATH=. ... python -m pytest over tests/test_integration_record.py, tests/test_parallel_epic_children.py, and tests/test_epic_strategy.py while OOMPAH-791 exact gate was the sole recorded validation owner. No worker waiter/owner existed for OOMPAH-808. The exact sandbox process tree confirmed concurrent pytest. Operator terminated only the stray sandbox PID 2783035 after coordination; OOMPAH-808 edits and agent session remain intact. This three-file shape must classify heavyweight and must be blocked before spawn.
---
<!-- COMMENTS:END -->

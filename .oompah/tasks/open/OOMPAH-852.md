---
id: OOMPAH-852
type: bug
status: Open
priority: 1
title: Protect exact gates from concurrent focused validation commands
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:51:38.786179Z'
updated_at: '2026-08-06T04:53:14.285343Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-852
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8ad0ba722a7e5c3a7846477b5c8cfc67db681f9b2ccea62300fe250a2029f95a
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a29d8bd1-d517-426d-833b-5ded8fe29162
  claim_owner: 11468835-7c49-48df-a46d-b143af3a940a
  claimed_at: '2026-08-06T04:52:41.935629+00:00'
  claim_expires_at: '2026-08-06T05:22:41.935629+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 2e83615c-9fa9-4625-a634-b3949bed70ca
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-852
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-852
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T04:53:06.964358+00:00'
---
## Summary

Live regression at 2026-08-06T04:52Z: while OOMPAH-821 owned the only validation-resource slot for its authoritative make test, completion auditor OOMPAH-826 ran `python -m pytest tests/test_epic_strategy.py -x -q` as service child PID 3113755 for at least 226 seconds. validation_resources still reported only the OOMPAH-821 exact_gate owner and no auditor waiter because the named single-module pytest command is classified as bounded/light. Earlier OOMPAH-847 single-module commands caused D-state contention and contributed to unrelated five-second exact-gate failures. Implementation scope: distinguish harmless inspection from actual validation, and require every pytest/py.test/unittest invocation plus configured Make/tox/nox/npm/cargo validation target to participate in ValidationResourceLease even when selectors are focused; keep help/version/static inspection outside the lane. Preserve priority so exact gates and terminal auditors cannot starve, and ensure waits begin before process creation with truthful tool_liveness. Relevant files: oompah/validation_resource_lease.py classifiers, api_agent/acp_tools/native guard launch paths, and validation telemetry. Required tests: named and absolute Python single-test/module commands wait behind an exact gate; bounded commands run when capacity is available; help/version and non-test inspection do not lease; API, Claude ACP, Codex native, auditor, worker, cancellation, timeout, and restart paths; a real exact gate plus attempted focused test proves no overlapping test process; make test. Acceptance criteria: while an exact gate owns capacity, no worker or auditor test process exists outside its process tree; all waiters are visible and cancellable; after release they run exactly once; ordinary inspection remains concurrent; no global timeout is raised.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:53
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

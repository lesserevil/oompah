---
id: OOMPAH-811
type: task
status: Open
priority: null
title: Atomically rearm integration ownership when rebase advances the task head
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-768
labels: []
assignee: null
created_at: '2026-08-04T22:28:32.090875Z'
updated_at: '2026-08-04T22:59:19.269760Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d8d4771762019c61d2a7033903b4d7cacd621cacf0c783a2e3e879350014675a
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d2e3898c-f8a5-403a-9825-684aac807a92
  claim_owner: 209db773-bcba-4efb-b625-7acd11d20c5f
  claimed_at: '2026-08-04T22:58:45.716894+00:00'
  claim_expires_at: '2026-08-04T23:28:45.716894+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4ae7fb99-3b89-4854-8eb0-a14fb4ba1e9e
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-791 was submitted/queued at f8f9d382c43d4cc002f34cbcac0410e5c1f6f38e. The shared-epic integration executor rebased and pushed origin/epic-OOMPAH-768--task-OOMPAH-791 to 9e2ecc3f..., then attempted the combined-tree gate while its queue row/authority generation still named f8f9d382. Exact-head fencing correctly rejected the run with 'Quality gate owner metadata does not match the exact resolved candidate head', but the executor classified the normal branch advance as infrastructure_error and moved the task/row to Needs CI Fix/blocked even though no test ran.\n\nImplementation scope:\n- Make integration conflict-free rebase/push plus queue row, tracker oompah.integration record, and quality-gate authority generation advance one fenced transaction or restart-safe saga.\n- After a successful candidate-head rewrite, CAS the durable submission to the new remote head before requesting a gate; retire the old generation and reset/rearm attempts without exposing a mixed-head window.\n- If tracker/queue authority changed concurrently, discard the stale executor result without mutating task status; if push succeeds but metadata commit fails, recover the exact remote head deterministically on restart.\n- Classify an exact remote branch advance as superseded/requeued, not CI failure or infrastructure failure. Never send Needs CI Fix unless a gate actually ran and failed at the exact recorded head.\n- Preserve lease ownership, dependency heads, per-epic serialization, conflict repair, force-with-lease safety, and branch-mutation fencing from OOMPAH-684/697/724. Coordinate with OOMPAH-808 prerequisite reachability and the durable integration workflow rather than adding another local authority map.\n\nRelevant code: integration executor rebase/push result, IntegrationQueue CAS/update APIs, _process_integration_queues/_route_integration_failure, quality_gate owner metadata/generation, tracker integration-record writes, restart recovery.\n\nRequired tests:\n- Reproduce f8 -> 9e2 conflict-free rebase and prove the gate starts exactly once at 9e2 with matching queue/tracker/generation evidence.\n- Crash after push before queue metadata, after queue CAS before tracker write, and before gate launch; each restart converges to one exact new generation without Needs CI Fix.\n- Concurrent resubmit/operator branch advance causes stale result discard; genuine exact-head gate failure still blocks with Needs CI Fix.\n- Remote force-with-lease failure never rewrites durable authority.\n- Focused integration/executor/quality-gate/recovery tests and make test pass.\n\nAcceptance criteria: no integration-generated branch head can differ from its gate-owner metadata; successful rebases automatically rearm the exact new head; stale generations cannot run or poison tracker state; OOMPAH-791 flows from the advanced head without manual CI repair.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 22:59
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
<!-- COMMENTS:END -->

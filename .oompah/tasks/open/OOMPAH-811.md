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
updated_at: '2026-08-04T23:35:38.260931Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-811
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
  verdict: no_duplicate
  checked_at: '2026-08-04T23:04:15.195952+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-811 describes a specific bug in the integration\
    \ executor's handling of a conflict-free rebase/push: after the remote branch\
    \ head advances (f8f9d382 \u2192 9e2ecc3f), the queue row, tracker `oompah.integration`\
    \ record, and quality-gate authority generation still name the old head. The exact-head\
    \ fencing correctly rejects the gate attempt, but the executor misclassifies this\
    \ normal branch advance as `infrastructure_error` and sets the task to Needs CI\
    \ Fix even though no test ran. The fix requires an atomic saga: CAS-advance all\
    \ three durable records to the new head before requesting a gate, and classify\
    \ branch-advance as superseded/requeued rather than CI failure.\nFocus handoff:\
    \ duplicate_detector\nDuplicate preflight verdict: no_duplicate\nMatches: none\n\
    \nEvidence: OOMPAH-811 describes a specific bug in the integration executor's\
    \ handling of a conflict-free rebase/push: after the remote branch head advances\
    \ (f8f9d382 \u2192 9e2ecc3f), the queue row, tracker `oompah.integration` record,\
    \ and quality-gate authority generation still name the old head. The exact-head\
    \ fencing correctly rejects the gate attempt, but the executor misclassifies this\
    \ normal branch advance as `infrastructure_error` and sets the task to Needs CI\
    \ Fix even though no test ran. The fix requires an atomic saga: CAS-advance all\
    \ three durable records to the new head before requesting a gate, and classify\
    \ branch-advance as superseded/requeued rather than CI failure.\n\nThe closest\
    \ active non-terminal peer is **OOMPAH-806** (\"Fence stalled-task recovery behind\
    \ internal gate authority,\" Ready to Integrate), which addresses a distinct but\
    \ related failure mode \u2014 the stalled-task watchdog overriding an authoritative\
    \ internal gate failure when external CI passes. OOMPAH-806 fixes watchdog-vs-gate-authority\
    \ precedence; OOMPAH-811 fixes the failure to atomically update authority metadata\
    \ after a rebase-push. Different triggering conditions, different code paths (`stalled_task_watchdog.py`\
    \ vs. integration executor rebase/push result + queue CAS), different root causes,\
    \ and different required tests \u2014 they are complementary bugs, not duplicates.\n\
    \n**OOMPAH-768** (\"Migrate every workflow domain to shared decisions and durable\
    \ jobs,\" In Progress) is the parent epic covering integration queue migration\
    \ broadly; OOMPAH-811 is a specific correctness bug within that domain, not a\
    \ duplicate of the umbrella epic. **OOMPAH-808** (fence nested-epic dispatch)\
    \ and **OOMPAH-809** (scheduler lane capacity) are siblings covering entirely\
    \ different failure classes. All similarity-scored candidates (OOMPAH-1, OOMPAH-10,\
    \ OOMPAH-156, etc.) are in terminal states (Archived) and are excluded as duplicat"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4ae7fb99-3b89-4854-8eb0-a14fb4ba1e9e
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-811
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-811
  base_branch: epic-OOMPAH-763
  base_sha: 5cd24351e3b3f643bf4d43af84e81af0928b5f44
  updated_at: '2026-08-04T22:59:28.443522+00:00'
oompah.task_costs:
  total_input_tokens: 3
  total_output_tokens: 342
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 3
      output_tokens: 342
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 3
    output_tokens: 342
    cost_usd: 0.0
    recorded_at: '2026-08-04T23:04:15.194369+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-811__20260804T230012Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-811
    source_sha: 5cd24351e3b3f643bf4d43af84e81af0928b5f44
    completed_at: '2026-08-04T23:04:15.216058+00:00'
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
author: oompah
created: 2026-08-04 22:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 23:04
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 6, Tool calls: 0
- Tokens: 3 in / 342 out [345 total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 57s
- Log: OOMPAH-811__20260804T230012Z.jsonl
---
author: oompah
created: 2026-08-04 23:35
---
Read-only design audit reproduced the defect and recommends a durable two-generation saga rather than an in-memory owner rekey. G0/H0 may persist rearm intent and force-with-lease publish H1, but must not gate. A dedicated restart-safe rearm phase CASes queue + IntegrationRecord on exact project/task/branch/H0/G0/lease to G1/H1, verifies both projections, then exposes a fresh claim; only G1/H1 constructs QualityGateOwner and gates. Persist intent before push; recover remote=H0 by retrying push, remote=H1 by completing rearm, foreign remote by superseding without mutation. All complete/fail/cancel writes need head+generation+lease CAS. Map owner mismatch/stale/preflight/force-lease loss to reconcile, never Needs CI Fix; only a proven executed current-head gate failure may do that. Required tests: real f8→9e2 two-pass gate; crash at intent/push/queue/tracker boundaries; concurrent H2 resubmit; force-lease loss; genuine H1 failure; racing recovery workers; dependency/base/priority/per-epic preservation. Implement on durable integration workflow and land before OOMPAH-804 final composition.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-858
type: task
status: Open
priority: null
title: Exclude nested-container rollup edges from child integration dependencies
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T09:23:22.752195Z'
updated_at: '2026-08-06T09:36:00.357557Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-858
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b246bd903dc87ce89edfb8c74322723bde4e0b6f84a19e884acf560e0426765a
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 638791e5-1727-4589-a020-9a3dcaa7cedb
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T09:35:40.775858+00:00'
  claim_expires_at: '2026-08-06T10:05:40.775858+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5b29980a-9b9a-4959-86e2-5b04287e09b2
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-858
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-858
  base_branch: epic-OOMPAH-763
  base_sha: 52cf744ab676b50bdb999e9b0feb39bc092418c1
  updated_at: '2026-08-06T09:35:55.856464+00:00'
---
## Summary

Live OOMPAH-804/834 deadlock on 2026-08-06: OOMPAH-804 is a task with decomposition children OOMPAH-834..837 and has finish dependencies on those children for parent rollup. IntegrationQueue._integration_dependency_map calls effective_dependencies for OOMPAH-834, which inherits all OOMPAH-804 dependencies. The resulting queue row waits on OOMPAH-834 itself and its siblings to pass terminal audit, so no child can ever integrate and the parent can never roll up. The dashboard reported waiting_on OOMPAH-834/835/836/837 plus already-terminal external prerequisites. Implementation scope: make ordered integration distinguish externally inherited finish-order prerequisites from parent/container rollup edges to the current descendant set; never include the queued task itself; preserve legitimate ancestor dependencies outside the current delivery container and ordinary sibling dependencies explicitly declared on the child. Keep the rule project-scoped and apply the same normalized dependency projection to eligibility, queue diagnostics, container-cycle analysis, restart recovery, and executor generation fencing. Relevant code: oompah/dependency_graph.py effective_dependencies or a typed integration dependency projection, oompah/orchestrator.py _integration_dependency_map/_integration_satisfied_dependencies, oompah/server.py integration queue summary, and container dependency graph helpers. Required tests: exact nested parent->children rollup graph reproducing OOMPAH-804/834; self and sibling rollup edges excluded; explicit child->sibling and external ancestor dependencies retained; no-op/ancestor-composed heads integrate in deterministic order; restart with durable ready rows; diagnostics match executor; top-level epic children and standalone delivery unchanged. Acceptance: every eligible nested child can acquire a queue lease without waiting on itself or implicit parent rollup siblings, while real finish-order constraints remain enforced and no global/manual status mutation is required.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 09:25
---
Additional live finding: after removing the implicit parent->child rollup edges, OOMPAH-834 still waited on already-terminal external prerequisites because _integration_satisfied_dependencies and _execute_integration_item derive origin/epic-OOMPAH-804 from queue.epic_id. The authoritative nested delivery target recorded by submission is epic-OOMPAH-768--task-OOMPAH-804. The executor ignores IntegrationRecord.base_branch, so eligibility reachability, worktree creation, integration, and persisted base_branch can all use a stale sibling branch. The fix must resolve and fence the exact recorded immediate-parent target consistently; add a divergent stale epic-OOMPAH-804 alias regression. Task-scoped workaround will preserve the stale target under a backup ref and align the alias to the already validated f89c477d parent head so the deployed executor can complete the existing queue safely.
---
author: oompah
created: 2026-08-06 09:31
---
Third live failure mode: when a child submitted head is already an ancestor of the current nested target, execute_integration resolves the combined candidate to the newer target head but keeps QualityGateOwner.head_sha at the older submitted head. The exact-head gate correctly refuses with owner metadata mismatch, the queue blocks, and repair dispatches unnecessarily. Production fix must canonicalize submitted/already-integrated delivery to the resolved candidate head atomically across queue generation, owner, gate, commit_allowed, integration metadata, and audit evidence; add an ancestor/no-op nested child regression that proves one gate and no repair worker.
---
author: oompah
created: 2026-08-06 09:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 09:36
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

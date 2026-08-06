---
id: OOMPAH-858
type: task
status: Backlog
priority: null
title: Exclude nested-container rollup edges from child integration dependencies
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T09:23:22.752195Z'
updated_at: '2026-08-06T09:25:39.156346Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->

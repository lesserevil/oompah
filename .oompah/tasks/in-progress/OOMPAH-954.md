---
id: OOMPAH-954
type: bug
status: In Progress
priority: 1
title: Compose canonical epic facts in universal workflow decisions
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:29:27.319915Z'
updated_at: '2026-08-09T11:30:12.452199Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by PR #757 hosted CI run 31310033950 and OOMPAH-945. All Python 3.11-3.13 jobs deterministically fail the OOMPAH-748 production-stack incident because work_decision now correctly requires canonical epic containment (epic_branch and target_branch) while Orchestrator._collect_universal_workflow_facts still composes the generic WorkflowFactCollector containment projection (parent_id and children only). This also makes universal liveness/UI publish evidence.containment_malformed for valid landed Done epics while the dedicated epic lane reaches terminal.immediate_target_landing_proven. Scope: based on the exact OOMPAH-940 aggregate head and targeting epic-OOMPAH-940, route epic tasks in universal fact collection through the canonical EpicFactCollector using the project repo/default branch and the same production sources as scheduler/shadow composition; update the OOMPAH-748 production-stack replay to exercise that production epic collector path. Do not restore mutable task-field fallback or weaken fail-closed containment validation. Required tests: exact failing OOMPAH-748 replay; universal/UI and epic scheduler agree on terminal.immediate_target_landing_proven; malformed and wrong-target containment remain fail-closed; full incident module, universal decision/cache and epic workflow suites; aggregate protected branch gate. Acceptance: PR #757 passes its full Python matrix, universal/scheduler/UI decisions share one canonical reason, and no incomplete generic containment is used for epic universal decisions.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


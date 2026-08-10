---
id: OOMPAH-1003
type: bug
status: Backlog
priority: 1
title: Revalidate root epic auto-close from durable landing authority without a mutable
  issue head
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T19:11:49.831627Z'
updated_at: '2026-08-10T19:11:49.831627Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: o940-root-epic-auto-close-null-head
  request_fingerprint: 6e42d1ebee1399c57ba567812850dfa474f446e9fa9271a6cee34474222ffa31
---
## Summary

Triggered by the live OOMPAH-940 rollout at workflow generations 1564-1571. Problem: universal workflow decisions correctly accept the durable root-epic landing fact epic-OOMPAH-940 -> main at 2dd74be288b81265ea4a242d7467ecc1ed9f1435 and enqueue epic_auto_close, but EpicWorkflow._is_action_current(AUTO_CLOSE) requires that landed revision to equal issue_exact_head(snapshot.epic). OOMPAH-940 has intentionally null work_branch, target_branch, review_head, and exact mutable head after landing, so every auto-close job is claimed then superseded as 'workflow evidence changed after job enqueue'; the action can never succeed. Scope: make epic auto-close worker revalidation consume the same canonical durable landing authority and target identity as universal decision construction, while fencing task/project/evidence-generation changes and preserving fail-closed behavior for ambiguous or stale facts. Do not reintroduce mutable-head authority and do not direct-edit task or workflow data. Relevant code: EpicWorkflow AUTO_CLOSE decision/current-action validation and workflow job authority snapshots; compare the composed/null-head parent_rollup_review fix in OOMPAH-975. Required tests: reproduce a root epic with null issue_exact_head plus an exact current durable landing fact, prove auto-close remains current and reaches terminal flow, and prove mismatched revision/target/generation or changed task authority is rejected. Acceptance: OOMPAH-940 naturally leaves In Progress after deployment, no epic_auto_close supersession loop remains, a complete published scan has zero current divergence/exhaustion/action_required, and make workflow-rollout-check passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


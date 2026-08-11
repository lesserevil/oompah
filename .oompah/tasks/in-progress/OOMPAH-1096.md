---
id: OOMPAH-1096
type: task
status: In Progress
priority: null
title: Prevent unrelated tracker churn from starving exact Ready-work publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T17:33:22.243112Z'
updated_at: '2026-08-11T17:35:03.020365Z'
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
  creation_marker: 9bd7eafe-8b80-4e48-830b-3a29b5bfa538
  request_fingerprint: 99c02ef95efb85612c63db568b0bc0b8a0c40ff0fd752d3bcd2746f9bc53f74d
---
## Summary

Bug observed live on 2026-08-11: workflow jobs 5180 (OOMPAH-1091 review_merge), 5181 (OOMPAH-1085 standalone_delivery), and 5182 (OOMPAH-1095 standalone_delivery) were all superseded at 17:27:53 UTC with 'workflow snapshot publication did not commit' while unrelated terminal auditors were posting task/comment/status updates. Exact heads remained unchanged; PRs #827 and #830 were clean with all protected CI green, yet no replacement intent was materialized beyond the configured review reassessment window. Implementation scope: workflow snapshot publication/reconciliation and exact durable job materialization. Prevent unrelated project tracker revision churn from starving a task whose own evidence/authority is unchanged. Preserve fail-closed behavior for relevant task/head/authority changes, exact idempotency, and no duplicate forge effects. Add deterministic concurrency tests with continuous unrelated task/comment churn proving the eligible task publishes/requeues a current exact job within its bounded SLO, plus restart/retry coverage. Acceptance: eligible Ready/In Review work progresses during unrelated tracker churn; relevant evidence drift still supersedes stale work; observability distinguishes bounded retry from overdue starvation; full focused workflow/publication tests and workflow soak pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


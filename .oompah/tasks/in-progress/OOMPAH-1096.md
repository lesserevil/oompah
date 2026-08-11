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
updated_at: '2026-08-11T17:48:59.269244Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 17:48
---
Implementation is committed and pushed at exact head 1cade67f25011c1e94df187f737957d5e8bad67b on branch OOMPAH-1096, rebased patch-equivalently onto current origin/main b948150a8. The workflow snapshot publisher now consumes the existing managed per-task publication journal: a final revision advance is accepted only when the journal is complete, the delta is nonempty and exactly matches the observed counter, at least one exact durable action is staged, and every changed task is disjoint from staged effect identities and dependency targets. Journal-proven unrelated tasks are excluded from the projection and mark the liveness cut intentionally incomplete; exact task drift, dependency drift, ambiguous membership, missing history, and unknown scope still supersede and retry the whole generation. Observability records tracker_scoped_publication_advances/exclusions separately from scoped_publication_retries. Deterministic regressions cover a 64-write continuous unrelated burst publishing review_merge on the first cut, relevant exact-task drift forcing a fresh generation, durable-store restart reusing one exact job, and health projection remaining non-overdue. Verification after rebase: 446 focused workflow job/controller/runtime/cache/tracker-lock tests passed; make workflow-soak-ci completed 120 tasks with 380 projection checks, 0 mismatches, 1 expected actionable alert, and no unexplained tasks; make terminal-audit-scan passed 21/21; py_compile, diff check, secret hooks, and range-diff clean. No full 20k gate was run per handoff. Not submitted; awaiting independent exact-head review.
---
<!-- COMMENTS:END -->

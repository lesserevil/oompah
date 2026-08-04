---
id: OOMPAH-765
type: epic
status: Backlog
priority: 1
title: Build unified versioned facts and a pure WorkDecision evaluator
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:55:54.087142Z'
updated_at: '2026-08-04T13:55:54.087142Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Create versioned WorkflowFacts and a pure evaluate_task(task, facts) -> WorkDecision engine. Facts must normalize tracker state, dependencies, containment, integration records/queue rows, terminal audit records, review/CI state, Git/forge landing evidence, ownership generations, retry budgets, and configuration. WorkDecision must be total for every task and return disposition (runnable, owned, blocked, retry_scheduled, action_required, terminal), stable reason code, responsible owner type, unmet prerequisites, evidence revision, next reassessment time, permitted actions, action_required flag, and alert level. Centralize dependency satisfaction, target/landing resolution, and retry classification. Run shadow evaluation without mutations, compare with legacy scheduler/UI/watchdog decisions, and expose a diagnostic API. Required tests: pure table-driven decisions, deterministic evidence revisions, multi-project scope, missing/stale/error facts, nested epic landing, cross-epic dependencies, and shadow disagreement telemetry. Acceptance: every nonterminal task produces a deterministic decision; scheduler, UI, and liveness consumers can use the same object; unexplained shadow divergences are zero before enforcement.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


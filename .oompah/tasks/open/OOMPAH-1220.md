---
id: OOMPAH-1220
type: task
status: Open
priority: null
title: Defer shared-child Merged transitions until the parent rollup is terminal
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T04:40:53.600135Z'
updated_at: '2026-08-13T04:51:36.239714Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 6491613b-cadb-45fd-bc25-919e0fd32fb0
  request_fingerprint: 84197b591728a766bfc9e0854826f9a889ab47127f7218b3446c07dbbdb06975
oompah.lifecycle_revision: 1
---
## Summary

### Problem

A Done shared-epic child whose own commit is proven on the parent epic branch evaluates to `terminal.immediate_target_landing_proven` and schedules `parent_rollup_review` immediately. The terminal coordinator correctly rejects Merged while the parent epic has not landed on its configured target. The job exhausts as `transition.terminal_rejected`; restart liveness then requires the exhausted obligation but cannot prove it materialized. Worker admission fails closed at 20/21 obligations and every runnable task is stalled. Live reproduction: TRICKLE-129 under parent TRICKLE-127 after deploying eb281f1e.

### Implementation scope

Make the canonical integration decision include the current parent lifecycle state for a Done shared child. Keep the child at Done with a non-alerting, reassessed blocked decision and no executable terminal job until its current parent is Merged or Archived. Once the parent is terminal, retain the existing exact composed-landing proof and schedule `parent_rollup_review`. Fail closed when parent identity/state cannot be read. Preserve nested-epic behavior and standalone/top-level task behavior.

Relevant files:
- oompah/workflow_facts.py
- oompah/work_decision.py
- oompah/integration_workflow.py only if required
- tests/test_work_decision.py
- tests/test_integration_workflow.py
- focused restart/liveness tests as needed

### Required tests

- A Done ordinary child with exact landing on its parent branch and a nonterminal parent remains Done, has no parent_rollup_review job, and is not action-required.
- The same child schedules parent_rollup_review after the exact current parent becomes Merged or Archived.
- Missing/reparented parent authority fails closed without an executable terminal job.
- Restart reconciliation counts the deferred child as explained rather than an unmaterialized recovery obligation.
- Existing exact-head, ABA, nested-epic, and top-level landing fences remain intact.

### Acceptance criteria

- Shared-child terminal decisions agree with terminal coordinator policy.
- Restart convergence cannot be held at N-1 by a predictably rejected parent_rollup_review.
- Trickle restart liveness becomes complete and corrected workers can be admitted.
- Focused tests and the complete Makefile quality gate pass; reviewed change is merged and deployed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 04:46
---
Live root cause confirmed: TRICKLE-129 was the single missing restart obligation (20/21), because its parent_rollup_review is correctly terminal-rejected while parent TRICKLE-127 is nonterminal. Patch now snapshots exact parent identity/type/status into task facts and returns a non-alerting, jobless rollup.waiting_parent_landing decision until the parent is Merged/Archived. Tests prove zero jobs before parent landing and one exact parent_rollup_review afterward. Focused results: work decision 101 passed; integration workflow 147 passed; workflow facts/owner delivery 63 passed; restart/runtime selection 15 passed.
---
author: oompah
created: 2026-08-13 04:51
---
Fix committed and pushed as 1c01057b; PR #850 is running CI. Exact parent authority now keeps a landed shared child in a jobless rollup wait until its parent epic is Merged or Archived, preventing the rejected terminal job from holding restart reconstruction at N-1. Focused regression suites: 312 passed plus 15 runtime restart/rollup tests.
---
<!-- COMMENTS:END -->

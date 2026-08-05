---
id: OOMPAH-837
type: task
status: In Progress
priority: 1
title: Bind epic rollup, delivery, repair, and cleanup to durable handlers
parent: OOMPAH-804
children: []
blocked_by:
- OOMPAH-791
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:45.984953Z'
updated_at: '2026-08-05T17:02:58.678279Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Add EpicWorkflowBackend/EpicWorkflowHandler production contracts and handlers for all ten actions: readiness, rollup reconciliation, child landing verification, rollup review creation, target resolution, auto close, terminal validation, rebase repair, cleanup, and restart reconciliation. Use fresh EpicFactCollector containment/LandingFacts, persist evidence only in enforce mode, build terminal TaskTransitionService intents, and extract exact one-epic review creation, rebase helper, and cleanup bodies from legacy sweeps. Wire production schedule_action wakes for parent/child/target changes, restart, rebase requests, and terminal cleanup. Relevant files: oompah/epic_workflow.py, oompah/workflow_runtime.py or typed adapter modules, orchestrator epic rollup/open-review/rebase/cleanup paths. Required tests: nested epics, immediate-parent targets, child arrival permutations, stale landing evidence, exact review/head CAS, restart after effect before verify, rebase helper idempotency, terminal cleanup evidence, multi-project routing, and shadow zero-write/enforce single-writer behavior. Acceptance: every epic action has a real project-bound handler/event source; no parent-child proof cycle or legacy rollup writer remains active in enforce mode; effects are exactly replayable after restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


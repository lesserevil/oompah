---
id: OOMPAH-837
type: task
status: In Progress
priority: 1
title: Bind epic rollup, delivery, repair, and cleanup to durable handlers
parent: OOMPAH-804
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:45.984953Z'
updated_at: '2026-08-06T09:39:37.003086Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-837
  head_sha: f89c477d4c03a8992a7278337182c0352da5de16
  submitted_at: '2026-08-06T09:39:35.189606+00:00'
  updated_at: '2026-08-06T09:39:35.189606+00:00'
---
## Summary

Add EpicWorkflowBackend/EpicWorkflowHandler production contracts and handlers for all ten actions: readiness, rollup reconciliation, child landing verification, rollup review creation, target resolution, auto close, terminal validation, rebase repair, cleanup, and restart reconciliation. Use fresh EpicFactCollector containment/LandingFacts, persist evidence only in enforce mode, build terminal TaskTransitionService intents, and extract exact one-epic review creation, rebase helper, and cleanup bodies from legacy sweeps. Wire production schedule_action wakes for parent/child/target changes, restart, rebase requests, and terminal cleanup. Relevant files: oompah/epic_workflow.py, oompah/workflow_runtime.py or typed adapter modules, orchestrator epic rollup/open-review/rebase/cleanup paths. Required tests: nested epics, immediate-parent targets, child arrival permutations, stale landing evidence, exact review/head CAS, restart after effect before verify, rebase helper idempotency, terminal cleanup evidence, multi-project routing, and shadow zero-write/enforce single-writer behavior. Acceptance: every epic action has a real project-bound handler/event source; no parent-child proof cycle or legacy rollup writer remains active in enforce mode; effects are exactly replayable after restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 19:59
---
Post-review repairs complete. Cleanup now locks/revalidates epic authority before every child deletion, requires terminal lifecycle plus exact own landing for Merged epics (including remote-only top-level branches), and verifies exact remote generations before CAS deletion. Shielded external mutations are included in runtime drain; runtime/store closure fails closed while operations remain. Real Orchestrator staged composition now proves enforce mode refuses partial sibling coverage instead of relying on fakes. The first focused run exposed four test/fixture integration issues; repaired terminal fixture authority, atomic remote-delete expectation, handler-drain scheduling, and exact revalidation evidence. Final focused gate passed: terminal mutation scan green and 419/419 epic adapter/controller, project cleanup, transition service, runtime, rebase-state, and webhook tests passed in 67.78s. Awaiting one fresh independent final review before commit.
---
<!-- COMMENTS:END -->

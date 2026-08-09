---
id: OOMPAH-948
type: bug
status: Open
priority: 1
title: Bound terminal branch cleanup as durable fair maintenance
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:56:00.569098Z'
updated_at: '2026-08-09T09:56:33.498190Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-947

Live regression observed during the 2026-08-09 OOMPAH-939 rollout: after the orchestrator quiesced at 09:46:21, an already-started maintenance tick walked terminal branch cleanup across the full multi-project historical corpus until at least 09:54:46, logging dozens of nested-parent deferrals and a final 178-branch skip aggregate. This independently holds the event loop and graceful drain for minutes even when audit scanning is bounded. Scope: replace the monolithic terminal branch cleanup sweep with a durable project/task cursor and explicit scheduler-scale operation/time slice; keep exact ownership, accepted-target, shared-epic, nested-topology, and deletion safety fences; persist progress across restart; coalesce an immediate continuation only while eligible cleanup remains; separate bounded actionable work from complete historical observability. Relevant code: orchestrator terminal branch cleanup/maintenance scheduling, project cleanup helpers, workflow maintenance cursors and tick telemetry. Required tests: thousands of terminal/shared/nested rows keep one invocation below the configured deterministic budget; a Ready integration claim progresses between slices; cursor survives restart and visits every project/task fairly; quiesce/drain stops after the current bounded unit; no duplicate or unsafe deletion; partial health remains truthful; existing cleanup safety tests remain green. Acceptance: terminal cleanup cannot monopolize an event-loop tick or graceful restart for minutes, live telemetry shows bounded fair convergence, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


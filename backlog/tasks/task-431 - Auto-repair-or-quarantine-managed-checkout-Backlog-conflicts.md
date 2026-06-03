---
id: TASK-431
title: Auto-repair or quarantine managed checkout Backlog conflicts
status: Open
assignee: []
created_date: '2026-06-03 06:16'
labels:
  - bug
  - backlog
  - orchestrator
dependencies: []
priority: high
ordinal: 67000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Managed project checkouts can accumulate unresolved Git conflicts in backlog task files when oompah and remote updates both edit task metadata. We saw this in Aethel TASK-3.1/TASK-8.3 and in the managed oompah checkout TASK-407.11/TASK-427/TASK-428. When a Backlog task file contains conflict markers or otherwise invalid YAML/frontmatter, BacklogMdTracker skips the task and the dashboard becomes inconsistent with reality.

Implement startup and project-sync handling so oompah never silently runs with a managed checkout that has unresolved Backlog conflicts. The handler should inspect each managed repo for unmerged paths and Backlog parse failures before scheduling. For conflicts limited to backlog task files, attempt a deterministic structured repair that preserves both sides where possible: canonical lifecycle status, comments, final summary, oompah.task_costs, dependencies, labels, parent_task_id, and the newest meaningful updated_date. After repair, validate with BacklogMdTracker/backlog CLI parsing before allowing the project to schedule.

If repair cannot be proven safe, quarantine or pause that project, surface a dashboard alert with the project name and conflicted paths, and avoid dispatching tasks from that project until the checkout is repaired. Do not leave tasks invisible or schedulable from partially parsed state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Startup checks every managed checkout for unmerged Git paths and invalid Backlog task frontmatter before dispatch.
- [ ] #2 Backlog-only conflicts get an automatic structured merge that preserves comments, final summary, oompah.task_costs, dependencies, labels, parent_task_id, and valid lifecycle status.
- [ ] #3 Automatic repair validates the resulting task files through the same parser used by BacklogMdTracker before the project can schedule.
- [ ] #4 Unrepairable conflicts pause or quarantine only the affected project and show a dashboard alert naming the project and conflicted files.
- [ ] #5 Regression tests cover auto-repair, unrepairable quarantine/alert behavior, and prevention of task scheduling from an invalid managed checkout.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Use the Backlog CLI or BacklogMdTracker parser for validation instead of ad hoc string checks.
- [ ] #2 make test passes.
<!-- DOD:END -->

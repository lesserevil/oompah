---
id: TASK-402.13
title: Reconcile stale Backlog In Progress tasks after hard restart
status: Done
assignee:
  - oompah
created_date: '2026-06-01 20:40'
updated_date: '2026-06-09 00:29'
labels:
  - bug
  - 'needs:backend'
  - 'needs:test'
dependencies: []
parent_task_id: TASK-402
priority: high
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context
After fixing the dashboard-only project-scoping issue and restarting oompah on 2026-06-01, the live API still showed Backlog.md tasks in `In Progress` with no tracked running agent. This regresses the behavior claimed complete in `TASK-402.11`.

Observed from `/api/v1/state` and `/api/v1/issues?project_id=...` on port 8090 after restart:
- Running agents: `oompah-397`, `trickle-262`, `trickle-263`
- Board still showed additional In Progress cards without tracked running agents: `oompah-389`, `oompah-399`, `trickle-264`, `trickle-265`, `trickle-267`

This is not the dashboard optimistic-render bug fixed in the current session. The board data is coming from Backlog.md task state. Operators still see stale In Progress work even after the running-agent list has moved on.

## Expected behavior
After startup/restart reconciliation, every Backlog.md task shown in the dashboard In Progress column should either have a tracked running/retrying agent, or be reset/recovered according to the configured workflow.

## Investigation notes
- `TASK-402.11` says orphan cleanup for Backlog `In Progress` tasks is fixed, but the live service still exhibits stale In Progress cards after hard restart.
- Check whether orphan cleanup runs during startup, during dispatch-only paths, or only after specific event-driven ticks.
- Include multi-project Backlog task ids in the test case because duplicate `TASK-N` identifiers across projects can mask the issue.

## Acceptance criteria
- A hard restart with Backlog tasks in `In Progress` but no tracked running/retrying agent reconciles those tasks deterministically.
- Dashboard board data no longer shows stale In Progress cards indefinitely after restart.
- Running/retrying agent state and project-scoped board data agree for both `oompah` and `trickle` projects.
- Regression tests cover startup/restart reconciliation and multi-project duplicate Backlog task identifiers.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed as part of the Backlog-only tracker migration. Removed Beads/bd runtime paths where applicable, moved lifecycle behavior to canonical Backlog.md statuses, updated UI/API/tests/docs for Backlog-only behavior, and verified with make test: 3677 passed.
<!-- SECTION:FINAL_SUMMARY:END -->

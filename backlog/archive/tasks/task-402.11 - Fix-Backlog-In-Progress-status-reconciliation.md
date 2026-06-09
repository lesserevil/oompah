---
id: TASK-402.11
title: Fix Backlog In Progress status reconciliation
status: Done
assignee: []
created_date: '2026-06-01 19:30'
updated_date: '2026-06-09 00:29'
labels:
  - bug
dependencies: []
parent_task_id: TASK-402
priority: high
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Oompah incorrectly treats Backlog.md status 'In Progress' as different from legacy internal state 'in_progress'. The reconcile path logs 'no longer in_progress ... state=In Progress', terminates live agents, and leaves stale In Progress task files without running agents. Orphan cleanup has the same hard-coded comparison. Fix status normalization so Backlog 'In Progress', 'in_progress', and 'in-progress' compare equivalently; update RunningEntry.issue after dispatch sets status to In Progress; and add tests for reconcile/orphan cleanup behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Reconcile does not terminate a running agent whose tracker state is Backlog 'In Progress'.
- [x] #2 Orphan cleanup can reset Backlog 'In Progress' tasks with no running agent or retry.
- [x] #3 RunningEntry.issue reflects the tracker state after dispatch sets a task to In Progress.
- [x] #4 Status normalization handles 'In Progress', 'in_progress', and 'in-progress' consistently.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed as part of the Backlog-only tracker migration. Removed Beads/bd runtime paths where applicable, moved lifecycle behavior to canonical Backlog.md statuses, updated UI/API/tests/docs for Backlog-only behavior, and verified with make test: 3677 passed.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Focused tests cover reconcile, orphan cleanup, and dispatch running-entry state update.
- [x] #2 make test passes.
<!-- DOD:END -->

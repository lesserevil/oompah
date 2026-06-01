---
id: TASK-402.5
title: Update dashboard and APIs for canonical Backlog statuses
status: Open
assignee: []
created_date: '2026-06-01 19:20'
updated_date: '2026-06-01 21:57'
labels:
  - task
dependencies:
  - TASK-402.4
parent_task_id: TASK-402
priority: high
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update the HTTP API and dashboard to use Backlog.md statuses directly instead of the legacy deferred/open/in_progress/closed board model.

Context:
- server.py currently maps tracker-native statuses into legacy dashboard states with _dashboard_state.
- dashboard.html hard-codes four columns: deferred, open, in_progress, closed.
- The new Backlog model has many statuses and should not hide state in labels or has_open_review booleans.

Work required:
- Replace or retire _dashboard_state so API responses expose canonical Backlog statuses.
- Update board columns to include or group canonical statuses in an operator-friendly order.
- Update drag/drop so moving a card writes the exact Backlog status.
- Update child counts to be dynamic by status rather than hard-coded deferred/open/in_progress/closed.
- Update the In-flight only filter to keep Open, In Progress, In Review, Needs CI Fix, and Needs Rebase.
- Update badges and UI text that currently rely on merged/draft/lifecycle labels.
- Preserve draft epic behavior intentionally: decide whether draft remains an epic presentation label or becomes a status, and document the decision in the task notes.

Files to inspect first:
- oompah/server.py
- oompah/templates/dashboard.html
- tests/test_dashboard_hide_merged.py
- tests/test_draft_epic_kanban.py
- tests/test_draft_epic_swimlane.py
- tests/test_collapsed_epics.py
- tests/test_server_epic_state.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The dashboard renders Backlog statuses directly or through an explicitly documented grouping.
- [ ] #2 Moving a task in the dashboard writes the intended Backlog status.
- [ ] #3 In-flight filtering no longer depends on the merged label or closed plus has_open_review.
- [ ] #4 Epic child counts work for all canonical statuses.
- [ ] #5 Backlog and Open render as separate dashboard columns with separate dispatch semantics.
- [ ] #6 The dashboard does not render a To Do column and drag/drop never writes To Do.
- [ ] #7 Waiting and triage status groups are minimized when empty and expand automatically when they contain tasks.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Update server serialization to send canonical status and status metadata.
2. Replace hard-coded frontend column constants with the canonical status order.
3. Adjust filters, child counts, swimlane rendering, and drag/drop status writes.
4. Update dashboard tests for the new statuses and remove legacy closed-with-has_open_review assumptions.
5. Verify dashboard behavior with focused tests; use browser/screenshot checks if visual behavior changes substantially.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dashboard column decisions from planning: Backlog and Open are distinct canonical statuses. Backlog means not ready and not dispatchable. Open means ready for work and dispatchable. To Do is not a valid oompah lifecycle status and should only be handled as a migration/bootstrap alias. The dashboard should not render a To Do column and drag/drop should never write To Do. Waiting statuses (Needs Answer, Needs Human) and triage statuses (Decomposed, Duplicate Candidate) should not consume full board width when empty; render those groups as minimized/collapsed lanes or compact affordances when they contain zero tasks, then expand automatically when tasks exist.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Relevant server and dashboard tests pass.
- [ ] #2 No frontend code assumes only deferred/open/in_progress/closed states.
<!-- DOD:END -->

---
id: TASK-402.7
title: Rename live Beads terminology to Backlog task terminology
status: Open
assignee: []
created_date: '2026-06-01 19:20'
updated_date: '2026-06-01 19:21'
labels:
  - task
dependencies:
  - TASK-402.4
  - TASK-402.5
  - TASK-402.6
parent_task_id: TASK-402
priority: high
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rename live runtime, API, and UI wording from bead/bd terminology to task/Backlog terminology.

Context:
- The codebase still uses bead wording in comments, logs, dashboard text, error messages, tests, and docs.
- Once Beads support is removed, live operator-facing text should not call tasks beads or suggest bd commands.
- Do not churn historical completed task descriptions unless needed for code/tests.

Work required:
- Update operator-facing text in dashboard templates from bead/beads to task/tasks or issue/issues as appropriate.
- Update runtime logs and error messages to avoid bd-specific remediation.
- Update comments/docstrings in active code that describe current behavior.
- Update test names/assertions that encode Beads terminology for live behavior.
- Leave historical data under backlog/completed alone unless a test imports or parses it as active documentation.

Files to inspect first:
- oompah/templates/dashboard.html
- oompah/orchestrator.py
- oompah/server.py
- oompah/api_agent.py
- oompah/acp_tools.py
- oompah/acp_agent.py
- oompah/landing_gate.py
- README.md
- docs/
- plans/
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Operator-facing UI and API errors no longer tell users to run bd or refer to live work as beads.
- [ ] #2 Active code comments describe Backlog.md behavior, not Beads behavior.
- [ ] #3 Any remaining bead/bd references are either historical task data or explicitly documented exceptions.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Use rg to inventory bead/bd wording outside backlog task history.
2. Classify each hit as runtime/operator-facing, active code comment, active doc, test, or historical data.
3. Update runtime/operator-facing text first.
4. Update tests and active documentation.
5. Record any deliberately retained historical references in the task notes.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 rg-based terminology audit is included in the final task comment.
- [ ] #2 Relevant UI/server tests pass.
<!-- DOD:END -->

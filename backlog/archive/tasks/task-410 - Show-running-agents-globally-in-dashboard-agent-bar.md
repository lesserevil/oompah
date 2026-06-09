---
id: TASK-410
title: Show running agents globally in dashboard agent bar
status: Done
assignee: []
created_date: '2026-06-02 00:53'
updated_date: '2026-06-02 00:55'
labels:
  - bug
dependencies: []
priority: high
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard currently filters running-agent chips by the selected project filter. That makes the agent bar show no running agents when the operator is viewing a different project, even though /api/v1/state reports active agents elsewhere. Update the UI so the running-agent list remains globally visible and labels each agent with its project-aware display id. Keep the project-filtered board behavior unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Running-agent chips are rendered from all state.running entries, not hidden by the selected project filter.
- [ ] #2 The Agents count in the top bar reflects total running agents.
- [ ] #3 Project-specific task boards remain filtered by the selected project.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated the dashboard agent bar so running-agent chips and the Agents count use all state.running entries globally instead of filtering by the selected project. The project-filtered board and issue fetch behavior remain unchanged. Verification: uv run pytest tests/test_dashboard_running_agent_project_filter.py tests/test_dashboard_dispatch_optimistic.py -q passed; make test passed with 3681 passed, 17 warnings.
<!-- SECTION:FINAL_SUMMARY:END -->

---
id: TASK-411
title: Hide empty Needs CI Fix and Needs Rebase dashboard columns
status: Done
assignee:
  - oompah
created_date: '2026-06-02 02:27'
updated_date: '2026-06-02 02:29'
labels:
  - task
dependencies: []
priority: medium
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard already treats Needs Answer and Needs Human as conditional columns that only appear when tasks exist in those states. Extend that same behavior to Needs CI Fix and Needs Rebase so those columns do not take space on the board when they are empty. Keep the columns visible whenever there is at least one task in the corresponding state, including under the in-flight-only toggle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Needs CI Fix does not render as an empty dashboard column.
- [ ] #2 Needs Rebase does not render as an empty dashboard column.
- [ ] #3 Both columns render when tasks exist in those states.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed the dashboard Needs CI Fix and Needs Rebase column configuration to conditional columns, while preserving their in-flight filtering behavior when tasks exist in those states. Added tests/test_dashboard_conditional_columns.py to lock the column metadata and visibleColumns rule. Verified with uv run pytest tests/test_orchestrator_merged.py tests/test_dashboard_conditional_columns.py -q and make test (3685 passed, 18 warnings).
<!-- SECTION:FINAL_SUMMARY:END -->

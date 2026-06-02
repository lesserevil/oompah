---
id: TASK-413
title: Fetch In Progress tasks explicitly for orphan reset
status: Done
assignee:
  - oompah
created_date: '2026-06-02 02:34'
updated_date: '2026-06-02 02:37'
labels:
  - bug
dependencies: []
priority: high
ordinal: 45000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The orchestrator currently calls _reset_orphaned_in_progress with the dispatch candidate list. Under the new Backlog status model, dispatch candidates come from active states such as Open, Needs CI Fix, and Needs Rebase; In Progress is intentionally not a dispatchable status. As a result, tasks left In Progress with no running or retrying agent are never presented to orphan reset. Add an explicit fetch of In Progress tasks for orphan reconciliation, preserve project_id on fetched issues, handle tracker errors without failing the tick, and keep the reset running in the executor.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the second orphan-reset root cause by fetching In Progress tasks explicitly via fetch_issues_by_states([In Progress]) instead of relying on dispatch candidates. Project IDs are preserved on fetched issues, and reset still runs in the executor. Verified with uv run pytest tests/test_orchestrator_handlers.py::TestHandleDispatchNeeded tests/test_orchestrator_handlers.py::TestFetchAllCandidatesTimeout tests/test_orchestrator_merged.py::TestResetOrphanedInProgress tests/test_orchestrator_merged.py::TestFetchInProgressIssues -q and make test (3688 passed, 17 warnings).
<!-- SECTION:FINAL_SUMMARY:END -->

---
id: TASK-466.10
title: Bound merged-label maintenance runtime
status: Done
assignee:
  - oompah
created_date: '2026-06-10 08:32'
updated_date: '2026-06-10 08:37'
labels:
  - bug
dependencies: []
parent_task_id: TASK-466
priority: high
ordinal: 231000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The merged_labels maintenance job can run for minutes and remain in_flight, leaving the service CPU-heavy and making issue snapshots slow. Add a configurable runtime budget and cooperative deadline checks across merged-label, stale-review, terminal-review, and deferred-Done review sweeps so one pass yields and resumes later instead of monopolizing maintenance.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added OOMPAH_MERGED_LABELS_MAX_RUNTIME_SECONDS with a 15s default, wired merged_labels through the maintenance runtime budget, and made merged-label/review reconciliation sweeps poll the deadline so long scans yield and resume later. Verified with: uv run pytest tests/test_config.py tests/test_orchestrator_handlers.py::TestMaybeRunMergedLabels tests/test_orchestrator_handlers.py::TestRunMaintenanceJobGate -q (84 passed).
<!-- SECTION:FINAL_SUMMARY:END -->

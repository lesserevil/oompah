---
id: TASK-499
title: Place In Review between Done and Merged in dashboard columns
status: Done
assignee:
  - oompah
created_date: '2026-06-10 01:25'
updated_date: '2026-06-10 01:26'
labels: []
dependencies: []
priority: medium
ordinal: 217000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard currently renders the In Review column before Done. Reorder the UI column configuration so In Review appears after Done and before Merged, without changing canonical lifecycle ranking semantics used elsewhere.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Moved the dashboard In Review column after Done and before Merged. Added a regression test in tests/test_dashboard_dispatch_optimistic.py to enforce the relative column order. Verification: tests/test_dashboard_dispatch_optimistic.py passed (20 tests).
<!-- SECTION:FINAL_SUMMARY:END -->

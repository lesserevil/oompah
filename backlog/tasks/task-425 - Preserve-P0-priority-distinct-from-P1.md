---
id: TASK-425
title: Preserve P0 priority distinct from P1
status: Done
assignee:
  - oompah
created_date: '2026-06-02 23:53'
updated_date: '2026-06-02 23:59'
labels: []
dependencies: []
priority: high
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix oompah's Backlog.md priority handling so numeric P0 tasks remain distinguishable from P1/high tasks. Today oompah parses numeric 0 as P0, but when writing priority back to Backlog it maps both 0 and 1 to the string high, losing the distinction. Update the tracker/write path and tests so P0 survives round trips and the dashboard/operator can tell P0 from P1.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Preserved P0 as distinct oompah priority metadata for Backlog.md tasks. Backlog CLI rejects critical and only accepts high/medium/low, so P0/critical now bypasses CLI priority flags and writes numeric priority: 0 directly to task frontmatter after create/update. Renamed the int-to-name map to make clear it is only for CLI-supported priority names. Added tests for numeric 0, P0, and critical parsing/writes.
<!-- SECTION:FINAL_SUMMARY:END -->

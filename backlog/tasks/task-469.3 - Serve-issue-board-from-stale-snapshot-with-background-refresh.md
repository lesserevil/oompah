---
id: TASK-469.3
title: Serve issue board from stale snapshot with background refresh
status: Done
assignee:
  - oompah
created_date: '2026-06-08 22:17'
updated_date: '2026-06-08 23:02'
labels: []
dependencies: []
parent_task_id: TASK-469
priority: high
ordinal: 172000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The board endpoint currently performs cold full-corpus reads that measured 18.9s and 30.0s for about 1365 issues. Change /api/v1/issues and WebSocket issue broadcasts to serve the last completed snapshot immediately, refresh asynchronously in a bounded single-flight job, and expose snapshot age/refresh status. Avoid invalidating the entire board cache on every small mutation when a stale snapshot is acceptable for UI responsiveness.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed /api/v1/issues and WebSocket issue broadcasts to serve the last snapshot immediately, refresh through a bounded single-flight background job, and expose snapshot status through response headers.
<!-- SECTION:FINAL_SUMMARY:END -->

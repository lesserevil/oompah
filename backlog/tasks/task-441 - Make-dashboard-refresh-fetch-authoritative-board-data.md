---
id: TASK-441
title: Make dashboard refresh fetch authoritative board data
status: Done
assignee:
  - oompah
created_date: '2026-06-03 20:52'
updated_date: '2026-06-03 20:56'
labels: []
dependencies: []
priority: high
ordinal: 77000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard Refresh button only asks the WebSocket to push an issues payload when WS is connected. If a connected browser misses or delays that push, stale cards can remain visible even though the REST issues API has the correct state. Make manual refresh fetch current board data directly and keep WebSocket refresh only as a secondary signal.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed dashboard manual refresh so it always fetches the current /api/v1/issues payload directly, even when WebSocket is connected, while still sending the WS refresh signal for other tabs. Added regression coverage that refreshBoard does not return before fetchIssues after sending a WS refresh.
<!-- SECTION:FINAL_SUMMARY:END -->

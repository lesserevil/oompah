---
id: TASK-469.5.3
title: Make issue snapshot freshness window configurable
status: Done
assignee: []
created_date: '2026-06-10 08:50'
updated_date: '2026-06-10 08:50'
labels: []
dependencies: []
parent_task_id: TASK-469.5
priority: high
ordinal: 233000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live monitoring after the accelerated YAML loader showed issue snapshots refreshing in about 21s, but /api/v1/issues still treated snapshots as stale after a hard-coded 5s. With an open dashboard/WebSocket client this causes repeated refresh churn and GIL contention. Make the freshness window configurable and raise the default to 60s so passive polling serves cached board data while webhooks/task-change hooks still trigger refreshes for real changes.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added OOMPAH_ISSUES_SNAPSHOT_STALE_MS with a 60000ms default, replacing the hard-coded 5000ms issue snapshot staleness threshold. Added tests for env parsing and stale metadata behavior. Verified with: uv run pytest tests/test_server_issue_snapshot.py tests/test_backlog_tracker.py -q (67 passed).
<!-- SECTION:FINAL_SUMMARY:END -->

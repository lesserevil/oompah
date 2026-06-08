---
id: TASK-469
title: Reduce Oompah service hanginess under load
status: Done
assignee:
  - oompah
created_date: '2026-06-08 22:17'
updated_date: '2026-06-08 23:02'
labels:
  - epic
dependencies: []
priority: high
ordinal: 169000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Investigation on 2026-06-08 found intermittent API/UI hangs while the service remained alive. Evidence: slow tick 416650ms with dispatch=231268ms and archive=121207ms; /api/v1/issues cold fetches at 18.9s and 30.0s for ~1365 issues; /api/v1/state sometimes timed out at 10-15s during dispatch/setup bursts. Design and implement changes so API responsiveness is isolated from scheduler, archive, tracker parsing, and agent setup work.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Reduced observed service hang sources by adding API/tick/tracker observability, nonblocking issue snapshots with background refresh, bounded maintenance batches, dispatch event coalescing, and bounded dispatch/duplicate-detection scans. Full make test passes. Physical multi-process split remains filed as TASK-469.5.1 if post-deploy metrics still require it.
<!-- SECTION:FINAL_SUMMARY:END -->

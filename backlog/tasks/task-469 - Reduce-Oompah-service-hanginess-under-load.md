---
id: TASK-469
title: Reduce Oompah service hanginess under load
status: Backlog
assignee: []
created_date: '2026-06-08 22:17'
updated_date: '2026-06-08 22:17'
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

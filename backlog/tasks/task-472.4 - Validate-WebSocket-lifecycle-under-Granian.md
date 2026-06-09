---
id: TASK-472.4
title: Validate WebSocket lifecycle under Granian
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 21:02'
labels:
  - 'needs:backend'
  - 'needs:test'
dependencies: []
parent_task_id: TASK-472
priority: medium
ordinal: 193000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Validate the full WebSocket path under granian beyond the basic prototype proof: broadcast fan-out to many clients, dead-client cleanup on disconnect, the console_input inbound path, and the throttled state/issues broadcasts. Confirm no cross-loop issues and acceptable behavior under concurrent clients.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Fan-out to multiple concurrent clients works; disconnected clients are pruned
- [ ] #2 console_input round-trips; throttled state/issues broadcasts deliver
<!-- AC:END -->

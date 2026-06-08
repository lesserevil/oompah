---
id: TASK-465.5
title: Make hard restart wait for old server to release the port
status: Open
assignee: []
created_date: '2026-06-08 19:51'
updated_date: '2026-06-08 19:52'
labels:
  - bug
dependencies: []
parent_task_id: TASK-465
priority: high
ordinal: 166000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During live recovery on 2026-06-08, make restart ran stop + start immediately. The old oompah process still held port 8090, so the new process failed with errno 98 address already in use, then overwrote .oompah.pid with the failed process PID.

Fix the Makefile/service control path so restart waits for the old PID to exit and for the configured port to be released before starting a replacement. If the old process does not exit within a bounded timeout, report a clear failure or escalate intentionally instead of writing a dead PID file.

Acceptance criteria:
- make restart does not start a second process while the old one still owns the configured port.
- Failed starts do not leave .oompah.pid pointing at a dead process.
- Tests or scripted coverage exercise the restart wait/race behavior without relying on sleeps alone.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:52
---
Filed from live recovery: make restart started a replacement before the old process released port 8090 and left .oompah.pid pointing at the failed process.
---
<!-- COMMENTS:END -->

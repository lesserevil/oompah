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

author: oompah
created: 2026-06-08 23:08
---
Verification: 26 tests pass (20 new + 6 existing test_makefile_setup). Breakdown: 13 static-analysis (Makefile structure), 4 functional port_in_use shell tests, 3 end-to-end wait_for_stop behavior tests. Broader suite (260 tests including orchestrator/dispatch) also passes. Committed a7bbf34 on epic-TASK-465.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed make restart race: stop now calls wait_for_stop which polls kill -0 then port_in_use before returning. Fixed @ bug in wait_for_stop define (was causing shell error when expanded inline). start now refuses to launch when port is already in use and removes .oompah.pid on failed startup. Added 20 tests: static Makefile structure analysis + functional port_in_use shell + end-to-end wait_for_stop with lightweight TCP server.
<!-- SECTION:FINAL_SUMMARY:END -->

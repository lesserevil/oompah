---
id: TASK-461.9
title: Run retry issue fetch off the event loop
status: Done
assignee:
  - oompah
created_date: '2026-06-10 01:03'
updated_date: '2026-06-10 01:41'
labels: []
dependencies: []
parent_task_id: TASK-461
priority: high
ordinal: 215000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: retry timers call _fetch_retry_issue from async _on_retry_timer. _fetch_retry_issue can call _fetch_all_candidates, which uses asyncio.run() for bounded multi-project refresh, so retry handling logs RuntimeError: asyncio.run() cannot be called from a running event loop. Move the blocking retry issue fetch off the event loop and cover it with a regression test.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Moved retry issue lookup off the event loop by running _fetch_retry_issue in a worker thread from _on_retry_timer. Added a regression test that simulates _fetch_retry_issue calling asyncio.run() and verifies it executes outside the event-loop thread. Focused retry tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

---
id: TASK-100
title: Replace polling with event-driven calls
status: Done
assignee: []
created_date: 2026-03-08 20:10
updated_date: 2026-03-08 20:56
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-kkd
  state: closed
  parent_id: oompah-ky3
  dependencies: []
  branch_name: oompah-kkd
  target_branch: null
  url: null
  created_at: '2026-03-08T20:10:20Z'
  updated_at: '2026-03-08T20:56:45Z'
  closed_at: '2026-03-08T20:56:45Z'
parent: TASK-71
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace all instances of polling with event-driven function calls
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 91f2c9f9-bb18-4558-8d9f-4ea0040f8968
author: oompah
created: 2026-03-08T20:30:02Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 92e237f1-fba7-41ad-bbf7-da2facc5b096
author: oompah
created: 2026-03-08T20:30:02Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5554b2bb-040f-4f5f-a096-77be1bb1c272
author: oompah
created: 2026-03-08T20:31:16Z

I understand the issue: Replace all polling patterns with event-driven function calls. After analyzing the codebase, I've found the main polling pattern is in LogFileWatcher (error_watcher.py) which polls a log file every 2 seconds using asyncio.sleep(). The fix is to replace this with watchfiles.awatch() which is already a dependency (used in __main__.py for workflow reloading) - this gives us inotify/FSEvents/kqueue-backed file watching instead of polling. Other 'while True' loops in the codebase (agent stderr drain, websocket message loop, etc.) are I/O event-driven reads, not polling, so they don't need changes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8f1a5744-8aca-45ec-950f-6b8f8e72f7ea
author: oompah
created: 2026-03-08T20:50:04Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f8bd9281-db23-43be-852b-d0e11cf4224c
author: oompah
created: 2026-03-08T20:50:05Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4c302fe2-5e4f-4778-8c85-963e37362de2
author: oompah
created: 2026-03-08T20:50:42Z

I understand the issue from the previous agent's analysis. The main polling pattern to fix is in LogFileWatcher.start() in error_watcher.py - it uses asyncio.sleep(2.0) in a while loop to check for new log file content every 2 seconds. The fix is to replace this with watchfiles.awatch() (already in dependencies, already used in __main__.py) for event-driven file change notifications. The _poll_file() method and _seek_to_end() infrastructure can remain, but the polling loop gets replaced with an awatch event loop. My approach: (1) Replace the sleep-based loop in LogFileWatcher.start() with awatch(), (2) Keep backward-compat by removing poll_interval parameter or keeping it for fallback, (3) Update tests to cover the new event-driven behavior.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 935c1641-1e09-48c8-a292-2b5d67216f05
author: oompah
created: 2026-03-08T20:55:30Z

Implementation complete. Changed LogFileWatcher in oompah/error_watcher.py to use watchfiles.awatch() for event-driven file watching instead of asyncio.sleep() polling. Key changes: (1) Removed poll_interval parameter - no longer needed; (2) Added _stop_event: asyncio.Event for clean shutdown, passed to awatch() stop_event param; (3) Added _watch_path() method - returns log file path if exists, parent directory otherwise; (4) Added _make_watch_filter() method - filter function to only react to the specific log file when watching parent dir; (5) Replaced start() sleep loop with _watch_loop() using awatch() which uses inotify/kqueue/FSEvents under the hood. Updated tests: added 6 new tests for event-driven behavior (_watch_path, _make_watch_filter, stop_event, and integration tests), removed poll_interval arg from existing tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b03478c8-c4a1-4c63-8322-1781d0b6a049
author: oompah
created: 2026-03-08T20:56:34Z

Verification: All 52 tests in test_error_watcher.py pass. The 12 pre-existing failures in other test files (test_collapsed_epics.py, test_draft_epic_swimlane.py, test_focus.py) are unrelated to our changes and existed before. PR created: https://github.com/lesserevil/oompah/pull/37
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6686e68e-32aa-4e11-a1ed-0577103b7fb6
author: oompah
created: 2026-03-08T20:56:40Z

Completion: Replaced polling with event-driven file watching in LogFileWatcher (oompah/error_watcher.py). The asyncio.sleep()-based poll loop is gone; watchfiles.awatch() (inotify/kqueue/FSEvents) now drives file change detection. The watcher handles: files that don't exist yet (watches parent dir), log rotation, graceful shutdown via asyncio.Event. 52 tests pass. PR: https://github.com/lesserevil/oompah/pull/37
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8fb317b2-daba-4ca6-96bf-0c41140342e6
author: oompah
created: 2026-03-08T20:56:45Z

Agent completed successfully in 401s (2693638 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

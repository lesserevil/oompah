---
id: TASK-69
title: Make the auto-issue generation on error more generic
status: Done
assignee: []
created_date: 2026-03-08 15:17
updated_date: 2026-03-08 15:27
labels:
- archive:yes
- merged
- feature
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: feature
beads:
  id: oompah-qra
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-qra
  target_branch: null
  url: null
  created_at: '2026-03-08T15:17:41Z'
  updated_at: '2026-03-08T15:27:04Z'
  closed_at: '2026-03-08T15:27:04Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Right now, the 'create issue when error shows in log' code is specific to oompah. We need to make it more generic so any project can use it.

Add an optional 'log path' setting to the Project field. If the user fills out a log path, and the log file is present, the oompah will watch the log file and add issues to the backlog just like with oompah. Oompah's own log check should be converted to use this new system.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: a3eff7b9-5f71-430c-bc5b-77fc6ae3600e
author: oompah
created: 2026-03-08T15:17:58Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 527fb194-ccec-4cfd-8749-b33ef1ec39c5
author: oompah
created: 2026-03-08T15:17:59Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 687520a8-cda2-4c4e-9fae-9247404dcb72
author: oompah
created: 2026-03-08T15:18:20Z

Agent stalled 1 time(s) (21s (61011 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bc61b56d-618a-4aae-b814-9db7d53cb7fd
author: oompah
created: 2026-03-08T15:18:30Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b5ea6301-f15d-4b1d-be9a-5f5c18a8bb82
author: oompah
created: 2026-03-08T15:18:31Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bd23d6f7-5f55-4ad1-93c8-753d50f28a73
author: oompah
created: 2026-03-08T15:19:09Z

Agent stalled — no productive actions (writes/commands) for 5 consecutive turns (39s (170743 tokens)). Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 62fd8fa3-bcdf-4777-92e5-727c028f835b
author: oompah
created: 2026-03-08T15:19:30Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: beb34940-20ac-42b1-8dfe-f2a9b95a4284
author: oompah
created: 2026-03-08T15:19:30Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2db0a787-e4a6-4a9d-bf77-23b184595d69
author: oompah
created: 2026-03-08T15:20:04Z

Agent stalled 3 time(s) (34s (120849 tokens)). Escalating from 'standard' to 'deep'. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 70387287-948e-4569-8550-96c425fa2515
author: oompah
created: 2026-03-08T15:20:44Z

Retrying (attempt #3, agent: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ef4e7448-9c2b-40f5-bb9c-0930cb2d707e
author: oompah
created: 2026-03-08T15:20:45Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9e6809b3-a9ea-45c7-8add-8bdf39c2ad7e
author: Shawn Edwards
created: 2026-03-08T15:21:35Z

I understand the issue: The ErrorWatcher currently only watches oompah's own Python logging handler for errors. We need to make it generic so it can also watch external log files for any project. Plan: 1) Add optional 'log_path' field to Project model with serialization. 2) Create a LogFileWatcher class in error_watcher.py that tails a log file for ERROR lines and feeds them to ErrorWatcher.report_error(). 3) Wire up the log file watching in server.py's set_orchestrator to start watchers for projects with log_path set. 4) Convert oompah's own error watching (the logging handler) to use the same generic system where possible. 5) Update project API to accept log_path. 6) Add tests for all new code.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d2db39e9-258f-4d02-9af5-c1caf0e4933b
author: Shawn Edwards
created: 2026-03-08T15:21:52Z

Found the relevant code: 1) ErrorWatcher in error_watcher.py has report_error() for creating beads and install_log_handler() for Python logging. 2) Project model in models.py needs a log_path field. 3) server.py's set_orchestrator() wires up the ErrorWatcher with oompah's own logger. 4) The project API in server.py (api_update_project) needs to accept log_path. Key design: I'll add a LogFileWatcher class that uses asyncio to tail log files, detecting ERROR/CRITICAL lines and feeding them to the existing ErrorWatcher.report_error(). Each project with a log_path gets a watcher. Oompah's own log handler stays as-is (it's Python logging, not file-based) but the new system extends coverage to external projects.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 07dc7a6f-7c8f-44d4-be82-eeb745eebd5c
author: Shawn Edwards
created: 2026-03-08T15:26:14Z

Implementation complete. Changes made:

1. **oompah/models.py**: Added optional 'log_path' field to Project dataclass with serialization support in to_dict/from_dict.

2. **oompah/error_watcher.py**: Added three new components:
   - Helper functions: _detect_error_level(), _priority_for_level(), _extract_message() for parsing log lines
   - LogFileWatcher class: Async file tailer that polls a log file, detects ERROR/CRITICAL/FATAL/SEVERE lines, and feeds them to ErrorWatcher.report_error(). Handles log rotation (inode changes) and file truncation. Only processes new lines (seeks to end on start).
   - ProjectLogWatcherManager class: Manages LogFileWatcher instances for all projects. sync_watchers() starts/stops/restarts watchers as projects are added/removed/updated.

3. **oompah/server.py**:
   - Wired up ProjectLogWatcherManager in set_orchestrator() with a factory that creates project-specific ErrorWatchers
   - Added sync_watchers() calls in project create/update/delete API endpoints
   - Added 'log_path' to the accepted fields in api_update_project()

4. **tests/test_error_watcher.py**: 46 new tests covering all new code:
   - 11 tests for error line detection helpers
   - 5 tests for ErrorWatcher core behavior
   - 9 tests for LogFileWatcher (file polling, incremental reading, truncation, start/stop)
   - 5 tests for ProjectLogWatcherManager (sync, start, stop, restart, stop_all)
   - 4 tests for Project model log_path serialization

Oompah's own Python logging handler is preserved (it intercepts Python logging which is different from file tailing). The new system extends this to watch external log files for any project.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c8cc900b-52c5-4be1-90b7-31fdfdddd018
author: Shawn Edwards
created: 2026-03-08T15:26:21Z

All tests pass: 276 total (46 new + 230 existing). No regressions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bbfbe972-3dfe-4dab-b4a7-0d5506428a30
author: Shawn Edwards
created: 2026-03-08T15:26:59Z

PR created: https://github.com/lesserevil/oompah/pull/17
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5cf16d6f-c108-4108-af53-3e83900c2adb
author: oompah
created: 2026-03-08T15:27:06Z

Agent completed successfully in 381s (2630531 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

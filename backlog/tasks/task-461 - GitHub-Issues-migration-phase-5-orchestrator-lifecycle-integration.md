---
id: TASK-461
title: 'GitHub Issues migration phase 5: orchestrator lifecycle integration'
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458
  - TASK-460
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 136000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Teach the orchestrator to dispatch, claim, run, retry, complete, reopen, and auto-file work against GitHub-backed tasks while keeping normalized Issue semantics intact. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A GitHub-backed task can be dispatched and completed end to end.
- [ ] #2 Worker-exit and retry logic no longer rely on Backlog files for GitHub tasks.
- [ ] #3 Watcher-created work goes to the canonical tracker.
<!-- AC:END -->

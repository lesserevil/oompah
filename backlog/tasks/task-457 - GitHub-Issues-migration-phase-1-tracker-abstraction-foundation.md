---
id: TASK-457
title: 'GitHub Issues migration phase 1: tracker abstraction foundation'
status: Open
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-11 17:48'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies: []
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 108000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create the backend-neutral tracker foundation needed before GitHub Issues can become a task backend. This phase keeps Backlog.md behavior intact while introducing a protocol, adapter registry, structured tracker identity, and contract tests. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 BacklogMdTracker behavior remains unchanged for existing projects.
- [ ] #2 Server and orchestrator code can depend on a tracker protocol instead of BacklogMdTracker directly.
- [ ] #3 Shared contract tests define required tracker behavior for both Backlog.md and GitHub Issues.
<!-- AC:END -->

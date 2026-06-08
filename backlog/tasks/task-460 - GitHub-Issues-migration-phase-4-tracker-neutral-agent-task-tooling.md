---
id: TASK-460
title: 'GitHub Issues migration phase 4: tracker-neutral agent task tooling'
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 130000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stop teaching agents to run Backlog.md commands for GitHub-backed work. Provide oompah-owned task commands or tools that route to the active tracker and keep follow-up task creation canonical. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Agents can complete GitHub-backed tasks without invoking Backlog.md.
- [ ] #2 Follow-up and child task creation uses the canonical tracker.
- [ ] #3 Prompts remain correct for legacy Backlog tasks during transition.
<!-- AC:END -->

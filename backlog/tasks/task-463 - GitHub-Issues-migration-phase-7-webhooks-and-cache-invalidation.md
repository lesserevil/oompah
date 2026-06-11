---
id: TASK-463
title: 'GitHub Issues migration phase 7: webhooks and cache invalidation'
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-11 17:49'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459
  - TASK-461
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 151000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Expand webhook handling so GitHub issue edits, comments, labels, project field changes, PR events, and pushes update the dashboard and orchestrator promptly. Retire Backlog post-commit hooks for GitHub-backed projects. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub issue edits refresh oompah without waiting for full polling.
- [ ] #2 Backlog post-commit hooks are not installed for GitHub-backed projects.
- [ ] #3 Local gh webhook forward configuration includes the required events.
<!-- AC:END -->

---
id: TASK-458
title: 'GitHub Issues migration phase 2: GitHub tracker adapter'
status: Done
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-11 17:48'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 114000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement GitHubIssueTracker as a first-class tracker backend for the central task hub repository. This phase creates, reads, updates, comments on, labels, filters, and relates GitHub issues while hiding REST/GraphQL and issue-field details behind the tracker protocol. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A test GitHub-backed project can create and update tasks without Backlog.md.
- [ ] #2 The adapter normalizes GitHub API failures into tracker errors.
- [ ] #3 Issue fields are used when available, with body metadata fallback.
<!-- AC:END -->

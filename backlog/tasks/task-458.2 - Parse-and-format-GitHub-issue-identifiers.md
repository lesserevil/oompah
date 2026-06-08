---
id: TASK-458.2
title: Parse and format GitHub issue identifiers
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.1
  - TASK-457.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 116000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement parser/formatter support for fully qualified identifiers such as owner/repo#1234, central task hub short display identifiers, URL-safe route forms, and branch-safe slugs. Bare numeric identifiers must not be accepted as canonical.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Identifier parsing rejects ambiguous bare numbers.
- [ ] #2 Display identifiers and branch slugs are stable and filesystem-safe.
<!-- AC:END -->

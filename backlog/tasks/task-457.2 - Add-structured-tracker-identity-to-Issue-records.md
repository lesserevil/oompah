---
id: TASK-457.2
title: Add structured tracker identity to Issue records
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/models.py
  - oompah/server.py
  - oompah/prompt.py
parent_task_id: TASK-457
priority: high
ordinal: 110000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Extend normalized issue data so oompah can represent fully qualified GitHub issue identities while preserving existing Backlog identifiers. Include tracker kind, owner, repo, numeric issue number, display identifier, and stable provider URL where appropriate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Backlog tasks continue to serialize with their existing identifier shape.
- [ ] #2 GitHub-backed issues can be represented without bare-number ambiguity.
<!-- AC:END -->

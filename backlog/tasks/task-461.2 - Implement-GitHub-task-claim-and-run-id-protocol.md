---
id: TASK-461.2
title: Implement GitHub task claim and run-id protocol
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.1
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_dispatch_close_race.py
parent_task_id: TASK-461
priority: high
ordinal: 138000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
For GitHub-backed tasks, claim by writing In Progress plus Agent Run ID, then re-read and proceed only if the run ID still matches. Keep current single-process behavior for Backlog while preventing duplicate claims if multiple oompah instances exist.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Claim races are detected and skipped without starting duplicate agents.
- [ ] #2 Running state includes tracker kind and fully qualified identifier.
<!-- AC:END -->

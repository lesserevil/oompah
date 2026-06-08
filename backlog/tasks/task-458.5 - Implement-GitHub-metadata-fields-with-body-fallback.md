---
id: TASK-458.5
title: Implement GitHub metadata fields with body fallback
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 119000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Read and write oompah-owned metadata using GitHub issue fields when configured. Provide a hidden body-metadata fallback for deployments where issue fields are unavailable or incomplete, without leaking fallback details to server/orchestrator code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Metadata get/set works for project_id, target_branch, work_branch, review fields, attachments, and release-pick data.
- [ ] #2 Field-backed and body-backed metadata pass the same contract tests.
<!-- AC:END -->

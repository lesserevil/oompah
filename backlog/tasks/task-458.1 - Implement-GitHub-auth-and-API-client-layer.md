---
id: TASK-458.1
title: Implement GitHub auth and API client layer
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
  - oompah/github_tracker.py
  - oompah/config.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 115000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add GitHub App installation-token support as the preferred production auth path, with PAT and gh-auth fallback for development. Centralize request retries, timeout handling, pagination, rate-limit logging, ETag/cache hooks, and response redaction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub App, PAT, and missing-auth paths are covered by tests.
- [ ] #2 Rate-limit and auth errors become actionable TrackerError messages.
<!-- AC:END -->

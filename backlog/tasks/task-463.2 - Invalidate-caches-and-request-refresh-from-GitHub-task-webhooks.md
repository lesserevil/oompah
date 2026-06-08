---
id: TASK-463.2
title: Invalidate caches and request refresh from GitHub task webhooks
status: Backlog
assignee: []
created_date: '2026-06-08 17:58'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-463.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - oompah/orchestrator.py
  - tests/test_webhooks.py
parent_task_id: TASK-463
priority: high
ordinal: 153000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Wire GitHub task webhook events to invalidate issue list, detail, comment, branch-to-issue, and review caches. Trigger orchestrator refresh only when the event can affect dispatch, status, comments, or review reconciliation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dashboard updates promptly after GitHub-side status/comment edits.
- [ ] #2 Webhook storms do not trigger unnecessary full source syncs.
<!-- AC:END -->

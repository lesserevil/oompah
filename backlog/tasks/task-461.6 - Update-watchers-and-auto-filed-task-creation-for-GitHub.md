---
id: TASK-461.6
title: Update watchers and auto-filed task creation for GitHub
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.3
  - TASK-461.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/error_watcher.py
  - oompah/orchestrator.py
  - tests/test_error_watcher.py
parent_task_id: TASK-461
priority: high
ordinal: 142000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update ErrorWatcher, AgentWatcher, duplicate detection, CI-fix sibling filing, release-pick child task creation hooks, and other create_issue callers so new auto-filed work goes to GitHub Issues by default.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Auto-filed tasks include tracker identity, source project, and dedup metadata.
- [ ] #2 Existing source-task comments still go to the source task backend.
<!-- AC:END -->

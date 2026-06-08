---
id: TASK-460.3
title: Route follow-up and child task creation to the canonical tracker
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - WORKFLOW.md
  - oompah/orchestrator.py
  - oompah/error_watcher.py
parent_task_id: TASK-460
priority: high
ordinal: 133000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure agent-created follow-ups, child tasks, missing-capability tasks, watcher tasks, and handoff tasks go through the oompah task wrapper or tracker protocol. For legacy Backlog tasks, new follow-ups should still be GitHub Issues unless explicitly configured otherwise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No GitHub-backed workflow instructs agents to create Backlog task files.
- [ ] #2 Follow-up task parent/source metadata is preserved across tracker backends.
<!-- AC:END -->

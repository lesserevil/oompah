---
id: TASK-461.4
title: Refactor worker-exit terminal state handling for GitHub tasks
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_completion_verifier.py
parent_task_id: TASK-461
priority: high
ordinal: 140000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Gate worker-workspace Backlog task reads to legacy Backlog tasks only. For GitHub-backed tasks, re-read terminal state from GitHub after worker exit and use normalized status for completion, retry, and cleanup decisions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed completion does not inspect Backlog files in the worker worktree.
- [ ] #2 Legacy Backlog terminal-state recognition remains intact.
<!-- AC:END -->

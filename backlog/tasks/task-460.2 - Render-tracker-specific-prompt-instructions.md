---
id: TASK-460.2
title: Render tracker-specific prompt instructions
status: Backlog
assignee: []
created_date: '2026-06-08 17:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.1
  - TASK-457.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/prompt.py
  - WORKFLOW.md
  - tests/test_prompt.py
parent_task_id: TASK-460
priority: high
ordinal: 132000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update prompt rendering so the task reference section comes from the active tracker. GitHub-backed tasks should show oompah task commands and GitHub issue URL; legacy Backlog tasks may keep Backlog commands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed prompts do not include backlog task create/edit commands.
- [ ] #2 Legacy Backlog prompts remain functional for legacy dispatch.
<!-- AC:END -->

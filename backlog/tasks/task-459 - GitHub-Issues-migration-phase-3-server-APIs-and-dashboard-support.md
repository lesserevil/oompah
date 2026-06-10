---
id: TASK-459
title: 'GitHub Issues migration phase 3: server APIs and dashboard support'
status: Merged
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 03:12'
labels:
  - epic
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457
  - TASK-458
references:
  - plans/github-issues-tracker-migration.md
priority: high
ordinal: 122000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make the oompah API and dashboard backend-neutral so operators can create, view, edit, comment on, and label GitHub-backed tasks while legacy Backlog tasks remain visible during transition. See plans/github-issues-tracker-migration.md. Existing Backlog.md tasks must not be migrated; this work only changes new task creation and future task state management.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Operators can create and manage GitHub-backed tasks from the oompah UI.
- [ ] #2 Issue API responses include tracker identity and GitHub URLs.
- [ ] #3 Legacy Backlog tasks remain distinguishable during transition.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-09 23:50

Review reconciliation could not verify this task branch after its review artifact disappeared.

Branch: `TASK-459`
Target branch: `main`
Reason: git rev-list --count failed for main..origin/TASK-459: fatal: ambiguous argument 'main..origin/TASK-459': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'

Required: confirm whether the branch landed, restore the PR/MR, or archive the task.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-10 00:06

Review reconciliation could not verify this task branch after its review artifact disappeared.

Branch: `TASK-459`
Target branch: `main`
Reason: git rev-list --count failed for main..origin/TASK-459: fatal: ambiguous argument 'main..origin/TASK-459': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'

Required: confirm whether the branch landed, restore the PR/MR, or archive the task.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

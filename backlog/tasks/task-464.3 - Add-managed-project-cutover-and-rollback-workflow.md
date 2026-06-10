---
id: TASK-464.3
title: Add managed-project cutover and rollback workflow
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 10:11'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.2
  - TASK-459.4
  - TASK-461.7
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - oompah/templates/projects.html
  - docs
parent_task_id: TASK-464
priority: high
ordinal: 160000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement operator workflow for pausing a project, waiting for or cancelling agents, recording cutover timestamp, enabling GitHub tracker settings, verifying test task creation/dispatch/PR flow, unpausing, and rolling back if needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Cutover flow is documented and exposed through project management UI or API.
- [ ] #2 Rollback restores legacy Backlog dispatch settings without deleting GitHub issues.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 10:08
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 10:09
---
UNDERSTANDING: This is NOT a duplicate. Searched for 'cutover rollback workflow', 'pause project', 'cutover timestamp' — no other task covers this specific behavior. TASK-464.3 is the unique task responsible for implementing the operator cutover/rollback workflow atop the foundational work done in TASK-464.1 (tracker-aware sync) and TASK-464.2 (dual-read/dispatch flags). Dependencies TASK-464.2 is Done; others (TASK-459.4, TASK-461.7) are presumably done on their epic branches. Will now implement: (1) API/UI endpoint to initiate project cutover with timestamp, (2) pause/unpause mechanics, (3) rollback flow restoring legacy_backlog_dispatch=True without deleting GitHub issues, (4) operator documentation.
---

author: oompah
created: 2026-06-10 10:11
---
DISCOVERY: Confirmed this is not a duplicate. Key code locations: oompah/models.py (Project dataclass with tracker_kind/legacy_backlog fields), oompah/projects.py (UPDATABLE_FIELDS), oompah/server.py (pause/resume endpoints at lines 4867-4927), oompah/templates/projects.html. Missing: cutover_at, tracker_owner, tracker_repo fields; /cutover and /rollback API endpoints; tracker UI fields; operator docs. TASK-464.2 is Done and provides the dual-read/dispatch flags foundation. Implementation plan: (1) add cutover_at/tracker_owner/tracker_repo to Project model, (2) add to UPDATABLE_FIELDS, (3) add /cutover and /rollback server endpoints, (4) update PATCH handler to accept tracker_owner/tracker_repo/tracker_kind, (5) add cutover status UI and buttons to projects.html, (6) add operator docs, (7) tests.
---
<!-- COMMENTS:END -->

---
id: TASK-464.3
title: Add managed-project cutover and rollback workflow
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 10:21'
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

author: oompah
created: 2026-06-10 10:20
---
IMPLEMENTATION: Added cutover and rollback workflow to oompah. Changes: (1) Project model gains cutover_at/tracker_owner/tracker_repo fields with compact serialisation (only emitted when set). (2) UPDATABLE_FIELDS updated in ProjectStore. (3) POST /api/v1/projects/{id}/cutover pauses the project, sets tracker_kind=github_issues, records cutover_at UTC timestamp, accepts tracker_owner/tracker_repo and legacy_backlog_enabled/dispatch flags. (4) POST /api/v1/projects/{id}/rollback clears tracker_kind+cutover_at, enables legacy_backlog_enabled+dispatch, unpauses by default — does NOT delete GitHub Issues. (5) PATCH endpoint now accepts all tracker/cutover fields. (6) Projects UI gains tracker badge (GitHub Issues vs Backlog.md), cutover timestamp display, 'Cut over to GitHub Issues' button+modal, 'Rollback to Backlog' button. (7) docs/cutover-workflow.md added: full operator runbook with step-by-step instructions, legacy task paths, rollback, and troubleshooting. (8) 65 new tests in test_project_cutover.py; test_projects_crud.py updated for new UPDATABLE_FIELDS.
---

author: oompah
created: 2026-06-10 10:21
---
VERIFICATION: 65 new tests in test_project_cutover.py all pass. 695-test sweep (models, projects, projects_crud, project_pause, legacy_backlog_dispatch, project_cutover, backlog_tracker, tracker_protocol, shared_tracker_contract, config) passes. 357-test sweep including whitelist UI, server issue detail, and template fetch errors passes. No regressions detected.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented managed-project cutover and rollback workflow. Added: (1) cutover_at/tracker_owner/tracker_repo fields to Project model; (2) POST /api/v1/projects/{id}/cutover endpoint (pauses project, sets tracker_kind=github_issues, records timestamp, accepts hub coords and legacy flags); (3) POST /api/v1/projects/{id}/rollback endpoint (restores legacy_backlog_enabled/dispatch, clears tracker_kind+cutover_at, unpauses — does NOT delete GitHub Issues); (4) PATCH endpoint accepts all new tracker/cutover fields; (5) Projects UI: tracker badge, cutover timestamp, legacy mode indicator, 'Cut over' button+modal, 'Rollback' button; (6) docs/cutover-workflow.md operator runbook; (7) 65 new tests, all pass, no regressions.
<!-- SECTION:FINAL_SUMMARY:END -->

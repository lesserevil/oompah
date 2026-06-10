---
id: TASK-464.1
title: Make ProjectStore source sync tracker-aware
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 03:15'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
  - TASK-463.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/projects.py
  - tests/test_projects.py
parent_task_id: TASK-464
priority: high
ordinal: 158000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
For GitHub-backed projects, keep git self-heal and default-branch fast-forwarding, but skip Backlog compatibility checks, Backlog conflict repair/quarantine, and Backlog hook setup. Preserve current behavior for legacy Backlog projects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 sync_project_sources reports GitHub tracker status for GitHub-backed projects.
- [ ] #2 Backlog conflict repair remains active only for legacy Backlog projects.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 02:43
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 02:43
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 03:01
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 03:06
---
UNDERSTANDING: This task is NOT a duplicate — it's a unique subtask of TASK-464 with no overlapping existing implementation. Plan: modify sync_project_sources() in oompah/projects.py to check project.tracker_kind. For GitHub-backed projects (tracker_kind='github_issues'): keep git self-heal (ensure_repo_sound) but skip ensure_backlog_compatible() and repair_repo_backlog_conflicts()/quarantine, add tracker='github_issues' to returned status dict. Legacy Backlog projects unaffected. Add tests for both paths.
---

author: oompah
created: 2026-06-10 03:14
---
DISCOVERY: sync_project_sources() in oompah/projects.py runs three distinct phases: (1) git self-heal via ensure_repo_sound (tracker-agnostic), (2) Backlog.md compatibility check via ensure_backlog_compatible, (3) Backlog conflict repair/quarantine via repair_repo_backlog_conflicts. Only phases 2 and 3 are Backlog-specific. TASK-463.4 already added tracker_kind='github_issues' to the Project model. The change is to skip phases 2 and 3 for GitHub-backed projects while always running phase 1.
---

author: oompah
created: 2026-06-10 03:14
---
IMPLEMENTATION: Added _is_github_backed(project) helper to oompah/projects.py that normalizes tracker_kind and returns True for 'github_issues'/'github-issues'. Modified sync_project_sources() to: (1) always run git self-heal (ensure_repo_sound), (2) for GitHub-backed: add tracker='github_issues' to status, set backlog='skipped: github_issues', set conflicts='skipped: github_issues', return early before Backlog-specific phases. Legacy Backlog projects are unaffected. Updated docstring. Added 12 new tests: TestIsGithubBacked (5 tests) and TestSyncProjectSourcesGitHubBacked (7 tests).
---

author: oompah
created: 2026-06-10 03:14
---
VERIFICATION: 206 tests pass (139 in test_projects + test_backlog_conflict, 67 in test_models + test_backlog_webhooks). All 12 new tests pass. Branch pushed to origin/epic-TASK-464.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added _is_github_backed() helper and made sync_project_sources() tracker-aware: GitHub-backed projects (tracker_kind='github_issues') skip ensure_backlog_compatible and repair_repo_backlog_conflicts/quarantine while git self-heal continues to run. Status dict includes tracker='github_issues' for GitHub-backed projects. 12 new tests, 206 total pass. Legacy Backlog projects unaffected.
<!-- SECTION:FINAL_SUMMARY:END -->

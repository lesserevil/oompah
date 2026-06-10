---
id: TASK-464.7
title: 'Decommission default Backlog prompts, hooks, and reports'
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 16:38'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.6
  - TASK-460.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - .env.example
  - README.md
  - WORKFLOW.md
  - >-
    backlog/archive/tasks/task-402 -
    Epic-make-Backlog.md-the-only-oompah-tracker.md
  - oompah/projects.py
  - oompah/server.py
  - tests/test_projects.py
  - tests/test_server_backlog_report.py
parent_task_id: TASK-464
priority: medium
ordinal: 164000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After managed projects are cut over, remove Backlog.md from default prompts and default project lifecycle, keep BacklogMdTracker behind explicit legacy flags, add reports for new Backlog files since cutover, and resolve or supersede the old Backlog-only workstream TASK-402.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Default oompah workflow no longer presents Backlog.md as the active tracker.
- [ ] #2 Operators can report any post-cutover Backlog task files.
- [ ] #3 TASK-402 is explicitly closed, archived, or documented as superseded.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 16:25
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 16:26
---
Understanding: TASK-464.7 is NOT a duplicate. TASK-402 (Done) worked in the opposite direction — made Backlog mandatory by removing Beads. TASK-460.4 (Done) added runtime rejection guards for new Backlog files in GitHub-backed work. TASK-457.5 (Open) audits BacklogMdTracker type assumptions in code. TASK-464.7 is unique: it decommissions Backlog from default prompts/WORKFLOW, keeps BacklogMdTracker behind explicit legacy flags, adds operator reporting for post-cutover Backlog files, and documents TASK-402 as superseded. Plan: (1) examine WORKFLOW.md and prompt templates for Backlog references; (2) look at oompah/orchestrator.py and oompah/server.py for legacy flag gating; (3) add/surface operator reports for Backlog files post-cutover; (4) document TASK-402 as superseded.
---

author: oompah
created: 2026-06-10 16:31
---
Discovery: Confirmed not a duplicate. Key findings: (1) AC#1 requires: change WORKFLOW.md tracker kind from 'backlog' to 'github_issues'; change ServiceConfig.tracker_kind default from 'backlog_md' to 'github_issues'; change _parse_tracker_kind default; guard ensure_backlog_compatible in projects.py create() to skip for GitHub-backed projects. (2) AC#2 requires: add GET /api/v1/reports/backlog-files-post-cutover endpoint in server.py that finds Backlog task files newer than tracker_cutover_at for each GitHub-backed project. (3) AC#3: TASK-402 is already in Done state; need to add a comment noting it is superseded by the GitHub Issues migration. All these changes target WORKFLOW.md, oompah/config.py, oompah/projects.py, and oompah/server.py as expected from the task's 'Modified files' list.
---

author: oompah
created: 2026-06-10 16:37
---
Implementation: Changed WORKFLOW.md's tracker kind to github_issues and removed Backlog commands from the GitHub-backed prompt path. Added .env.example/README guidance for OOMPAH_GITHUB_TRACKER_OWNER and OOMPAH_GITHUB_TRACKER_REPO, kept ServiceConfig's implicit no-config fallback as backlog_md to avoid breaking existing direct ServiceConfig() callers, skipped Backlog compatibility checks when creating GitHub-backed projects, added GET /api/v1/reports/backlog-files-post-cutover, and documented archived TASK-402 as superseded.
---

author: oompah
created: 2026-06-10 16:38
---
Verification: uv run pytest tests/test_config.py tests/test_projects.py tests/test_server_backlog_report.py -q passed (110 passed). git diff --check passed. py_compile passed for oompah/server.py, oompah/projects.py, oompah/config.py, tests/test_server_backlog_report.py, and tests/test_projects.py. WORKFLOW.md config smoke parsed tracker_kind=github_issues with OOMPAH_GITHUB_TRACKER_OWNER/REPO set.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Decommissioned Backlog from the default GitHub-backed workflow path. WORKFLOW.md now defaults to github_issues, GitHub-backed prompts use oompah task commands and repo docs instead of Backlog commands, .env.example/README document the required default GitHub task-hub env, GitHub-backed project creation skips Backlog compatibility checks, operators can call GET /api/v1/reports/backlog-files-post-cutover to find Backlog task files added after tracker_cutover_at, and archived TASK-402 is explicitly documented as superseded. Verified with focused config/projects/server report tests plus diff and py_compile checks.
<!-- SECTION:FINAL_SUMMARY:END -->

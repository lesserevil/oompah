---
id: TASK-402.3
title: 'Remove Beads project bootstrap, sync, and worktree plumbing'
status: Done
assignee:
  - oompah
created_date: '2026-06-01 19:20'
updated_date: '2026-06-08 23:18'
labels:
  - task
dependencies: []
parent_task_id: TASK-402
priority: high
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove project-management plumbing that exists only for Beads/.beads/dolt.

Context:
- oompah/projects.py currently installs a beads JSONL merge driver, bootstraps bd, synchronizes bd dolt state, and cleans .beads copies from worktrees.
- Backlog.md stores tasks as normal markdown files in backlog/tasks and backlog/completed, so this plumbing is obsolete.

Work required:
- Remove _install_beads_merge_driver, _configure_beads_jsonl_ignore, _bootstrap_beads, and related constants.
- Remove project-create validation that requires .beads and replace it with validation that Backlog.md is initialized.
- Remove startup sync entries that call bd dolt pull/push or report a beads sync status.
- Remove worktree cleanup logic that strips .beads forks or kills dolt SQL server processes.
- Remove BEADS_DIR propagation from worktree/session creation paths.
- Update __main__.py status output so it reports only git/backlog-relevant project sync state.

Files to inspect first:
- oompah/projects.py
- oompah/__main__.py
- oompah/orchestrator.py
- tests/test_projects.py
- tests/test_beads_merge_driver.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Project registration fails clearly when Backlog.md is not initialized.
- [ ] #2 Project registration no longer checks for .beads or runs bd bootstrap.
- [ ] #3 Startup sync no longer reports or executes a beads/dolt step.
- [ ] #4 Agent worktrees no longer receive BEADS_DIR.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read project create/sync/worktree tests to understand expected behavior.
2. Replace .beads checks with Backlog.md checks for backlog/config.yml or backlog/tasks.
3. Remove bd dolt sync and merge-driver installation.
4. Rewrite project tests around Backlog.md initialization requirements.
5. Delete obsolete Beads merge-driver tests.
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed as part of the Backlog-only tracker migration. Removed Beads/bd runtime paths where applicable, moved lifecycle behavior to canonical Backlog.md statuses, updated UI/API/tests/docs for Backlog-only behavior, and verified with make test: 3677 passed.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Focused project-store tests pass.
- [ ] #2 rg '.beads|BEADS_DIR|bd dolt|beads-jsonl' oompah tests shows no live runtime support.
<!-- DOD:END -->

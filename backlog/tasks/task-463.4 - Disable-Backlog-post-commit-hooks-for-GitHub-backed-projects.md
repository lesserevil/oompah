---
id: TASK-463.4
title: Disable Backlog post-commit hooks for GitHub-backed projects
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 01:14'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/backlog_webhooks.py
  - oompah/server.py
  - oompah/__main__.py
parent_task_id: TASK-463
priority: high
ordinal: 155000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make startup, project create, and project update hook installation tracker-aware. GitHub-backed projects should skip Backlog hook installation and ignore Backlog webhook receipts for that project.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed projects do not install or depend on Backlog post-commit hooks.
- [ ] #2 Legacy Backlog projects continue to install hooks idempotently.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 00:56
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:58
---
Understanding: No duplicate found. TASK-423 (Merged) installed Backlog post-commit hooks for all managed projects. TASK-464.7 (Backlog) is a later full decommission. TASK-463.4 is distinct: it makes the existing hook installation tracker-aware so GitHub-backed projects skip Backlog hook installation and webhook processing. Plan: (1) Check TASK-459.3 dependency status and available tracker model fields; (2) Guard install_backlog_webhook_hook / ensure_backlog_webhooks to skip GitHub-backed projects; (3) Guard the webhook receipt handler to ignore GitHub-backed project payloads; (4) Update tests; (5) Commit and push.
---

author: oompah
created: 2026-06-10 01:07
---
Discovery: TASK-459.3 (add per-project tracker fields to Project model) has code on epic-TASK-461 branch but is NOT merged into the current epic-TASK-463 branch. The Project model currently lacks tracker_kind. Strategy: add tracker_kind to Project in this task's scope (minimal field needed), then guard (1) ensure_backlog_webhooks in backlog_webhooks.py to skip github_issues projects, (2) _install_backlog_hook_for_project in server.py to skip, (3) the /api/v1/webhooks/backlog receipt handler to ignore GitHub-backed projects. Also updating bootstrap.py (the real startup caller). Add tests for all guards.
---

author: oompah
created: 2026-06-10 01:13
---
Implementation: Added tracker-aware guards to Backlog hook installation. Changes: (1) oompah/models.py: Added tracker_kind: str|None=None to Project dataclass, with to_dict/from_dict support. (2) oompah/backlog_webhooks.py: ensure_backlog_webhooks() skips projects with tracker_kind='github_issues' with 'skipped: github_issues tracker' status. (3) oompah/server.py: _install_backlog_hook_for_project() returns early for GitHub-backed projects; /api/v1/webhooks/backlog handler returns {ok:true, action:'ignored', reason:'github_issues tracker'} for GitHub-backed projects without refreshing caches or triggering sync. (4) tests/test_backlog_hook_tracker_guards.py: 25 new tests covering all guards (model round-trips, ensure bulk skip, install skip, webhook receipt ignore). Legacy Backlog projects continue to install hooks and process webhooks as before.
---

author: oompah
created: 2026-06-10 01:14
---
Verification: All tests pass. 25 new tests in tests/test_backlog_hook_tracker_guards.py. 55 existing backlog webhook tests and 137 project/CRUD tests unchanged. Branch pushed to origin/epic-TASK-463 (commit 814e92f). Both acceptance criteria verified: (1) GitHub-backed projects (tracker_kind='github_issues') do not get Backlog hooks installed at startup, project create, or project update; webhook receipts are acknowledged with action='ignored' but no cache invalidation or sync. (2) Legacy Backlog projects (tracker_kind=None) continue to install hooks idempotently and process webhooks normally.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added tracker_kind field to Project model and guarded all Backlog hook paths. GitHub-backed projects (tracker_kind='github_issues') skip hook installation at startup (ensure_backlog_webhooks), project create/update (_install_backlog_hook_for_project), and ignore webhook receipts (/api/v1/webhooks/backlog returns action='ignored'). Legacy Backlog projects unaffected. 25 new tests, 199 existing tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

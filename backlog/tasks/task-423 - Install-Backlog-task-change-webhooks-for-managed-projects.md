---
id: TASK-423
title: Install Backlog task-change webhooks for managed projects
status: Merged
assignee:
  - oompah
created_date: '2026-06-02 21:07'
updated_date: '2026-06-03 04:48'
labels: []
dependencies: []
priority: high
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add project-level Backlog.md task-change webhook setup so oompah is notified when backlog task files are added, modified, or deleted in each managed project. On startup and project add/update, ensure each managed repo has a compatible Backlog webhook configured to POST to the local oompah server. The webhook handler should pull/sync the project promptly, invalidate issue caches, and request a UI refresh. Include tests for idempotent webhook configuration and webhook receipt triggering project sync.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 01:06

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 01:14

Understanding: Backlog.md v1.45.2 has no native webhook command. The implementation uses git post-commit hooks installed into managed project repos. When a commit touches backlog/tasks/*.md or backlog/completed/*.md, the hook POSTs to oompah new /api/v1/webhooks/backlog endpoint. The webhook handler invalidates issue caches, triggers project sync, and requests a UI refresh. Plan: (1) oompah/git_hooks/post-commit script, (2) oompah/backlog_webhooks.py module, (3) server endpoint, (4) startup integration, (5) tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-03 02:00

Implementation complete. Key changes: (1) oompah/git_hooks/post-commit - self-contained Python script installed as a git hook in managed repos; detects backlog file changes, POSTs HMAC-SHA256-signed payload to oompah webhook endpoint; sentinel marker for idempotency; non-blocking (3s timeout, exceptions swallowed). (2) oompah/backlog_webhooks.py - validate_backlog_webhook_signature(), install_backlog_webhook_hook(), ensure_backlog_webhooks(); symlink-or-copy installation, idempotency via marker. (3) oompah/server.py - POST /api/v1/webhooks/backlog endpoint invalidates issue cache, calls request_refresh(), spawns background sync thread; _install_backlog_hook_for_project() called from create/update project endpoints. (4) oompah/__main__.py - ensure_backlog_webhooks() called on startup. (5) plans/backlog-task-change-webhooks.md - design doc with Mermaid diagram. 55 new tests, 308 total passing.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 02:01

Verification: All 55 new tests pass (39 in test_backlog_webhooks.py, 16 in test_server_backlog_webhook.py). Full test suite: 308 tests pass with 1 pre-existing warning. Key test coverage: idempotent hook installation (marker detection), HMAC-SHA256 signature validation, invalid signature rejection, cache invalidation on webhook receipt, background sync thread spawned, ensure_backlog_webhooks bulk idempotency, startup integration, and project create/update hook installation. Branch pushed to origin/TASK-423.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding: Backlog.md v1.45.2 has no native webhook command. Using git post-commit hooks in managed repos. Agent starting implementation.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Installed Backlog task-change webhooks for managed projects via git post-commit hooks (Backlog.md v1.45.2 has no native webhook command). New files: oompah/git_hooks/post-commit (self-contained Python hook with HMAC-SHA256 signing, idempotency sentinel, 3s timeout), oompah/backlog_webhooks.py (install/validate/ensure functions), tests/test_backlog_webhooks.py (39 tests), tests/test_server_backlog_webhook.py (16 tests), plans/backlog-task-change-webhooks.md (design doc). Modified: oompah/server.py (POST /api/v1/webhooks/backlog endpoint with cache invalidation + background sync, _install_backlog_hook_for_project called on create/update), oompah/__main__.py (ensure_backlog_webhooks on startup). 308 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

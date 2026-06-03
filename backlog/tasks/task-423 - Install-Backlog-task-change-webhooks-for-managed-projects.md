---
id: TASK-423
title: Install Backlog task-change webhooks for managed projects
status: In Progress
assignee:
- oompah
created_date: 2026-06-02 21:07
updated_date: 2026-06-03 01:14
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
<!-- COMMENTS:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding: Backlog.md v1.45.2 has no native webhook command. Using git post-commit hooks in managed repos. Agent starting implementation.
<!-- SECTION:NOTES:END -->

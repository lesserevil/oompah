---
id: TASK-423
title: Install Backlog task-change webhooks for managed projects
status: Open
assignee:
  - oompah
created_date: '2026-06-02 21:07'
updated_date: '2026-06-02 21:13'
labels: []
dependencies: []
priority: high
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add project-level Backlog.md task-change webhook setup so oompah is notified when backlog task files are added, modified, or deleted in each managed project. On startup and project add/update, ensure each managed repo has a compatible Backlog webhook configured to POST to the local oompah server. The webhook handler should pull/sync the project promptly, invalidate issue caches, and request a UI refresh. Include tests for idempotent webhook configuration and webhook receipt triggering project sync.
<!-- SECTION:DESCRIPTION:END -->

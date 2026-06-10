---
id: TASK-511
title: Fix GitHub tracker cutover bootstrap for managed projects
status: Done
assignee:
  - oompah
created_date: '2026-06-10 15:40'
updated_date: '2026-06-10 15:43'
labels: []
dependencies: []
priority: high
ordinal: 238000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Hotfix: managed-project GitHub Issues cutover currently has two bootstrap failures. Project-scoped GitHubIssueTracker instances do not use the managed project's access_token, so private/project-specific task hubs may fail auth. Also, PATCHing tracker_kind/tracker_owner/tracker_repo leaves the orchestrator's cached tracker instance stale until restart, so a cutover can keep using the old Backlog tracker. Fix both so operator/API cutovers take effect immediately and use the project token.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed managed-project GitHub Issues cutover bootstrap. Project-scoped GitHubIssueTracker construction now receives the managed project's access_token, so private/project-specific task hubs can authenticate without relying on global env or gh CLI auth. Project PATCH updates to tracker config or access_token now invalidate the per-project tracker cache, branch index cache, stale cache, and issues API cache so cutover settings take effect immediately. Verification: .venv/bin/python -m pytest tests/test_backlog_tracker.py tests/test_github_tracker.py tests/test_projects_crud.py tests/test_mixed_tracker_regression.py -q (582 passed).
<!-- SECTION:FINAL_SUMMARY:END -->

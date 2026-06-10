---
id: TASK-503
title: Clean up stale gh-webhook repository hooks before forwarder launch
status: Done
assignee:
  - oompah
created_date: '2026-06-10 02:45'
updated_date: '2026-06-10 02:48'
labels:
  - bug
dependencies: []
priority: high
ordinal: 221000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The gh webhook forward extension leaves a repository hook behind when the local forwarder exits unexpectedly. On restart, gh webhook forward fails with HTTP 422 'Hook already exists on this repository', so oompah never receives GitHub webhook events. Before launching a repo-scoped forwarder, remove stale cli/gh-webhook hooks for the target repo using the project token, and keep failures visible without leaking secrets.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added stale cli/gh-webhook repository hook cleanup before managed forwarder launches, using the project token environment and keeping inspection/delete failures visible without blocking launch.
<!-- SECTION:FINAL_SUMMARY:END -->

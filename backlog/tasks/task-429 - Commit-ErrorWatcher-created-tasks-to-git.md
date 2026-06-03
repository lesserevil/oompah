---
id: TASK-429
title: Commit ErrorWatcher-created tasks to git
status: Done
assignee: []
created_date: '2026-06-03 04:35'
updated_date: '2026-06-03 04:40'
labels:
  - bug
dependencies: []
priority: high
ordinal: 64000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ErrorWatcher currently creates Backlog.md task files in the tracker repo, but leaves them untracked. For oompah's own project this means the managed checkout never sees them, so they cannot appear on the dashboard or be scheduled after moving to an active state. Add best-effort git persistence for ErrorWatcher-created tasks: stage only the new task file, commit it with the canonical oompah trailer, and push the current branch. Failures must be logged without cascading into error reporting.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented best-effort git persistence for ErrorWatcher-created Backlog tasks. ErrorWatcher now stages only the created task file, commits it with the canonical oompah trailer using git commit --only, pushes the current branch, and treats git failures as non-fatal. Added tests for successful remote push, preserving unrelated staged/untracked work, and push failure behavior.
<!-- SECTION:FINAL_SUMMARY:END -->

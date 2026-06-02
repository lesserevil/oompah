---
id: TASK-419
title: Ensure In Review tasks always have review artifacts
status: Done
assignee:
  - oompah
created_date: '2026-06-02 15:54'
updated_date: '2026-06-02 15:58'
labels:
  - bug
dependencies: []
priority: high
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: a task could end up treated as review-ready without an actual PR/MR or CI/review process acting on it. Reproduce with an agent worktree that closes a task after pushing a branch while the managed checkout only sees the remote-tracking branch or review creation fails. Expected behavior: remote-only task branches are recognized as unmerged work; successful review handoff creates or finds a PR/MR and then marks the task In Review; failed handoff reopens the task with an actionable comment instead of silently logging or leaving the work stranded.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 15:54

Implementing guard so In Review is only set after a PR/MR exists, and failed review handoff reopens the task with an actionable comment.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the review handoff invariant. Close-gate commit counting now recognizes remote-tracking task branches in managed checkouts. Successful review handoff marks tasks In Review only after a PR/MR exists, failed handoff for unmerged work reopens the task with an actionable comment, worker exit no longer records a clean completion when review handoff fails, and merged-branch reconciliation now scans In Review/Needs CI Fix/Needs Rebase so landed PRs move to Merged. Verified with focused tests and make test.
<!-- SECTION:FINAL_SUMMARY:END -->

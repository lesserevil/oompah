---
id: TASK-461.8
title: Preserve completed shared epic child tasks during orphan reset
status: Done
assignee:
  - oompah
created_date: '2026-06-10 00:45'
updated_date: '2026-06-10 01:00'
labels: []
dependencies: []
parent_task_id: TASK-461
priority: high
ordinal: 214000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: when an agent completes a shared-epic Backlog task in its worker worktree, the worker-exit path can recognize the terminal Done state, but the managed checkout may still show In Progress. The orphan reset sweep then resets the task to Open when _done_issue_has_unmerged_review_work returns false, as observed with TASK-461.1 on 2026-06-10. Completed tasks must remain Done and must not become dispatchable again.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed orphan reset so completed tasks tracked in orchestrator state are preserved as Done, including shared epic child tasks without per-child review branches. Verified with focused orchestrator tests and full make test.
<!-- SECTION:FINAL_SUMMARY:END -->

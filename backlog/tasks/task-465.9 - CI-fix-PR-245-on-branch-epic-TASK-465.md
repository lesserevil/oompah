---
id: TASK-465.9
title: 'CI fix: PR #245 on branch epic-TASK-465'
status: Done
assignee:
  - oompah
created_date: '2026-06-09 03:48'
updated_date: '2026-06-09 03:55'
labels: []
dependencies: []
parent_task_id: TASK-465
ordinal: 190000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
YOLO: CI tests failed on MR #245 (branch epic-TASK-465). The branch's primary task TASK-465 (type=epic) has 6 children and won't be dispatched. This sibling task carries the actual fix work.

Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-09 03:51

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the PR #245 CI failure by carrying enqueue-time duplicate wakeups into the per-tick coalesced event count. Added focused regression coverage and verified make test: 5428 passed, 4 skipped.
<!-- SECTION:FINAL_SUMMARY:END -->

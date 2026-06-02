---
id: TASK-417
title: >-
  [backend:server] Add comment API error: backlog command failed (exit 1):
  error: unknown option '--comment'
status: Done
assignee:
  - oompah
created_date: '2026-06-02 14:06'
updated_date: '2026-06-02 14:15'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add comment API error: backlog command failed (exit 1): error: unknown option '--comment'
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed comment posting by removing oompah's runtime dependency on 'backlog task edit --comment'. BacklogMdTracker now appends Backlog.md comment blocks directly to the task markdown, preserves the author, increments comment indexes, and updates updated_date. The dashboard submit handler now preserves the typed draft and alerts on failed POST responses instead of silently clearing the input. Verification: focused tests passed; make test passed with 3755 tests; service restarted on port 8090; live POST to TASK-407.1 returned HTTP 201 and the comment was readable afterward as id 2.
<!-- SECTION:FINAL_SUMMARY:END -->

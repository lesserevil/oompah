---
id: TASK-416
title: Ensure Needs Human tasks always include an actionable comment
status: Done
assignee: []
created_date: '2026-06-02 08:56'
updated_date: '2026-06-02 09:03'
labels:
  - bug
dependencies: []
priority: high
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: tasks can appear in the dashboard Needs Human column without any task comment explaining what a human should do. This leaves operators with no actionable context. Add a code-level invariant so any oompah transition into the canonical Needs Human status posts an oompah-authored comment first, and repair existing active Needs Human tasks that have no comments.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 08:57

Confirmed bug: the managed oompah repo has active Needs Human tasks with empty comment sections. Logs show these came from the orchestrator completed-without-closing give-up path, so the fix must preserve/add an actionable comment whenever oompah moves a task to Needs Human.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented a Needs Human comment invariant. BacklogMdTracker now serializes per-task CLI and frontmatter mutations, exposes mark_needs_human() that leaves the explanatory comment as the final write, and metadata writes preserve comments. Orchestrator give-up/landing-gate transitions and PATCH /api/v1/issues status changes now use the helper. Added regression tests for tracker order/comment preservation, API Needs Human comments, and the completed-without-closing orchestrator path. Also repaired the seven live oompah Needs Human tasks by adding actionable comments in the managed repo.
<!-- SECTION:FINAL_SUMMARY:END -->

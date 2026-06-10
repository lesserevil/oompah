---
id: TASK-508.1
title: Auto-close standalone task PRs blocked by epic-owned policy
status: Done
assignee:
  - oompah
created_date: '2026-06-10 08:16'
updated_date: '2026-06-10 08:19'
labels:
  - bug
dependencies: []
parent_task_id: TASK-508
priority: high
ordinal: 230000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-508. When a managed project has require_epic_for_tasks enabled and YOLO sees an already-open standalone task PR whose source branch resolves to a top-level non-epic task, oompah must close that stale review and reconcile the task metadata instead of repeatedly logging gate_blocked and leaving the UI in In Review. This prevents old task PR artifacts from violating the one-PR-per-epic policy or slowing every tick.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added SCMProvider.close_review for GitHub and GitLab, then wired YOLO's require_epic_for_tasks gate to close stale standalone task PRs automatically. Closed invalid standalone PRs now get provider-visible audit comments and task reconciliation: In Review tasks move to Needs Human, while already-Done tasks stay Done with an audit comment. Added focused regression coverage for the YOLO close path and SCM provider close calls.
<!-- SECTION:FINAL_SUMMARY:END -->

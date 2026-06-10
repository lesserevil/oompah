---
id: TASK-469.5.2
title: Use accelerated YAML loader for Backlog task parsing
status: Done
assignee: []
created_date: '2026-06-10 08:47'
updated_date: '2026-06-10 08:47'
labels: []
dependencies: []
parent_task_id: TASK-469.5
priority: high
ordinal: 232000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live monitoring showed /api/v1/issues snapshot refreshes taking 57-78s for about 1404 Backlog tasks, causing GIL contention and stale UI data even after maintenance lane fixes. PyYAML CSafeLoader is available in the running environment, but BacklogMdTracker used yaml.safe_load on the issue-board hot path. Switch the tracker frontmatter/config reads to the accelerated safe loader while preserving safe parsing semantics.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed BacklogMdTracker YAML reads to use PyYAML CSafeLoader when available, falling back to SafeLoader. Added a regression test proving loader selection and frontmatter parsing still work. Verified with: uv run pytest tests/test_backlog_tracker.py tests/test_server_issue_snapshot.py -q (64 passed).
<!-- SECTION:FINAL_SUMMARY:END -->

---
id: OOMPAH-186
type: task
status: Open
priority: 2
title: Add task CLI commands to edit and remove source references
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:44:41.783116Z'
updated_at: '2026-07-13T02:45:02.928808Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

The task CLI supports --source when creating a task but exposes no command to change or clear that source reference afterward. Add a task subcommand or cohesive command pair that (1) sets/replaces a task's source reference and (2) removes it entirely. Reuse the server/tracker update path so native Markdown and supported tracker backends persist the same canonical source metadata. Define clear command syntax, help text, validation errors, and stable machine-readable output. Tests: parser/help coverage; set source; replace existing source; remove source; missing task/project; invalid input; and backend persistence through the server API. Update CLI/API documentation. Acceptance: an operator can create a task, change its source, verify the new source with task view, then remove it and verify no source remains—without editing task files directly.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


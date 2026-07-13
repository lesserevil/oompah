---
id: OOMPAH-186
type: task
status: In Progress
priority: 2
title: Add task CLI commands to edit and remove source references
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:44:41.783116Z'
updated_at: '2026-07-13T02:54:53.310974Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: fe940984-495e-4b87-87eb-03851596c09b
---
## Summary

The task CLI supports --source when creating a task but exposes no command to change or clear that source reference afterward. Add a task subcommand or cohesive command pair that (1) sets/replaces a task's source reference and (2) removes it entirely. Reuse the server/tracker update path so native Markdown and supported tracker backends persist the same canonical source metadata. Define clear command syntax, help text, validation errors, and stable machine-readable output. Tests: parser/help coverage; set source; replace existing source; remove source; missing task/project; invalid input; and backend persistence through the server API. Update CLI/API documentation. Acceptance: an operator can create a task, change its source, verify the new source with task view, then remove it and verify no source remains—without editing task files directly.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 02:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 02:47
---
UNDERSTANDING: Searched all tasks for duplicates (title grep, content grep for 'set-source', 'source reference', 'edit source', etc.). No duplicate found — this is a unique work item. 

Plan: OOMPAH-186 asks for two new CLI subcommands: (1) `oompah task set-source <task-id> <source>` to set/replace a task's source reference and (2) `oompah task remove-source <task-id>` to clear it entirely. These must reuse the server/tracker update path so native Markdown tasks persist the change. Must include help text, validation, machine-readable output, and tests (parser, set, replace, remove, missing task/project, invalid input, backend persistence). Also needs CLI/API doc updates.

Starting with codebase exploration to find existing --source implementation in task create.
---
author: oompah
created: 2026-07-13 02:54
---
DISCOVERY: No duplicate found. Codebase analysis complete.

Key findings:
1. Source is stored as 'Triggered by: X\n\n' prefix in issue.description (server.py ~L2641)
2. The PATCH /api/v1/issues/{id} endpoint accepts description and persists via tracker.update_issue()
3. test_task_cli.py and test_server_create_issue.py show the test patterns to follow
4. docs/task-epic-workflow.md has the CLI Reference section to update

Plan:
- Add _strip_source_header() helper to server.py
- Add source_task_id / clear_source handling to api_update_issue() PATCH endpoint
- Add _cmd_set_source() and _cmd_remove_source() in task_cli.py
- Add set-source and remove-source subparsers
- Add tests: parser coverage, set, replace, remove, error cases, server backend
- Update docs/task-epic-workflow.md CLI Reference section
---
<!-- COMMENTS:END -->

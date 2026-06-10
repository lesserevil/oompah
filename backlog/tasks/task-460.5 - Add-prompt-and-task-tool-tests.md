---
id: TASK-460.5
title: Add prompt and task-tool tests
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 05:32'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-460
priority: medium
ordinal: 135000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add snapshot and behavioral coverage for GitHub-backed prompts, legacy Backlog prompts, oompah task wrapper operations, local-server failures, and task creation routing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Prompt tests prove Backlog commands are absent for GitHub-backed tasks.
- [ ] #2 Task wrapper tests cover create, comment, status, labels, and errors.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 05:26
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 05:30
---
Understanding: No duplicate found. Searched for tasks related to 'prompt task-tool tests', 'snapshot behavioral tests prompts', and 'github-backed prompts'. The only related tasks are TASK-460.1-460.4 (all Done), which are the upstream subtasks this task was designed to complement. TASK-460.5 is a unique test-coverage consolidation task, not a duplicate.
---

author: oompah
created: 2026-06-10 05:31
---
Discovery: All required test coverage already exists in the codebase, added inline by the prior subtasks. AC1 (prompt tests prove Backlog commands absent for GitHub-backed tasks): test_prompt.py::TestTrackerSpecificConditionalRendering::test_github_backed_shows_oompah_commands + test_workflow_md_renders_for_github_issue + test_github_follow_up_does_not_include_backlog_source cover this exactly. AC2 (task wrapper tests: create, comment, status, labels, errors): test_task_cli.py::TestCmdCreate/TestCmdComment/TestCmdSetStatus/TestCmdAddLabel/TestCmdRemoveLabel/TestHttpErrorHandling cover all operations and local-server failure scenarios. 149 tests pass across test_prompt.py, test_task_cli.py, test_server_create_issue.py, test_server_dependencies.py.
---

author: oompah
created: 2026-06-10 05:31
---
Verification: Ran python -m pytest tests/test_prompt.py tests/test_task_cli.py tests/test_server_create_issue.py tests/test_server_dependencies.py. Result: 149 passed in 0.75s. Both ACs verified: AC1 — test_github_backed_shows_oompah_commands asserts 'backlog task view/edit/create' all absent from GitHub-backed prompt output; test_workflow_md_renders_for_github_issue verifies end-to-end with actual WORKFLOW.md. AC2 — TestHttpErrorHandling covers connection error + timeout + 4xx (local-server failures); TestCmdCreate/Comment/SetStatus/AddLabel/RemoveLabel cover all wrapper operations.
---

author: oompah
created: 2026-06-10 05:32
---
Completion: All acceptance criteria are met by test coverage that was added inline during TASK-460.1/460.2/460.3. No additional code changes needed. AC1: test_prompt.py::TestTrackerSpecificConditionalRendering has snapshot-style tests proving Backlog commands are absent from GitHub-backed prompts (oompah commands present, backlog task view/edit/create absent). AC2: test_task_cli.py has behavioral tests covering all wrapper operations (create, comment, set-status, add/remove-label, set-dependency) and local-server failures (ConnectError, TimeoutException, 4xx). 149 tests pass. Pushed to epic-TASK-460.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
All acceptance criteria satisfied by test coverage added inline during TASK-460.1/460.2/460.3. AC1 (Backlog commands absent for GitHub-backed prompts): test_prompt.py::TestTrackerSpecificConditionalRendering (test_github_backed_shows_oompah_commands, test_workflow_md_renders_for_github_issue, test_github_follow_up_does_not_include_backlog_source). AC2 (task wrapper create/comment/status/labels/errors): test_task_cli.py::TestCmdCreate/Comment/SetStatus/AddLabel/RemoveLabel/HttpErrorHandling. 149 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

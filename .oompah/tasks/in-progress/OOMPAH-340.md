---
id: OOMPAH-340
type: task
status: In Progress
priority: null
title: Extend parse_gitlab_webhook and server handler for Push/Issue/Note/Pipeline/Job
  hooks
parent: OOMPAH-325
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:28:20.576396Z'
updated_at: '2026-07-22T01:30:52.923608Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a42e74e8-93f3-4ff4-97d3-e9f884e1c9ba
oompah.task_costs:
  total_input_tokens: 300324
  total_output_tokens: 2630
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 300324
      output_tokens: 2630
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 300324
    output_tokens: 2630
    cost_usd: 0.0
    recorded_at: '2026-07-22T01:30:49.861891+00:00'
---
## Summary

Extend the GitLab webhook parser and server endpoint to handle all subscribed hook types — not just Merge Request Hook.

## Scope

Files to modify:
- oompah/webhooks.py — parse_gitlab_webhook()
- oompah/server.py — /api/v1/webhooks/gitlab endpoint (response format for non-MR events)

The test engineer has already committed failing test contracts in tests/test_webhooks.py and tests/test_server_webhooks.py (unstaged on branch epic-OOMPAH-318). Stage and commit them alongside the implementation.

## What to implement

In parse_gitlab_webhook() (oompah/webhooks.py line 582):
- Currently returns None for anything other than 'Merge Request Hook'
- Extend to handle:
  - Push Hook: set action='pushed', target_branch from ref (strip refs/heads/), author from user_username, repo_slug from project.path_with_namespace
  - Issue Hook: set action from object_attributes.action, issue_number from object_attributes.iid (as str), title from object_attributes.title, repo_slug from project.path_with_namespace; for label-update events, extract the last label name from changes.labels.current and set label_name
  - Note Hook: set action from object_attributes.action, comment_id from object_attributes.id (as str), issue_number from object_attributes.noteable_iid (as str) when noteable_type=='Issue', repo_slug from project.path_with_namespace
  - Pipeline Hook: set action from object_attributes.status, target_branch from object_attributes.ref, repo_slug from project.path_with_namespace
  - Job Hook: set action from build_status, target_branch from ref, repo_slug from project.path_with_namespace
- Unknown event types (e.g. 'Wiki Page Hook') continue to return None
- All normalized events have provider='gitlab' and the correct event_type set

In /api/v1/webhooks/gitlab server handler:
- When parse_gitlab_webhook returns a non-None event for Push Hook, process it (call _handle_webhook_event, return action='processed' and call request_refresh)
- The test expects: resp.json()['action'] == 'processed' and orch.request_refresh.assert_called_once()

## Tests that must pass (already written)

In tests/test_webhooks.py::TestParseGitLabWebhook:
- test_supported_project_hook_is_normalized[push]
- test_supported_project_hook_is_normalized[issue]
- test_supported_project_hook_is_normalized[note]
- test_supported_project_hook_is_normalized[pipeline]
- test_supported_project_hook_is_normalized[job]
- test_label_update_retains_label_name_for_downstream_invalidation

In tests/test_server_webhooks.py::TestGitLabWebhookEndpoint:
- test_push_event_is_processed_and_refreshes_tracked_branch

All other existing tests must continue to pass.

## Acceptance criteria
- `make test` (or `.venv/bin/pytest tests/test_webhooks.py tests/test_server_webhooks.py -v`) passes with no new failures
- No webhook secret appears in logs

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 00:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 00:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 00:40
---
Understanding: Investigating OOMPAH-340 as a Duplicate Investigator. The issue requests extending parse_gitlab_webhook and the server handler to support Push, Issue, Note, Pipeline, and Job hooks (currently only Merge Request Hook is handled). Searching for existing tasks that may cover the same ground before any implementation work begins.
---
author: oompah
created: 2026-07-22 01:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 01:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 01:30
---
Agent completed successfully in 65s (302954 tokens)
---
author: oompah
created: 2026-07-22 01:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 8
- Tokens: 300.3K in / 2.6K out [303.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 5s
- Log: OOMPAH-340__20260722T012947Z.jsonl
---
author: oompah
created: 2026-07-22 01:30
---
Agent completed without closing this issue (65s (302954 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->

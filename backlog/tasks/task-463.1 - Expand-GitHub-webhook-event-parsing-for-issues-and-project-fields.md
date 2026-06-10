---
id: TASK-463.1
title: Expand GitHub webhook event parsing for issues and project fields
status: Done
assignee: []
created_date: 2026-06-08 17:58
updated_date: 2026-06-10 00:27
labels:
- task
- github-issues
- tracker-migration
dependencies:
- TASK-458.4
- TASK-459.1
references:
- plans/github-issues-tracker-migration.md
modified_files:
- oompah/server.py
- tests/test_webhooks.py
parent_task_id: TASK-463
priority: high
ordinal: 152000
oompah.task_costs:
  total_input_tokens: 31
  total_output_tokens: 6797
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 31
      output_tokens: 6797
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 31
    output_tokens: 6797
    cost_usd: 0.0
    recorded_at: '2026-06-10T00:21:54.344140+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add parsing and validation for issues, issue_comment, label, pull_request, push, and project-field events needed by GitHub-backed task tracking. Reuse existing GitHub webhook auth and redaction patterns.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Issue, comment, label, PR, push, and project field events are parsed into normalized events.
- [ ] #2 Invalid signatures and unsupported events are handled safely.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 00:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:05
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 00:18
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:20
---
UNDERSTANDING: This issue asks to add parsing for issues, issue_comment, label, pull_request, push, and project-field events. Investigation confirmed NO duplicate exists — TASK-463.3 depends on this work (it handles docs after parsing is done). The implementation is already present as unstaged changes in the worktree: webhooks.py has all 4 new parser functions + WebhookEvent extended fields; server.py propagates the new fields in _handle_webhook_event; tests/test_webhooks.py has comprehensive coverage. Running tests confirms 129 pass. Now staging and committing.
---

author: oompah
created: 2026-06-10 00:21
---
DISCOVERY + IMPLEMENTATION: All code was already present as unstaged changes in the worktree. oompah/webhooks.py: WebhookEvent extended with issue_number, comment_id, label_name, project_item_id, project_field_name, project_field_value; parse_github_webhook() routes issues/issue_comment/label/projects_v2_item; 4 new private parser functions. oompah/server.py: _handle_webhook_event() propagates all new extended fields. tests/test_webhooks.py: 4 new test classes (TestParseGitHubIssuesWebhook, TestParseGitHubIssueCommentWebhook, TestParseGitHubLabelWebhook, TestParseGitHubProjectsV2ItemWebhook). Invalid signatures handled by existing validate_github_signature(); unsupported events return None.
---

author: oompah
created: 2026-06-10 00:21
---
VERIFICATION: 153 tests pass (129 in test_webhooks.py + 24 in test_server_webhooks.py). AC#1 verified: issues, issue_comment, label, PR, push, projects_v2_item events all parsed into normalized WebhookEvent objects. AC#2 verified: validate_github_signature() returns False for invalid/missing signatures; parse_github_webhook() returns None for unsupported event types. Branch epic-TASK-463 pushed to origin.
---
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-10 00:05

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-10 00:05

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-10 00:18

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-10 00:18

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-10 00:22

Agent completed successfully in 234s (6828 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-10 00:22

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 69, Tool calls: 43
- Tokens: 31 in / 6.8K out [6.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 54s
- Log: TASK-463.1__20260610T001812Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added parsing and validation for issues, issue_comment, label, pull_request, push, and projects_v2_item events. WebhookEvent dataclass extended with issue_number, comment_id, label_name, project_item_id, project_field_name, project_field_value fields. parse_github_webhook() routes all 6 event types; 4 new private parsers (_parse_github_issues, _parse_github_issue_comment, _parse_github_label, _parse_github_projects_v2_item). server.py _handle_webhook_event propagates new fields. 153 tests pass (129 + 24). Both ACs met: normalized event parsing + safe signature validation and unsupported-event handling.
<!-- SECTION:FINAL_SUMMARY:END -->

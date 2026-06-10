---
id: TASK-463.1
title: Expand GitHub webhook event parsing for issues and project fields
status: Open
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 00:21'
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
<!-- COMMENTS:END -->

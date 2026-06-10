---
id: TASK-463.3
title: Update webhook forwarder event set and documentation
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 01:25'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-463.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - docs/webhook-forwarding.md
  - plans/backlog-task-change-webhooks.md
parent_task_id: TASK-463
priority: medium
ordinal: 154000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update local development and operator docs for gh webhook forward so issue, issue_comment, label, project item/field, pull_request, and push events reach oompah. Include verification and troubleshooting steps.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Docs list the required GitHub events for GitHub-backed tasks.
- [ ] #2 Docs distinguish GitHub task webhooks from legacy Backlog post-commit webhooks.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 01:16
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 01:17
---
UNDERSTANDING: This is NOT a duplicate. TASK-463.1 (Done) added event parsing; TASK-463.3 documents the expanded event set. No other tasks cover this documentation work. Plan: (1) Update docs/webhook-forwarding.md to list all required events (issue, issue_comment, label, projects_v2_item, pull_request, push) and distinguish them from legacy Backlog post-commit webhooks; (2) Update plans/backlog-task-change-webhooks.md as needed; (3) Update any env/config defaults in code that still mention only push,pull_request. AC#1: docs list required GitHub events for GitHub-backed tasks. AC#2: docs distinguish GitHub task webhooks from legacy Backlog post-commit webhooks.
---

author: oompah
created: 2026-06-10 01:19
---
DISCOVERY: Key findings: (1) oompah/webhooks.py line 641: _WEBHOOK_DEFAULT_EVENTS = 'push,pull_request' — needs updating to include issues, issue_comment, label, projects_v2_item. (2) docs/webhook-forwarding.md has 3 places mentioning 'push,pull_request' event list, no Backlog webhook distinction. (3) tests/test_webhooks.py at lines 1637 and 1846 hardcode 'push,pull_request' — need updating after code change. (4) .env.example has no OOMPAH_WEBHOOK_EVENTS entry. Changes needed: update _WEBHOOK_DEFAULT_EVENTS, update docs with full event set + Backlog distinction + verification steps, update tests, update .env.example.
---

author: oompah
created: 2026-06-10 01:25
---
IMPLEMENTATION: Changes made across 5 files. (1) oompah/webhooks.py: Updated _WEBHOOK_DEFAULT_EVENTS from 'push,pull_request' to 'push,pull_request,issues,issue_comment,label,projects_v2_item'; updated module docstring; updated WebhookForwarder events docstring. (2) docs/webhook-forwarding.md: Full rewrite — added 'Two webhook channels' table (AC#2 GitHub vs Backlog hook distinction), 'Required GitHub events' table (AC#1), updated all event references, added verification steps for expanded set including projects_v2_item caveat, added 'Relation to Backlog task-change webhooks' section. (3) plans/backlog-task-change-webhooks.md: Added 'Scope: Backlog.md-backed projects only' section explaining GitHub-backed projects skip the Backlog hook. (4) tests/test_webhooks.py: Updated 2 hardcoded 'push,pull_request' assertions to the new full default. (5) .env.example: Added OOMPAH_WEBHOOK_EVENTS entry with inline documentation.
---
<!-- COMMENTS:END -->

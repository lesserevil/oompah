---
id: TASK-457.2
title: Add structured tracker identity to Issue records
status: Done
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-08 20:51'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/models.py
  - oompah/server.py
  - oompah/prompt.py
parent_task_id: TASK-457
priority: high
ordinal: 110000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Extend normalized issue data so oompah can represent fully qualified GitHub issue identities while preserving existing Backlog identifiers. Include tracker kind, owner, repo, numeric issue number, display identifier, and stable provider URL where appropriate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Backlog tasks continue to serialize with their existing identifier shape.
- [ ] #2 GitHub-backed issues can be represented without bare-number ambiguity.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:42
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:46
---
Extended Issue class with GitHub identity fields: tracker_kind, owner, repo, issue_number, display_identifier, provider_url. Preserves existing Backlog identifiers.
---

author: oompah
created: 2026-06-08 20:50
---
Successfully extended the normalized Issue class with GitHub identity fields: tracker_kind, owner, repo, issue_number, display_identifier, provider_url. Preserves existing Backlog identifiers while enabling structured GitHub issue representation.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Extended Issue class with GitHub identity fields
<!-- SECTION:FINAL_SUMMARY:END -->

---
id: TASK-458.3
title: 'Implement GitHub issue list, detail, and status filtering'
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 117000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Map GitHub Issues plus Oompah Status fields into normalized Issue records. Support fetch_all_issues, fetch_candidate_issues, fetch_issues_by_states, fetch_issue_states_by_ids, labels, priority, target branch, project ID, URL, timestamps, and issue type.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Candidate fetch returns only configured dispatchable statuses.
- [ ] #2 Pagination and empty result sets are tested.
<!-- AC:END -->

---
id: TASK-457.4
title: Add shared tracker contract tests
status: In Progress
assignee: []
created_date: 2026-06-08 17:56
updated_date: 2026-06-08 20:44
labels:
- task
- github-issues
- tracker-migration
dependencies:
- TASK-457.1
references:
- plans/github-issues-tracker-migration.md
modified_files:
- tests
parent_task_id: TASK-457
priority: high
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create backend-neutral contract tests for issue creation, state transitions, comments, labels, parent/child relationships, dependencies, metadata, archive detection, missing issue behavior, and candidate sorting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Contract tests can run against BacklogMdTracker and a fake tracker implementation.
- [ ] #2 Future GitHubIssueTracker tests can reuse the same contract suite.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-08 20:44

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

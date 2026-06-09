---
id: TASK-458.3
title: 'Implement GitHub issue list, detail, and status filtering'
status: Done
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-09 06:46'
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

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 06:16
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 06:17
---
Focus: Feature Developer
---

author: oompah
created: 2026-06-09 06:26
---
Agent stalled 1 time(s) (562s (366506 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 06:26
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 365.6K in / 935 out [366.5K total]
- Cost: $0.0000
- Exit: stalled, Duration: 9m 22s
- Log: TASK-458.3__20260609T061726Z.jsonl
---

author: oompah
created: 2026-06-09 06:27
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 06:28
---
Focus: Feature Developer
---

author: oompah
created: 2026-06-09 06:32
---
Agent stalled 2 time(s) (279s (316006 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 06:32
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 315.0K in / 1.0K out [316.0K total]
- Cost: $0.0000
- Exit: stalled, Duration: 4m 39s
- Log: TASK-458.3__20260609T062811Z.jsonl
---

author: oompah
created: 2026-06-09 06:34
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-09 06:37
---
UNDERSTANDING: This task requires implementing the issue list, detail, and status filtering methods in GitHubIssueTracker. The stub methods (fetch_all_issues, fetch_candidate_issues, fetch_issues_by_states, fetch_issue_states_by_ids, fetch_issue_detail, fetch_children, fetch_comments, fetch_issues_by_labels) all return empty lists/dicts. I need to: (1) add status encoding helpers using oompah:status:* labels as proxy for GitHub Projects custom field, (2) implement _gh_issue_to_issue mapper, (3) implement all fetch methods using existing GitHubClient with pagination, (4) add tests for candidate filtering and pagination. Previous 2 runs stalled without writing any code.
---

author: oompah
created: 2026-06-09 06:46
---
COMPLETION: Implemented GitHub issue list, detail, and status filtering in oompah/github_tracker.py.

Changes:
- Added status encoding via oompah:status:* GitHub labels (REST-compatible proxy for GitHub Projects custom fields)
- Added _gh_issue_to_issue() mapper covering all required fields: state, labels, priority, issue type, timestamps, URL, target branch, project ID, tracker identity
- Implemented all stub fetch methods: fetch_all_issues, fetch_candidate_issues (filters to active_states, sorts by priority/created_at), fetch_issues_by_states (smart open/closed/all query), fetch_issue_states_by_ids, fetch_issue_detail (404 returns None), fetch_children (sub-issues API + label fallback), fetch_comments, fetch_issues_by_labels
- Added 96 new tests: status helpers, mapper unit tests, all fetch method integration tests with mocking including pagination (multi-page) and empty result sets
- Both acceptance criteria met: #1 candidate fetch filtering, #2 pagination and empty results tested
- 205 tests pass in test_github_tracker.py
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented GitHub issue list, detail, and status filtering. Added status encoding via oompah:status:* GitHub labels as REST-compatible status proxy. Implemented all fetch methods (fetch_all_issues, fetch_candidate_issues, fetch_issues_by_states, fetch_issue_states_by_ids, fetch_issue_detail, fetch_children, fetch_comments, fetch_issues_by_labels) plus _gh_issue_to_issue mapper covering labels, priority, issue type, timestamps, URL, target branch, project ID, tracker identity. Added 96 tests covering all helpers, mapper, and fetch methods including pagination and empty result sets. Both acceptance criteria met.
<!-- SECTION:FINAL_SUMMARY:END -->

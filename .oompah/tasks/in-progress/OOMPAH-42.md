---
id: OOMPAH-42
type: task
status: In Progress
priority: 1
title: Run post-release install and bootstrap smoke checks
parent: OOMPAH-37
children: []
blocked_by:
- OOMPAH-41
labels: []
assignee: null
created_at: '2026-06-22T01:17:50.933134Z'
updated_at: '2026-06-22T17:25:37.653532Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 87bb8761-c9ad-4466-8ba6-ad39e33e1624
---
## Summary

Plan: plans/oompah-1.0-release.md#release-execution-and-verification

WHAT TO DO
Run post-release smoke checks for Git tag install, wheel install, CLI help, task command help, project-bootstrap help, and managed-project bootstrap preview/status.

HOW TO VERIFY
Post-release verification results are recorded on this task, including any follow-up tasks for non-blocking findings.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 17:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 17:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 17:25
---
UNDERSTANDING: Not a duplicate. OOMPAH-42 is the unique E5 step in the 1.0 release plan. All other release tasks are distinct: OOMPAH-38=E1 (Done), OOMPAH-39=E2 (Done), OOMPAH-40=E3 (Done), OOMPAH-41=E4 (Done, v1.0.0 published at https://github.com/lesserevil/oompah/releases/tag/v1.0.0). No other task covers post-release smoke checks from the published artifacts. Plan: (1) Git tag install from v1.0.0, (2) Wheel install from GitHub Release, (3) CLI/task/project-bootstrap --help checks, (4) managed-project bootstrap preview/status. Proceeding with E5 work.
---
<!-- COMMENTS:END -->

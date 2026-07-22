---
id: OOMPAH-337
type: task
status: Open
priority: null
title: Build GitLabIssueTracker core REST adapter and protocol registration
parent: OOMPAH-323
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T23:24:30.718256Z'
updated_at: '2026-07-22T00:37:52.255932Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 06094d1b-b458-4c29-866f-62cd06a7c195
---
## Summary

Implement the foundational GitLab Issues adapter in oompah/gitlab_tracker.py and register gitlab_issues in oompah/tracker.py. Model transport, token/base-URL handling, nested namespace project URL encoding, pagination, timeout/retry/error normalization, GitLab issue-to-Issue mapping, globally unambiguous identifiers, issue detail/list/state queries, labels, notes/comments, and issue create/update/close/reopen/archive operations. Reuse established GitHub tracker semantics where provider-neutral. Add focused unit tests using mocked GitLab API responses for every implemented TrackerProtocol method, pagination, encoded project paths, and API failure handling. Do not implement external intake. Acceptance: GitLabIssueTracker satisfies TrackerProtocol and standard task lifecycle calls work without GitHub paths; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 00:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 00:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

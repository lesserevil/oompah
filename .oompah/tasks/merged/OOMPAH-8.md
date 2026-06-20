---
id: OOMPAH-8
type: task
status: Merged
priority: null
title: Add installed CLI smoke coverage
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-20T02:13:20.713362Z'
updated_at: '2026-06-20T14:53:02.055017Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#315
  owner: lesserevil
  repo: oompah
  number: '315'
  url: https://github.com/lesserevil/oompah/issues/315
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Merged
  last_synced_at: '2026-06-20T14:52:03.403823+00:00'
  migrated_at: '2026-06-20T02:13:20.715240Z'
  migrated_from_tracker: github_issues
  external_state: open
  external_created_at: '2026-06-15T02:39:16Z'
  external_updated_at: '2026-06-15T05:24:20Z'
  external_parent_id: lesserevil/oompah#312
  last_github_state: closed
---
## Summary

Add automated coverage that verifies the GitHub-distributed CLI works after installation.

Implementation notes:
- build or install the package into an isolated environment from the current source artifact
- verify the oompah console script starts and prints help
- verify oompah task --help is available
- where practical, exercise server URL/port parsing without requiring a live production server

Acceptance criteria:
- tests fail if the console script entry point is missing or broken
- tests fail if oompah task cannot be invoked after package installation
- coverage is included in the project test or CI path appropriate for packaging changes

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/315
- Requestor: @lesserevil
- Reference: lesserevil/oompah#315

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


---
id: OOMPAH-9
type: task
status: Done
priority: null
title: Update managed-project guidance for optional oompah CLI use
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-20T02:13:20.718959Z'
updated_at: '2026-06-20T02:14:02.575723Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#316
  owner: lesserevil
  repo: oompah
  number: '316'
  url: https://github.com/lesserevil/oompah/issues/316
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Done
  last_synced_at: '2026-06-20T02:13:20.721017Z'
  migrated_at: '2026-06-20T02:13:20.721020Z'
  migrated_from_tracker: github_issues
  external_state: open
  external_created_at: '2026-06-15T02:39:23Z'
  external_updated_at: '2026-06-15T05:40:31Z'
  external_parent_id: lesserevil/oompah#312
---
## Summary

Update the templates and generated instructions that oompah writes into managed projects so they describe oompah task commands accurately.

Implementation notes:
- AGENTS.md guidance may reference oompah task only when the CLI is available and configured for the local oompah server
- include GitHub-native fallback instructions for parent/child relationships and dependencies when the CLI is unavailable
- state that body text like Parent: #123 is human context only and not sufficient for oompah rollups/dispatch
- point users to structured GitHub sub-issues/dependencies or oompah-compatible fallback labels where appropriate

Acceptance criteria:
- newly bootstrapped or updated managed projects do not require an unpublished CLI without explaining how to install/configure it
- instructions preserve oompah-compatible parent/child and dependency metadata
- existing tests for project template generation are updated or added

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/316
- Requestor: @lesserevil
- Reference: lesserevil/oompah#316

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


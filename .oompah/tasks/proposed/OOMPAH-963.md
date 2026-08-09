---
id: OOMPAH-963
type: task
status: Proposed
priority: null
title: 'OOMPAH-960: Consume parent-scoped canonical child landing facts'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-08-09T14:59:47.450633Z'
updated_at: '2026-08-09T14:59:56.711497Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#768
  owner: lesserevil
  repo: oompah
  number: '768'
  url: https://github.com/lesserevil/oompah/pull/768
  requestor_login: NVShawn
  imported_comment_ids:
  - '5232157145'
  last_synced_status: Proposed
  last_synced_at: '2026-08-09T14:59:48.570298+00:00'
---
## Summary

### Summary
- resolve durable parent-scoped landing facts for their exact child source
- bind imports to current direct containment, project, route, source, revision, durability, and target history
- preserve fail-closed behavior for ambiguous or stale evidence

### Tests
- `tests/test_integration_workflow.py`: 113 passed
- epic workflow/adapter focus: 91 passed
- terminal mutation and secret scans passed

Task: OOMPAH-960

### External GitHub Issue
- URL: https://github.com/lesserevil/oompah/pull/768
- Requestor: @NVShawn
- Reference: lesserevil/oompah#768

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: NVShawn
created: 2026-08-09 14:59
---
Corrected the exact-head review blocker in `b9db677d1c4736a9c976c9a4ae3f8be33a9c071b`.

The parent-scoped resolver now uses a bounded indexed exact source/target landing-fact query, so 1,000 lexically earlier sibling facts cannot hide a valid child proof. Foreign, corrupt, ambiguous, route-mismatched, and revision-stale evidence remains fail closed. The regression crosses the prior 1,000-row boundary.

Validation: 10 focused tests passed; `tests/test_integration_workflow.py` + `tests/test_workflow_jobs.py`: 193 passed; terminal mutation scan and secret scan passed.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-963
type: task
status: Archived
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
updated_at: '2026-08-09T16:11:34.154653Z'
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
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c57ca92b151f
    project_id: proj-14849f1b
    task_id: OOMPAH-963
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 83fb17fd81755906bf6e1df1979bc2dcfd935ea0cf50af611806e3d693f76444
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner cleanup of an erroneously imported GitHub pull request:
      OOMPAH-963 points to merged PR #768 and duplicates the delivered OOMPAH-960
      review artifact. Runtime logs prove PR issue_comment events entered the uncovered
      intake path; OOMPAH-964 tracks the systemic fix.'
    created_at: '2026-08-09T16:11:27.233114+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-09 16:09
---
Duplicate/erroneous-intake evidence: this native Proposed task points to https://github.com/lesserevil/oompah/pull/768 and its title/body are the merged OOMPAH-960 pull request, not a customer GitHub issue. Runtime logs record issue_comment.created deliveries for #768 at 2026-08-09T14:59:41 and 14:59:54; GitHub uses issue_comment for PR conversation as well as issue conversation. Existing main already filters PRs from GitHub issues-list polling and PR-backed issues events, so the uncovered path is PR-backed issue_comment intake. Follow-up bug OOMPAH-964 records the systemic fix and regression requirements. Archiving this task as erroneous imported review metadata; no implementation is due under OOMPAH-963.
---
<!-- COMMENTS:END -->

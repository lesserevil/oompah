---
id: OOMPAH-626
type: bug
status: In Progress
priority: 1
title: Supersede in-flight terminal audits when evidence changes
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:02:35.998442Z'
updated_at: '2026-07-30T22:02:38.677544Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: update TerminalTransitionCoordinator transition staging so a new request for the same target with a changed evidence fingerprint supersedes an existing in-progress audit record as well as pending and completed records. The old worker may finish, but its result must fail the existing audit-id/state/fingerprint CAS and must never apply a terminal state to stale evidence. Preserve coalescing for identical evidence and the ordered Done/Merged/Archived chain contract. Relevant context: OOMPAH-591 gained audit-0e821c979fd2 while audit-85eb5879d029 was still in progress; recovery later changed the old record back to pending, leaving two eligible Done audits with different fingerprints. Tests: reproduce staging changed evidence over an in-progress record, verify only the fresh record remains eligible, verify a late result for the superseded record is rejected, and run focused coordinator/dispatcher tests plus the Makefile gate. Acceptance criteria: one active audit per target/evidence revision; stale in-flight results cannot close the task; focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


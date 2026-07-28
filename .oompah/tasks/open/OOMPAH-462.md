---
id: OOMPAH-462
type: feature
status: Open
priority: 1
title: Define terminal-audit records, enums, and evidence fingerprints
parent: OOMPAH-457
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:05:04.307001Z'
updated_at: '2026-07-28T18:06:15.386009Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Create a small terminal-audit domain module with typed enums/dataclasses for target state (Done, Merged, Archived), request state, verdict, failure classification, contributor identity, evidence fingerprint, and audit attempt. Define versioned to_dict/from_dict methods with strict required-field validation and forward-compatible optional fields. Build a deterministic SHA-256 evidence fingerprint from normalized requirements text, project/task identity, source and target branch names/SHAs, review identity/state, child-audit digest, and contributor identities. Never include credentials, full diffs, or model prose in the fingerprint payload.

Tests

Test deterministic serialization and hashing, order-independent contributor/child input, changed requirements/SHA/review/children producing a new fingerprint, malformed/unknown enum rejection, and legacy missing optional fields. Run focused tests and make test.

Acceptance criteria

Other tasks can construct, persist, and compare terminal-audit records without tracker-specific logic; identical evidence produces the same fingerprint and every material evidence change produces a different one.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


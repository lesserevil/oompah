---
id: OOMPAH-593
type: task
status: Open
priority: 1
title: Integrate and live-verify scoped Codex task CLI authentication
parent: OOMPAH-586
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:54.281403Z'
updated_at: '2026-07-30T14:47:50.858035Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7e0d6ed69f96dd5e289a4e8acbb2b5007bf599bb935b31f5a64158dcb9377c21
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 46537354-a353-431e-ab09-87ea34c58167
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T14:47:49.776663+00:00'
  claim_expires_at: '2026-07-30T15:17:49.776663+00:00'
  retry_count: 0
  retry_after: null
---
## Summary

Triggered by: OOMPAH-575

Implementation scope

Use the existing OOMPAH-575 branch rather than reimplementing it. Get its focused handoff-auth regression through the normal delivery path, deploy it, then run a live least-privilege probe from a service-launched Codex task: view, comment, coordinate if allowed, and submit its assigned task; verify an unrelated task and expired/missing capability fail closed. Record only safe evidence. If the live path still returns 401, fix the actual launch/environment propagation gap with tests before resubmission.

Tests

Retain OOMPAH-575 focused suites, add any live-path reproducer required, and run make test for the final head.

Acceptance criteria

OOMPAH-575 reaches Merged; a newly launched Codex worker completes the documented task CLI workflow with no operator credentials and no broader task authority.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
<!-- COMMENTS:END -->

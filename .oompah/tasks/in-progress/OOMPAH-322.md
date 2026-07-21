---
id: OOMPAH-322
type: task
status: In Progress
priority: 1
title: Add GitLab pipeline and commit CI status support
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-321
labels: []
assignee: null
created_at: '2026-07-21T20:33:52.275830Z'
updated_at: '2026-07-21T23:59:30.932532Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8ea3f1fb-761b-4e50-a704-d8ccf70004d6
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Implement GitLab pipeline/job lookup for branch heads, commit SHAs, and MRs using the forge-neutral CI contract. Normalize pipeline/job outcomes to passed, failed, pending, or unknown; include bounded actionable warnings and job/pipeline URLs. Support self-managed GitLab API bases.

Do not wire orchestration behavior in this task; expose provider methods and tests only.

Tests:
- Success, failure, canceled, skipped, running, pending, no-pipeline, forbidden, rate-limited, and malformed-response fixtures.
- Multiple pipeline/job aggregation and deterministic warning ordering.
- Contract parity assertions against the GitHub CI result shape.

Acceptance criteria:
- Callers can determine GitLab CI state for a MR, branch, or commit without parsing provider payloads.
- Unavailable CI permissions are visible as capability warnings, not false success.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:59
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

---
id: OOMPAH-329
type: task
status: In Progress
priority: 1
title: Add cross-forge GitLab acceptance and migration test suite
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-321
- OOMPAH-322
- OOMPAH-323
- OOMPAH-324
- OOMPAH-325
- OOMPAH-326
- OOMPAH-327
- OOMPAH-328
labels: []
assignee: null
created_at: '2026-07-21T20:34:42.931068Z'
updated_at: '2026-07-22T07:52:06.744334Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9f297a26-1c31-4c84-8b9b-fbeaf915aa55
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Migration, testing, and acceptance.

Add the final cross-forge acceptance layer after all GitLab feature tasks land. Build network-free GitLab HTTP fixtures and a provider contract suite shared with GitHub. Add gated integration configuration for GitLab.com and a GitLab 17.x self-managed fixture; standard tests must not require credentials or network. Verify existing GitHub projects load unchanged and GitLab projects cover setup, task lifecycle, native intake, MR/pipeline lifecycle, webhook/polling fallback, selected release delivery, and CI remediation.

Tests:
- Execute the shared provider and tracker contracts for both forges.
- Migration fixture for persisted pre-forge GitHub project records.
- Gated live GitLab.com and self-managed smoke tests, skipped with explicit reason when credentials are absent.

Acceptance criteria:
- The full plan acceptance criteria are demonstrably covered by automated tests.
- No standard test needs a GitLab token, public endpoint, or live GitLab service.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 07:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 07:52
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

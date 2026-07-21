---
id: OOMPAH-329
type: task
status: Backlog
priority: 1
title: Add cross-forge GitLab acceptance and migration test suite
parent: OOMPAH-318
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T20:34:42.931068Z'
updated_at: '2026-07-21T20:34:42.931068Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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


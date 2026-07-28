---
id: OOMPAH-470
type: feature
status: Backlog
priority: 1
title: Seed the auditor role and select an independent provider-model candidate
parent: OOMPAH-458
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:06:10.311921Z'
updated_at: '2026-07-28T13:06:10.311921Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Create a reserved editable auditor role. On migration, seed it from the deduplicated union of deep, standard, and default role candidates, followed by remaining configured provider defaults; do not hardcode local provider IDs. Implement candidate filtering that first respects project provider whitelist, credentials, health, budget, and model validity, then excludes every contributor model. Prefer a provider not used by any contributor. Fall back to a contributing provider only when its candidate has an explicit model ID different from every contributed model on that provider. An SDK-managed unknown model on a contributing provider is not independently provable and must be excluded. Return normalized no-candidate reasons.

Tests

Cover different provider/model, same-provider different model fallback, same model on another provider, multi-contributor epic exclusion, unknown ACP models, round-robin ordering, whitelist, unhealthy/missing credentials, budget, empty role, migration seeding, and no-candidate diagnostics. Run focused tests and make test.

Acceptance criteria

Selected auditors are demonstrably independent under the agreed policy; unsafe or unverifiable candidates are never used; operators can edit auditor candidates through the existing role configuration path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


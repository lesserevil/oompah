---
id: OOMPAH-470
type: feature
status: Open
priority: 1
title: Seed the auditor role and select an independent provider-model candidate
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-468
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:10.311921Z'
updated_at: '2026-07-28T22:17:20.637081Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e2241edb48d51aa19dd51c349cf33ea284834053394f0393dcce2d7d457837e5
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 265a34d4-a053-4502-b771-1694f7f0f996
  claim_owner: f5cb4973-0a40-4473-8af0-31431f690e1c
  claimed_at: '2026-07-28T22:17:14.574889+00:00'
  claim_expires_at: '2026-07-28T22:47:14.574889+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 13bb0b95-5345-4d91-9e96-dd5fb343b2bb
oompah.work_branch: epic-OOMPAH-458
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 22:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:17
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

---
id: TASK-407
title: 'Epic: multi-provider role assignments and failover'
status: Merged
assignee: []
created_date: '2026-06-01 21:43'
updated_date: '2026-06-11 17:12'
labels:
  - feature
  - epic
  - 'needs:backend'
  - 'needs:frontend'
  - 'needs:test'
dependencies: []
priority: high
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add support for assigning multiple provider/model candidates to each oompah role assignment. Each role must choose candidates with either priority order or least-recently-used round-robin order. When a selected candidate cannot start because of provider availability, credentials, budget, rate limit, overload, timeout, or invalid model, oompah should try the next candidate before giving up on the task.

This epic also includes a provider test button on the Providers page so operators can manually verify a provider with a tiny prompt without creating an oompah task or changing role selector state.

Important boundaries:
- The candidate list belongs to the role assignment, not to the provider.
- Existing single provider/model role config must keep working through migration.
- A normal task failure after an agent has already started work should continue through the existing retry/escalation path unless the failure is clearly provider-capacity or provider-auth related.
- The Providers page must continue to support existing providers while adding candidate editing and provider testing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each role can store more than one provider/model candidate.
- [ ] #2 Each role can be configured as priority or round-robin.
- [ ] #3 Priority roles try candidates in configured order.
- [ ] #4 Round-robin roles select the least-recently-used candidate first, then fall through to the remaining candidates.
- [ ] #5 Provider availability failures can fall back to the next candidate without creating duplicate task work.
- [ ] #6 The Providers page includes a manual provider test button for each provider block.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All child tasks are complete and tested.
- [ ] #2 make test passes.
<!-- DOD:END -->

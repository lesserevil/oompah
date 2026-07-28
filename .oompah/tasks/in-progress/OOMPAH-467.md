---
id: OOMPAH-467
type: feature
status: In Progress
priority: 1
title: Add explicit authorized owner overrides for terminal audits
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-466
labels: []
assignee: null
created_at: '2026-07-28T13:05:09.155697Z'
updated_at: '2026-07-28T20:05:07.309116Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 0888bf70-257e-428e-839e-40de2770175b
oompah.work_branch: epic-OOMPAH-457
---
## Summary

Implementation scope

Add an explicit coordinator override operation requiring an actor, project-owner authorization through the existing transition authorization helpers, requested terminal target, current evidence fingerprint, and a non-empty reason. Reject implicit label changes and blank reasons. Persist an override audit record and human-readable comment before applying the target. Expose a typed result/error for later API and CLI integration. Never treat the oompah bot or an auditor agent as an owner unless existing project-owner rules independently authorize that identity.

Tests

Cover authorized owner, additional authorized login, unauthorized actor, bot-only actor, blank reason, stale fingerprint, repeated override, metadata/comment failure ordering, and redaction. Run focused tests and make test.

Acceptance criteria

A verified project owner can deliberately bypass auditing with a durable reason; no other path or actor can produce an override; normal audit requests remain mandatory.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 20:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 20:05
---
Focus: Api Oompah Integration Specialist
---
<!-- COMMENTS:END -->

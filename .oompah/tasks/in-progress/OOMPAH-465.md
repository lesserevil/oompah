---
id: OOMPAH-465
type: feature
status: In Progress
priority: 1
title: Implement idempotent terminal-transition staging and audit chains
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-461
- OOMPAH-462
- OOMPAH-463
labels: []
assignee: null
created_at: '2026-07-28T13:05:07.200491Z'
updated_at: '2026-07-28T19:17:07.220875Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ca99560e-6794-4d78-a222-ff3deec2c557
oompah.work_branch: epic-OOMPAH-457
---
## Summary

Implementation scope

Implement a TerminalTransitionCoordinator owned by the orchestrator/server bootstrap. Its request_transition method accepts the current issue, requested terminal target, trigger identity, project/tracker context, and evidence fingerprint. It must atomically persist the request before moving the item to In Validation. Done creates one audit. Merged reuses a current passed Done audit or queues Done then Merged. Archived creates a safe-retirement audit after any pending earlier target. Repeated identical requests coalesce; a changed fingerprint supersedes pending work; stale requests cannot apply status. Use per-project locking and post a concise queued comment once.

Tests

Cover every target and chain, direct Merged with/without current Done evidence, duplicate events, changed fingerprints, simultaneous requests, superseded chains, tracker write failure ordering, restart-recovered requests, and comment deduplication. Run focused tests and make test.

Acceptance criteria

No terminal status is written by staging, every request has one durable chain, direct Merged cannot skip completion auditing, and retries/events cannot create duplicate auditor work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 19:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 19:17
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

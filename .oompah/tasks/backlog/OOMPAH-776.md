---
id: OOMPAH-776
type: feature
status: Backlog
priority: 1
title: Implement TransitionIntent, transition journal, and TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:58:49.998013Z'
updated_at: '2026-08-04T13:58:49.998013Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Create the project-scoped TaskTransitionService foundation. Define TransitionIntent/TransitionOutcome with expected status/version, desired status, evidence generation/head, actor/authority, stable reason code, idempotency key, and originating job. Persist an append-only transition journal with atomic idempotency lookup; perform compare-and-swap precondition checks; apply and verify tracker effects; adapt terminal targets through TerminalTransitionCoordinator. Preserve existing API behavior initially. Required tests: replay/idempotency, stale generation, actor/project isolation, concurrent conflicting intents, tracker failure before/after effect, terminal staging, and journal corruption handling. Acceptance: the service safely handles every transition class and provides a restart-verifiable record before call-site migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


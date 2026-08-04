---
id: OOMPAH-776
type: feature
status: Ready to Integrate
priority: 1
title: Implement TransitionIntent, transition journal, and TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-772
labels: []
assignee: null
created_at: '2026-08-04T13:58:49.998013Z'
updated_at: '2026-08-04T14:59:52.223178Z'
work_branch: epic-OOMPAH-769--task-OOMPAH-776
target_branch: epic-OOMPAH-769
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.target_branch: epic-OOMPAH-769
oompah.work_branch: epic-OOMPAH-769--task-OOMPAH-776
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-769--task-OOMPAH-776
  base_branch: epic-OOMPAH-769
  head_sha: db015701875b7976bfdaa7993b4043f2a21f2817
  submitted_at: '2026-08-04T14:59:43.290461+00:00'
  updated_at: '2026-08-04T14:59:43.290461+00:00'
---
## Summary

Create the project-scoped TaskTransitionService foundation. Define TransitionIntent/TransitionOutcome with expected status/version, desired status, evidence generation/head, actor/authority, stable reason code, idempotency key, and originating job. Persist an append-only transition journal with atomic idempotency lookup; perform compare-and-swap precondition checks; apply and verify tracker effects; adapt terminal targets through TerminalTransitionCoordinator. Preserve existing API behavior initially. Required tests: replay/idempotency, stale generation, actor/project isolation, concurrent conflicting intents, tracker failure before/after effect, terminal staging, and journal corruption handling. Acceptance: the service safely handles every transition class and provides a restart-verifiable record before call-site migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:59
---
Implementation complete on the private task branch: added immutable TransitionIntent/Outcome contracts, a SQLite append-only journal with atomic idempotency registration and durable per-task claims, stable authority versioning that excludes benign metadata churn, status/generation/head fencing, verified and restart-recoverable tracker effects, and a TerminalTransitionCoordinator adapter that never writes terminal targets directly. Coverage includes idempotent replay, conflicting keys, cross-service concurrency, stale status/version/generation/head, project isolation, illegal edges, failures before and after effects, terminal staging/recovery, restart, append-only enforcement, expired claims, and corruption. 202 focused/adjacent tests passed, the final 38 service tests passed, Ruff/format/diff/secret checks are clean, and the terminal mutation scan passes.
---
author: oompah
created: 2026-08-04 14:59
---
Implemented a durable project-scoped task transition service with immutable version/head-fenced intents, append-only SQLite journal, atomic idempotency, per-task claims, restart verification, terminal-audit staging adapter, documentation, and comprehensive concurrency/failure coverage (202 adjacent tests passed).
---
<!-- COMMENTS:END -->

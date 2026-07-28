---
id: OOMPAH-460
type: epic
status: Open
priority: 1
title: Expose terminal audits in the UI, observability, migration, and end-to-end
  tests
parent: null
children:
- OOMPAH-484
- OOMPAH-485
- OOMPAH-486
- OOMPAH-487
- OOMPAH-488
- OOMPAH-489
blocked_by:
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:03:47.776498Z'
updated_at: '2026-07-28T18:10:06.553659Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Make independent terminal auditing understandable and operable: expose In Validation and audit progress in APIs and the dashboard, provide actionable health signals, document configuration and owner overrides, migrate existing installations safely, and validate the complete lifecycle end to end.

Required behavior

- The board and task detail surfaces show In Validation, requested target, audit phase, attempts, evidence revision, safe auditor identity, and latest verdict.
- Service status reports queued/running/passed/failed/retried/stale/overridden/no-candidate metrics.
- Alerts appear only for actionable audit stalls or missing independent candidates; normal successful audits are not alerts.
- Existing terminal records are grandfathered once and remain stable across restart. A later status or evidence change invalidates the grandfather record.
- Old OOMPAH_VERIFY_COMPLETION settings are deprecated with clear startup and operator guidance.
- End-to-end tests cover worker to Done audit, review merge to Merged audit, archive audit, nested/shared epics, stale verdicts, restart recovery, and owner override.

Constraints

Build after terminal paths are integrated. Configuration examples go in .env.example and user-facing operation guidance goes in docs/. Documentation diagrams must use Mermaid. All code changes require tests.

Acceptance criteria

Operators can see why a task is waiting, which evidence was audited, what action is required on failure, and whether the system has an eligible independent auditor. Upgrade and complete lifecycle tests pass through make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:10
---
Queued for execution. Every child explicitly depends on OOMPAH-459, so no epic-OOMPAH-460 branch/worktree will be created until OOMPAH-459 has landed. Its first dispatch will therefore branch from the then-latest main.
---
<!-- COMMENTS:END -->

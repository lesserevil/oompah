---
id: OOMPAH-481
type: feature
status: Open
priority: 1
title: Route automatic archive and intake retirement through Archived audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-475
labels: []
assignee: null
created_at: '2026-07-28T13:07:29.211296Z'
updated_at: '2026-07-28T18:07:21.185873Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Update auto-archive maintenance, external issue close/archive reconciliation, duplicate retirement, error-task cleanup, and other automatic archive_issue/status=Archived calls to request an Archived audit. Supply retention or structured disposition reason and pre-archive state. Do not repeatedly request archive while an audit is pending. On unsafe retirement, restore the recorded prior state or use the coordinator failure classification. Existing archived upgrade records stay grandfathered.

Tests

Cover aged Done/Merged auto-archive, recent item, active review/agent/retry, external issue close, duplicate with source reference, missing disposition evidence, repeated maintenance ticks, failed tracker writes, unsafe restoration, and grandfathered Archived records. Run archive/intake/error-watcher tests and make test.

Acceptance criteria

No automatic path hides unresolved work in Archived; valid retirement remains bounded/idempotent and produces a concise durable audit comment.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


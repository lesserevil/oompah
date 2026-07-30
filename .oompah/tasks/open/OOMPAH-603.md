---
id: OOMPAH-603
type: feature
status: Open
priority: 2
title: Define and enforce repository hygiene health thresholds
parent: OOMPAH-588
children: []
blocked_by:
- OOMPAH-600
- OOMPAH-601
- OOMPAH-602
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:16:03.538398Z'
updated_at: '2026-07-30T14:19:28.448902Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Turn cleanup inventory into actionable health rather than raw counts. Report registered worktrees and local/remote branches by active, dirty, unmerged, terminal-protected, shared-owner, and safely-prunable categories; define configurable age/count thresholds in .env/.env.example; alert only on overdue safely-prunable artifacts or cleanup errors. Provide an operator verification path in docs/. Relevant files include maintenance status/state APIs, cleanup scheduler, dashboard/operator docs, and configuration.

Tests

Cover healthy protected inventory, overdue safe artifacts, dirty/unmerged preservation, threshold configuration, cleanup success/alert clear, restart persistence, and dashboard/API rendering. Run focused health/UI tests and make test.

Acceptance criteria

Operators can distinguish necessary retained work from hygiene debt, green status is based on zero overdue safe artifacts/errors rather than an unrealistic zero-branch count, and alerts clear after safe cleanup.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
<!-- COMMENTS:END -->

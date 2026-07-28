---
id: OOMPAH-464
type: feature
status: Backlog
priority: 1
title: Persist the upgrade grandfather baseline and recover pending audits
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-463
labels: []
assignee: null
created_at: '2026-07-28T13:05:06.169316Z'
updated_at: '2026-07-28T13:09:10.224219Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Extend service_state.json with a versioned terminal-audit enforcement record. On the first upgraded startup, snapshot each existing terminal task as a grandfather tuple of project, task, terminal state, and current evidence fingerprint. Reuse that baseline across restart. A task that leaves and later re-enters terminal state, or whose evidence fingerprint changes, is no longer grandfathered. Also scan In Validation metadata on startup and rebuild pending audit queue entries without duplicating attempts. Keep legacy/corrupt entries fail-closed and observable.

Tests

Use temporary service-state and fake trackers to cover first startup, second startup, unchanged grandfathered records, changed evidence, terminal-to-nonterminal-to-terminal, pending queue recovery, duplicate suppression, corrupt state, and multiple projects with overlapping task IDs. Run focused tests and make test.

Acceptance criteria

Deployment does not retroactively audit existing terminal records, restart does not forget enforcement or pending work, and any post-upgrade terminal/evidence change requires a fresh audit.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


---
id: OOMPAH-551
type: feature
status: Backlog
priority: 1
title: Persist coordination messages and derive peer suggestions
parent: OOMPAH-550
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T16:23:14.047092Z'
updated_at: '2026-07-29T16:23:14.047092Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement a versioned SQLite CoordinationStore under Oompah service state with message IDs, project/task/run identities, kind, text, changed paths, commit SHA, timestamps, and delivered/read state. Derive peer suggestions from direct dependency neighbors, inherited epic relationships, active siblings, and live changed-path overlap. Bound message size and retention and make all writes idempotent and restart-safe.

Tests must cover schema migration, concurrent writers, restart recovery, ordering, idempotency, retention, graph derivation, inherited relationships, overlap detection, and empty/terminal projects.

Acceptance criteria: coordination history is durable and queryable, peer results are deterministic and project-scoped, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


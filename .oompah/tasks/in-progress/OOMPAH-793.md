---
id: OOMPAH-793
type: feature
status: In Progress
priority: 1
title: Cut implementation, direct-owner, handoff, and retry ownership over to durable
  jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:21.541694Z'
updated_at: '2026-08-04T18:23:59.471871Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Migrate scheduler claim-to-worker-start, implementation generations, direct-owner leases, focus handoff, duplicate screening, worker exit, validation submission, authority revocation, and retry timers to workflow jobs and transition intents. Expected/advisory policy denials must not poison completion; late worker results must be fenced; direct owners and agents share one ownership model. Required tests: claim/start crash window, restart redispatch, owner takeover races, token/peer authorization changes, successful work plus handoff denial, incomplete sessions, branch reuse, retry expiry, and OOMPAH-732/751. Acceptance: each In Progress task has exactly one durable implementation/direct-owner disposition and no process-local authority race can strand or revert accepted work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


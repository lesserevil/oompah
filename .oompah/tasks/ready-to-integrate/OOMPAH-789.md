---
id: OOMPAH-789
type: task
status: Ready to Integrate
priority: 1
title: Add restart and external-failure injection at every workflow boundary
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-790
- OOMPAH-783
labels: []
assignee: null
created_at: '2026-08-04T13:59:14.267846Z'
updated_at: '2026-08-04T18:10:01.407505Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-789
  head_sha: 6ae941a31682dce6cd9346c3c4d7116a4c2db8ae
  submitted_at: '2026-08-04T18:09:54.391958+00:00'
  updated_at: '2026-08-04T18:09:54.391958+00:00'
---
## Summary

Create controllable fault hooks/test adapters for process death or exception before/after job enqueue, lease, revalidation, Git/forge effect, tracker mutation, verification, transition journaling, and completion. Inject stale/missing tracker snapshots, duplicate/dropped events, fetch failure, deleted branches, target/head changes, expired leases, auth/policy changes, transport failures, and concurrent API/scheduler intents. Use real temporary SQLite, native Markdown trackers, and Git repositories. Acceptance: each boundary has a deterministic restart test; recoverable faults converge after restart; unrecoverable faults become bounded action_required without unsafe mutation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 18:09
---
Implemented typed, deterministic, serializable one-shot fault scripts covering both sides of all eight workflow boundaries, with adapters for the real job store, action handlers, transition journal, native tracker, snapshots, event delivery, authority, leases, and Git refs. Tests inject restart, stale/missing/fetch/transport, duplicate/drop, deleted/moved branch, auth/policy, lease, and concurrency faults. Verification: 43 new tests and 238 composed workflow tests pass; Ruff, terminal scan, and secret scan pass. Exact pushed head: 6ae941a31.
---
author: oompah
created: 2026-08-04 18:10
---
Added deterministic boundary and external-failure injection harness at 6ae941a31.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-561
type: chore
status: Open
priority: 1
title: Prune terminal branches and worktrees aggressively
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:03:33.910422Z'
updated_at: '2026-07-29T21:04:27.847669Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5564fb01f918b647d6568a7856225eb465888ace4cce6e15dfcfc4de0aba2a7a
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: bace875b-486e-4749-a2ea-c4156149a042
  claim_owner: c2c2ef6b-2a29-4c5e-a18b-825e02f11596
  claimed_at: '2026-07-29T21:04:22.459415+00:00'
  claim_expires_at: '2026-07-29T21:34:22.459415+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 63d49c67-b723-49cf-8b36-15ba1c486945
---
## Summary

Increase cleanup throughput for the parallel agent scheduler. Scope: make managed repository fetches prune deleted remote-tracking refs; give worktree cleanup its own short configurable interval and a higher bounded default batch; make terminal Merged/Archived cleanup remove the task or epic worktree plus its Oompah-owned local and remote work branch; do not count already-absent resources against the mutation budget; and sweep fully merged local branches whose upstream is gone. Preserve active/shared epic branches and protect default, configured target/release, and Git state branches. Relevant files: oompah/config.py, oompah/orchestrator.py, oompah/projects.py, oompah/repo_health.py, .env.example, docs/tick-latency-diagnostics.md, and focused tests under tests/. Tests must cover branch ownership/protection, shared-child safety, remote/local deletion, gone-upstream pruning, no-op budget behavior, interval/default configuration, and fetch --prune. Acceptance criteria: terminal Oompah-owned worktrees and branches are removed within the cleanup cadence; branch/worktree volume cannot grow merely because completed entries are revisited; protected or active refs are never deleted; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 21:03
---
Implementation started from the primary checkout. Confirmed current gaps: five-minute inherited cleanup cadence, default batch 25, no-op entries consume the budget, terminal task/epic cleanup leaves local and remote branches, and managed fetch does not prune remote-tracking refs. Adding guarded terminal branch cleanup, safe gone-upstream pruning, independent interval/batch defaults, and regression coverage.
---
author: oompah
created: 2026-07-29 21:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 21:04
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

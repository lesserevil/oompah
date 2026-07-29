---
id: OOMPAH-561
type: chore
status: Backlog
priority: 1
title: Prune terminal branches and worktrees aggressively
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:03:33.910422Z'
updated_at: '2026-07-29T21:03:33.910422Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Increase cleanup throughput for the parallel agent scheduler. Scope: make managed repository fetches prune deleted remote-tracking refs; give worktree cleanup its own short configurable interval and a higher bounded default batch; make terminal Merged/Archived cleanup remove the task or epic worktree plus its Oompah-owned local and remote work branch; do not count already-absent resources against the mutation budget; and sweep fully merged local branches whose upstream is gone. Preserve active/shared epic branches and protect default, configured target/release, and Git state branches. Relevant files: oompah/config.py, oompah/orchestrator.py, oompah/projects.py, oompah/repo_health.py, .env.example, docs/tick-latency-diagnostics.md, and focused tests under tests/. Tests must cover branch ownership/protection, shared-child safety, remote/local deletion, gone-upstream pruning, no-op budget behavior, interval/default configuration, and fetch --prune. Acceptance criteria: terminal Oompah-owned worktrees and branches are removed within the cleanup cadence; branch/worktree volume cannot grow merely because completed entries are revisited; protected or active refs are never deleted; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes


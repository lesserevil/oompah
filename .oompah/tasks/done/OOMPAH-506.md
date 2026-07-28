---
id: OOMPAH-506
type: feature
status: Done
priority: 1
title: Run safe stale-cache and worktree cleanup daily and under storage pressure
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:06.576042Z'
updated_at: '2026-07-28T15:27:11.240453Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: existing maintenance removes terminal registered worktrees frequently but does not perform one comprehensive owned-cache scan, age stale temp/cache entries, rotate agent logs, or accelerate cleanup under disk pressure. The host currently has only a few GiB free while old managed build/cache trees remain.

Implementation: add an observable storage-cleanup maintenance job. Run a comprehensive scan at least once per 24 hours and earlier when configured free-byte or free-percent thresholds are crossed. Limit deletion to Oompah-owned roots and entries that are provably stale by age/state/registration; preserve active agent worktrees, Done/conflict worktrees, live temp files, valid unregistered Git worktrees, VM images, repositories, symlink targets, and unknown/unowned paths. Include stale managed temp/cache directories, unregistered invalid worktree directories, terminal Merged/Archived worktrees, and age/size-based agent-log rotation. Use atomic/defensive filesystem operations and bounded batches. All tunables belong in .env/.env.example: interval, pressure thresholds, minimum age, batch/byte limits, and log retention.

Tests: fake filesystem/project store tests for daily throttling, pressure override, low-space repeated batches, active preservation, ownership boundaries, symlinks, races/disappearing paths, permission errors, and metrics. Assert cleanup failures never stop scheduling. Add operator docs for inspection and recovery.

Acceptance criteria: a daily scan is guaranteed, pressure triggers an earlier scan, only safe owned stale data is removed, reclaimed bytes/counts and errors are visible in maintenance state, and no active work is deleted.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:27
---
Implemented and pushed in commit f3c0afce4. A new observable storage_cleanup job runs daily and repeats bounded batches under byte/percent pressure; it cleans aged private temp entries and JSONL logs, reuses tracker-aware Merged/Archived worktree cleanup, and preserves active logs, Done/conflict worktrees, valid/unknown paths, VM images, and symlink targets. Atomic quarantine, race/error handling, env tunables, metrics, and operator recovery docs are included. Focused cleanup/config suite: 82 passed; cleanup plus maintenance suite: 335 passed.
---
<!-- COMMENTS:END -->

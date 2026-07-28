---
id: OOMPAH-506
type: feature
status: Backlog
priority: 1
title: Run safe stale-cache and worktree cleanup daily and under storage pressure
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:06.576042Z'
updated_at: '2026-07-28T15:06:06.576042Z'
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


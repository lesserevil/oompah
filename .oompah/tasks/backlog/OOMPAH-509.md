---
id: OOMPAH-509
type: feature
status: Backlog
priority: 2
title: Parallelize pytest safely on isolated workers
parent: OOMPAH-502
children: []
blocked_by:
- OOMPAH-492
labels: []
assignee: null
created_at: '2026-07-28T15:06:10.253754Z'
updated_at: '2026-07-28T15:06:58.224808Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: make test runs roughly 12k tests serially despite 64 CPUs. OOMPAH-490 is pruning and isolating the suite, and OOMPAH-491 blocks network Git; OOMPAH-492 owns known live-tracker leaks. Parallel execution must build on those protections rather than mask races.

Implementation: add pytest-xdist as a development/test dependency and make OOMPAH_PYTEST_WORKERS in .env control the Makefile test worker count with a conservative default based on measured safety, plus an explicit serial diagnostic target. Mark or group genuinely process-global tests (ports, Granian, environment, service PID, Git worktree metadata) so they remain deterministic. Ensure each worker receives isolated temp/cache/home paths and the Git-remote barrier. Record serial versus parallel duration and worker count; do not select 64 blindly under memory/storage pressure.

Tests: run collection and focused isolation suites, then compare a clean serial full run with repeated parallel full runs. Assert identical pass/skip/xfail outcomes, no live network Git, no leaked subprocesses, clean git status, and useful failure output. Add Makefile/config/docs contract tests.

Acceptance criteria: make test uses a safe bounded worker count, is materially faster than serial, remains deterministic, and make test-serial provides a reliable debugging fallback.

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
<!-- COMMENTS:END -->

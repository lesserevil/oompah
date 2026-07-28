---
id: OOMPAH-514
type: chore
status: Done
priority: 1
title: Prove maintenance cannot dirty or push the server code checkout
parent: OOMPAH-511
children: []
blocked_by:
- OOMPAH-512
- OOMPAH-513
labels: []
assignee: null
created_at: '2026-07-28T15:16:44.915690Z'
updated_at: '2026-07-28T15:41:58.105288Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add an end-to-end regression around scheduler/background maintenance and representative server-side tracker consumers. Build disposable local Git repositories with separate code and Oompah state branches, register the project, run maintenance ticks including archive/error-watcher style mutations, and verify all durable task changes land only on the state branch. Exercise an ambiguous or missing-project context and verify it fails closed. Ensure executor-backed maintenance futures are joined or cancelled by the test harness so no work escapes after the test finishes. This task complements OOMPAH-492; do not re-edit its specifically assigned worker-exit, ACP billing, or epic-rebase cases unless its completed result requires integration adjustment.

Relevant files

tests for the orchestrator event loop/maintenance, native state-branch E2E suites, server fixtures, and the smallest production cleanup needed to make background lifecycle ownership deterministic.

Required tests

Assert the code checkout HEAD, worktree, index, and origin/default ref are unchanged before/after maintenance; assert the state branch contains the expected task update; assert no child process or pending executor future remains; run the focused E2E tests repeatedly and run make test from a clean isolated worktree.

Acceptance criteria

Maintenance and server helpers cannot write or push task metadata to the code branch, ambiguous project context produces no mutation, all asynchronous work is accounted for before teardown, the regression is deterministic across repeated runs, and the full suite passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:38
---
Claimed in the OOMPAH-511 isolated worktree. Added disposable-remote regression coverage for state-only maintenance writes and orchestrator shutdown drainage; the full project test suite is running.
---
author: oompah
created: 2026-07-28 15:41
---
Completed in commit 6533e235e. A disposable bare-remote integration test proves auto-archive changes only the configured state ref while local/remote main and the code checkout remain unchanged. Orchestrator shutdown now drains maintenance futures and owned executor pools. make test: 12,402 passed, 39 skipped; make check-secrets passed.
---
<!-- COMMENTS:END -->

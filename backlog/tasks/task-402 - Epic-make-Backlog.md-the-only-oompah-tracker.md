---
id: TASK-402
title: 'Epic: make Backlog.md the only oompah tracker'
status: Open
assignee: []
created_date: '2026-06-01 19:17'
labels:
  - epic
dependencies: []
priority: high
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Parent epic for removing Beads/bd support and making Backlog.md the required tracker for oompah.

Context:
- oompah currently has two tracker backends: Beads via the bd CLI and Backlog.md via the backlog CLI.
- The project direction is to make Backlog.md mandatory and stop carrying runtime Beads support.
- Several lifecycle states are currently encoded as labels or derived review state; these should become Backlog.md statuses.

Target behavior:
- oompah starts only when the project has Backlog.md initialized.
- Runtime code never invokes bd, never depends on .beads, and never sets BEADS_DIR.
- Task lifecycle is represented with Backlog statuses such as Open, In Progress, Needs Answer, In Review, Needs CI Fix, Needs Rebase, Merged, and Archived.
- Existing historical migrated-task metadata such as beads.id may remain as archival data, but it must not drive runtime behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Backlog.md is the only supported runtime tracker for oompah.
- [ ] #2 All child tasks are complete and the full test suite passes.
- [ ] #3 No runtime code path invokes bd or requires .beads.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Implement this epic through focused child tasks:
1. Require Backlog.md in config and tracker construction.
2. Remove Beads project bootstrap, sync, and worktree plumbing.
3. Convert lifecycle labels into Backlog status transitions.
4. Update dashboard/API status rendering.
5. Remove Beads migration tooling, scripts, and obsolete docs.
6. Rename runtime wording from bead/bd to task/backlog where appropriate.
7. Rewrite tests for Backlog-only behavior and remove Beads tests.
8. Run final verification and document the migration outcome.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All child tasks are Done or otherwise explicitly closed with rationale.
- [ ] #2 make test passes.
<!-- DOD:END -->

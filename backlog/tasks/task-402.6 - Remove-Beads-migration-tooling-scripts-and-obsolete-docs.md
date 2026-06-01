---
id: TASK-402.6
title: 'Remove Beads migration tooling, scripts, and obsolete docs'
status: Open
assignee: []
created_date: '2026-06-01 19:20'
updated_date: '2026-06-01 19:21'
labels:
  - task
dependencies:
  - TASK-402.2
  - TASK-402.3
parent_task_id: TASK-402
priority: high
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove Beads migration tooling, merge-driver scripts, and obsolete Beads documentation from the supported codebase.

Context:
- Once oompah requires Backlog.md, it should not ship tools that imply Beads remains a supported tracker.
- Historical task files may still contain beads.id metadata from the old migration; do not rewrite completed task history unless explicitly required.

Work required:
- Remove the oompah-migrate-beads-to-backlog console entry from pyproject.toml.
- Delete or archive oompah/beads_to_backlog.py if it is no longer supported.
- Delete scripts/beads-merge.sh.
- Delete or rewrite docs/backlog-migration.md so user-facing docs no longer instruct operators to run Beads migration as a supported path.
- Update README tracker/setup sections to say Backlog.md is required.
- Review plans/ docs and remove references that present Beads as current architecture; leave clearly historical design notes only if they are marked historical.

Files to inspect first:
- pyproject.toml
- oompah/beads_to_backlog.py
- scripts/beads-merge.sh
- docs/backlog-migration.md
- README.md
- plans/tracker-backends.md
- plans/submit-queue.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No package entry point references Beads migration tooling.
- [ ] #2 No supported script exists solely for .beads merge handling.
- [ ] #3 User-facing docs describe Backlog.md as required, not optional.
- [ ] #4 Historical beads.id task metadata is not treated as runtime support.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove packaging entry points and script files first.
2. Delete tests that only validate removed migration tooling.
3. Rewrite README and active docs to Backlog-only setup.
4. Sweep plans for current-tense Beads architecture claims and update or mark historical.
5. Run tests/import checks to ensure no deleted module is imported.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Import/package tests pass.
- [ ] #2 README setup instructions mention only Backlog.md for issue tracking.
<!-- DOD:END -->

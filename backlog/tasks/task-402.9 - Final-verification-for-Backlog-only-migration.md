---
id: TASK-402.9
title: Final verification for Backlog-only migration
status: Open
assignee: []
created_date: '2026-06-01 19:20'
updated_date: '2026-06-01 19:21'
labels:
  - task
dependencies:
  - TASK-402.8
parent_task_id: TASK-402
priority: high
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Final verification and handoff for the Backlog-only tracker migration epic.

Context:
- This task should be completed after the implementation, docs, terminology, and test cleanup tasks are done.
- Its purpose is to catch missed Beads support and leave clear operator/developer handoff notes.

Work required:
- Run a final codebase audit for Beads runtime support. Suggested searches: BeadsTracker, BEADS_DIR, .beads, bd bootstrap, bd dolt, beads-jsonl, oompah-migrate-beads-to-backlog.
- Separate historical references, such as old backlog/completed task text or preserved beads.id frontmatter, from live runtime references.
- Run make test.
- Start or restart oompah with the appropriate Makefile target if runtime behavior changed and verify it starts against Backlog.md.
- Update the parent epic with a concise summary and close it when every child is complete.

Files to inspect first:
- README.md
- WORKFLOW.md
- backlog/config.yml
- pyproject.toml
- oompah/
- tests/
- docs/
- plans/
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Final rg audit finds no live Beads runtime support.
- [ ] #2 make test passes after all child work is complete.
- [ ] #3 The parent epic contains final handoff notes and is ready to close.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Confirm all dependent tasks are Done.
2. Run rg audits for removed Beads concepts.
3. Run make test.
4. Run make restart or make start if needed to verify service startup.
5. Post final notes to the parent epic and close it.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Final verification commands and results are recorded.
- [ ] #2 Parent epic is closed after all child tasks are complete.
<!-- DOD:END -->

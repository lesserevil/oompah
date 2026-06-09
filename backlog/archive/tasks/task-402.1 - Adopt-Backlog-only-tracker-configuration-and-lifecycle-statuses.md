---
id: TASK-402.1
title: Adopt Backlog-only tracker configuration and lifecycle statuses
status: Done
assignee:
  - oompah
created_date: '2026-06-01 19:20'
updated_date: '2026-06-01 22:40'
labels:
  - task
dependencies: []
parent_task_id: TASK-402
priority: high
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the Backlog-only configuration and lifecycle status foundation.

Context:
- The parent epic is making Backlog.md mandatory for oompah.
- The current config layer still accepts tracker.kind values such as beads/bd and defaults to legacy Beads states in some paths.
- The desired lifecycle should be represented as Backlog statuses rather than labels or hidden dashboard-derived state.

Work required:
- Update WORKFLOW.md tracker settings so future oompah agents see Backlog.md as the required tracker.
- Update oompah/config.py so Backlog.md is the only accepted tracker kind. Reject beads, bd, and unknown aliases with a clear validation error.
- Update default tracker states for Backlog-only operation. Keep compatibility aliases in code where useful, but do not allow selecting Beads.
- Ensure backlog/config.yml contains the canonical status list: Backlog, Open, In Progress, Needs Answer, Needs Human, Decomposed, Duplicate Candidate, In Review, Needs CI Fix, Needs Rebase, Done, Merged, Archived.
- Update BacklogMdTracker status normalization so internal legacy requests map to the canonical Backlog statuses. Examples: deferred/backlog -> Backlog; open -> Open; in_progress/doing/started -> In Progress; done/closed -> Done; merged -> Merged.

Files to inspect first:
- WORKFLOW.md
- oompah/config.py
- oompah/tracker.py
- tests/test_config.py
- tests/test_backlog_tracker.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Config validation rejects tracker.kind values beads and bd.
- [ ] #2 Backlog.md is the default and only supported tracker kind.
- [ ] #3 Legacy internal status aliases map to canonical Backlog statuses.
- [ ] #4 The canonical Backlog status list is documented in project workflow/config.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read the current tracker config parsing and BacklogMdTracker status mapping.
2. Add or adjust tests that prove beads/bd is rejected and Backlog aliases resolve to canonical statuses.
3. Update config defaults and validation.
4. Update WORKFLOW.md and backlog/config.yml status vocabulary.
5. Run focused config/tracker tests, then make test if this task includes broader behavior changes.
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed as part of the Backlog-only tracker migration. Removed Beads/bd runtime paths where applicable, moved lifecycle behavior to canonical Backlog.md statuses, updated UI/API/tests/docs for Backlog-only behavior, and verified with make test: 3677 passed.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Focused config and Backlog tracker tests pass.
- [ ] #2 No Beads runtime mode can be selected through configuration.
<!-- DOD:END -->

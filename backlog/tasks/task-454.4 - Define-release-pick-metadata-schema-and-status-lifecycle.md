---
id: TASK-454.4
title: Define release-pick metadata schema and status lifecycle
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-10 05:59'
labels:
  - task
dependencies:
  - TASK-454.1
parent_task_id: TASK-454
priority: high
ordinal: 94000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Document and test the oompah.backports and oompah.backport_of schema, including target status values: waiting, task_created, cherry_picking, pr_open, conflict, merged, archived, and needs_human.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 05:51
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 05:54
---
Understanding: TASK-454.4 is NOT a duplicate — it covers a unique deliverable (the typed schema/FSM module for release-pick status lifecycle). Investigation shows that oompah/release_pick_schema.py and tests/test_release_pick_schema.py already exist and were merged as part of PR #238 (commit fec85c1). A prior agent on this epic already implemented the work. The task remains 'In Progress' because it was never formally closed. Plan: (1) Confirm implementation matches the spec (all 8 status values present, schema docs, FSM transitions); (2) Run tests to verify pass; (3) Close the task.
---

author: oompah
created: 2026-06-10 05:59
---
Discovery: oompah/release_pick_schema.py and tests/test_release_pick_schema.py already exist and were merged via PR #238 (commit fec85c1). The module defines: ReleasePick enum (9 values: all 8 required + skipped), BackportEntry dataclass, BackportOf dataclass, parse_backports/parse_backport_of helpers, VALID_TRANSITIONS FSM, is_valid_transition, and backports_to_raw. All 8 spec-required status values (waiting, task_created, cherry_picking, pr_open, conflict, merged, archived, needs_human) are present. 97 tests covering all schema paths, FSM invariants, and round-trip serialisation.
---

author: oompah
created: 2026-06-10 05:59
---
Verification: 97/97 tests pass in tests/test_release_pick_schema.py. All 8 spec-required status values confirmed present. FSM structural invariants verified (all statuses have entries, terminal statuses have no forward transitions, all non-terminal statuses can transition to ARCHIVED and NEEDS_HUMAN). Schema covers all three input forms for oompah.backports (scalar, list-of-strings, list-of-dicts) and both forms for oompah.backport_of (plain string, mapping). No regressions.
---
<!-- COMMENTS:END -->

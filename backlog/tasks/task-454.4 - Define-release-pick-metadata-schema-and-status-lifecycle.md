---
id: TASK-454.4
title: Define release-pick metadata schema and status lifecycle
status: Open
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 22:50'
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
created: 2026-06-08 18:11
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 18:16
---
Understanding: This is NOT a duplicate. TASK-454.1 (done) covers reading raw oompah.backports/backport_of metadata from Backlog frontmatter. TASK-454.4 is about defining the formal schema with typed Python models and a status lifecycle (waiting, task_created, cherry_picking, pr_open, conflict, merged, archived, needs_human). Plan: (1) Create oompah/release_pick_schema.py with ReleasePick status enum, BackportEntry and BackportOf dataclasses, and parsing helpers; (2) Write tests in tests/test_release_pick_schema.py covering all statuses, schema round-trips, and parsing edge cases; (3) Write plans/release-pick-schema.md documenting the schema and lifecycle FSM.
---

author: oompah
created: 2026-06-08 18:22
---
Discovery: No duplicate found. TASK-454.1 reads raw metadata; no existing task defines the typed schema. Key finding: release_pick_schema.py did not yet exist. The oompah.backports/backport_of fields had tests for basic roundtrips but no formal ReleasePick enum, BackportEntry/BackportOf dataclasses, or FSM (VALID_TRANSITIONS). Created oompah/release_pick_schema.py with full typed schema and tests/test_release_pick_schema.py with 97 tests.
---

author: oompah
created: 2026-06-08 18:22
---
Implementation: Created 3 artifacts: (1) oompah/release_pick_schema.py — ReleasePick(str, Enum) with 8 status values, BackportEntry/BackportOf dataclasses with from_raw/to_raw methods, VALID_TRANSITIONS FSM, is_valid_transition helper, parse_backports/parse_backport_of/backports_to_raw top-level helpers; (2) tests/test_release_pick_schema.py — 97 tests covering all enum values, from_raw normalisation (case, hyphens, None, unknown), is_terminal/is_blocked properties, FSM invariants, valid/invalid/self-transitions, BackportEntry/BackportOf parsing and round-trips, all parse/serialise helpers; (3) plans/release-pick-schema.md — schema reference with Mermaid FSM diagram, YAML examples, Python API docs, and cross-references to related modules.
---

author: oompah
created: 2026-06-08 18:22
---
Verification: 97/97 tests pass in tests/test_release_pick_schema.py; 198/198 tests pass across test_release_pick_schema, test_release_pick_validation, test_backlog_tracker, test_backlog_compat — no regressions. All 8 documented status values present in enum; FSM invariants verified (terminal states have no forward transitions; all non-terminal states can archive or escalate).
---
<!-- COMMENTS:END -->

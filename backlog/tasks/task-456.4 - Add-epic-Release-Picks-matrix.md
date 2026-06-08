---
id: TASK-456.4
title: Add epic Release Picks matrix
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 22:33'
labels:
  - task
dependencies:
  - TASK-456.1
parent_task_id: TASK-456
priority: high
ordinal: 106000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
For epics, show a child-by-target-branch matrix with per-child status. Support applying release picks to all children and skipping individual children when a change should not be backported.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 21:24
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 21:24
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:15
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:19
---
Understanding: TASK-456.4 is NOT a duplicate. Searched 'epic release picks matrix', 'apply release picks', 'backport matrix'. No other task covers this exact feature. TASK-456.1 (Done) provides the backend API foundation. TASK-456.4 is distinct: implement get_epic_release_pick_matrix() and apply_release_picks_to_all_children() in release_pick_api.py, plus GET /api/v1/issues/{id}/release-picks/matrix and POST /api/v1/issues/{id}/release-picks/apply-all endpoints in server.py, with full test coverage. Plan: (1) Add two functions to release_pick_api.py, (2) Add two endpoints to server.py, (3) Add tests to test_release_pick_api.py and test_server_release_picks.py.
---

author: oompah
created: 2026-06-08 22:32
---
Discovery: TASK-456.4 is not a duplicate. The release_pick_api.py module's module-level docstring already described get_epic_release_pick_matrix and apply_release_picks_to_all_children as planned functions but they were not implemented. The release_pick_schema.py already had ReleasePick.SKIPPED status. TASK-456.1 (Done) provides get_release_pick_detail/update_release_pick_entry/update_release_picks_bulk and the GET+PATCH endpoints. My task adds the epic matrix functions and two new endpoints: GET /api/v1/issues/{id}/release-picks/matrix and POST /api/v1/issues/{id}/release-picks/apply-all. Also fixed a pre-existing test gap: test_release_pick_schema.py::test_all_expected_values_exist was missing 'skipped' from the expected set.
---

author: oompah
created: 2026-06-08 22:33
---
Implementation: Added get_epic_release_pick_matrix() and apply_release_picks_to_all_children() to oompah/release_pick_api.py. get_epic_release_pick_matrix fetches all children via tracker.fetch_children(), reads each child's oompah.backports metadata, collects unique branches, and returns {epic_identifier, branches, rows} where each row has {identifier, title, state, entries: {branch: normalised_entry_or_None}}. apply_release_picks_to_all_children validates all branches first (preventing partial writes on failure), then for each child: skipped children get ReleasePick.SKIPPED entries, normal children get ReleasePick.WAITING entries (existing entries are preserved; only missing branches are added). Returns the updated matrix. Added GET /api/v1/issues/{id}/release-picks/matrix and POST /api/v1/issues/{id}/release-picks/apply-all endpoints in server.py following existing patterns. Fixed pre-existing test_release_pick_schema.py gap by adding 'skipped' to expected values.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-23
type: task
status: Done
priority: 1
title: Bump release-branch package metadata to 1.0.0
parent: OOMPAH-22
children: []
blocked_by:
- OOMPAH-18
labels: []
assignee: null
created_at: '2026-06-22T01:16:41.668460Z'
updated_at: '2026-06-22T02:04:07.001333Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 025efdae-7b1d-4a2e-86f6-43c732ac3ead
---
## Summary

Plan: plans/oompah-1.0-release.md#epic-b-lock-the-10-cli-and-package-contract

WHAT TO DO
Bump package metadata to project.version = 1.0.0 on the release branch as part of the 1.0 release train.

HOW TO VERIFY
The release workflow and release-note generator agree that v1.0.0 matches the package version.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 01:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 01:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 01:54
---
UNDERSTANDING: This is NOT a duplicate. OOMPAH-23 is the specific task that actually bumps pyproject.toml project.version from 0.1.0 to 1.0.0. Checked all candidates: OOMPAH-18 (Done, updated docs/tests only), OOMPAH-21 (checklist docs, doesn't make the change), OOMPAH-38 (full quality gate, depends on this being done). None cover the actual pyproject.toml version bump. Proceeding to implement.
---
author: oompah
created: 2026-06-22 01:56
---
DISCOVERY: This is NOT a duplicate — no other task makes the actual pyproject.toml version change. Working on branch epic-OOMPAH-22 (the parent epic's branch for OOMPAH-22). Current pyproject.toml has version = "0.1.0"; needs to be changed to "1.0.0". The render_cli_release_notes.py script reads project.version and validates tag must equal v{version}, so after the bump, running the workflow with tag v1.0.0 will agree. No existing test asserts pyproject.toml version is 1.0.0 — will add one. Will also verify existing tests still pass.
---
author: oompah
created: 2026-06-22 02:01
---
IMPLEMENTATION: Changed pyproject.toml project.version from "0.1.0" to "1.0.0". Added two new tests to tests/test_cli_release_packaging.py: (1) test_pyproject_version_is_1_0_0 — asserts pyproject.toml project.version == "1.0.0" directly; (2) test_release_note_generator_accepts_v1_0_0_tag — verifies render_release_notes_for_dist accepts tag v1.0.0 when pyproject version is 1.0.0, confirming workflow/generator agreement.
---
author: oompah
created: 2026-06-22 02:01
---
VERIFICATION: All 8 tests in tests/test_cli_release_packaging.py pass (0 failures). Full test suite: 7040 passed, 28 skipped, 13 warnings. No pre-existing failures introduced.
---
author: oompah
created: 2026-06-22 02:03
---
COMPLETION: Bumped pyproject.toml project.version from 0.1.0 to 1.0.0, updated uv.lock to match. Added test_pyproject_version_is_1_0_0 (asserts version == 1.0.0 directly) and test_release_note_generator_accepts_v1_0_0_tag (verifies workflow/generator agreement). All 8 cli_release tests pass; full suite 7040 passed. Branch epic-OOMPAH-22 pushed to origin.
---
<!-- COMMENTS:END -->

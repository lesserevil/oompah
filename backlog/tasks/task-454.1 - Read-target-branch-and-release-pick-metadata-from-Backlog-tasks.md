---
id: TASK-454.1
title: Read target branch and release-pick metadata from Backlog tasks
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:44'
labels:
  - task
dependencies: []
parent_task_id: TASK-454
priority: high
ordinal: 91000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
BacklogMdTracker should populate Issue.target_branch from oompah.target_branch or compatible frontmatter, and expose parsed oompah.backports / oompah.backport_of metadata through existing metadata helpers. Include tests for missing, scalar, and nested metadata.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 17:38
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 17:39
---
Understanding: This is NOT a duplicate. TASK-397/TASK-408 are about preserving frontmatter on write. This task is about READING specific Backlog frontmatter fields into oompah's data model: (1) populate Issue.target_branch from oompah.target_branch frontmatter, (2) expose oompah.backports / oompah.backport_of via existing metadata helpers. Will explore BacklogMdTracker and Issue model to find where to hook in.
---

author: oompah
created: 2026-06-08 17:40
---
Discovery: The Issue dataclass already has target_branch: str | None = None. The _normalize_task method in BacklogMdTracker does NOT read oompah.target_branch from frontmatter to populate it. get_metadata() already returns all oompah.* keys, so oompah.backports/backport_of work if they're in frontmatter. Need to: (1) add target_branch extraction from oompah.target_branch (or compatible target_branch) in _normalize_task, (2) add the new fields to _KNOWN_BACKLOG_FIELDS, (3) write tests for missing/scalar/nested cases.
---

author: oompah
created: 2026-06-08 17:44
---
Implementation: Modified oompah/tracker.py to (1) add oompah.target_branch, oompah.backports, oompah.backport_of to _KNOWN_BACKLOG_FIELDS; (2) in _normalize_task, read oompah.target_branch (preferred) or top-level target_branch and set Issue.target_branch. get_metadata() already exposes all oompah.* keys so backports/backport_of work without further changes. Added 12 new tests covering: target_branch from oompah frontmatter, missing (None), compatible top-level field, precedence, scalar backport_of, scalar backports, list backports, nested dict backport_of, missing fields, set/retrieve roundtrips.
---

author: oompah
created: 2026-06-08 17:44
---
Verification: 50/50 tests pass in tests/test_backlog_tracker.py. All 12 new TASK-454.1 tests pass including: oompah.target_branch frontmatter → Issue.target_branch, missing → None, compatible top-level field, precedence, scalar/list/nested dict metadata, and set/retrieve roundtrips for backports, backport_of, and target_branch. 146 tests in related test files (backlog_compat, issue_enhancer, backlog_conflict) also pass.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented Issue.target_branch population from oompah.target_branch (preferred) or compatible top-level target_branch frontmatter in BacklogMdTracker._normalize_task. Added oompah.target_branch, oompah.backports, oompah.backport_of to _KNOWN_BACKLOG_FIELDS. get_metadata already returned all oompah.* keys so backports/backport_of needed no code changes. 12 new tests cover missing/scalar/nested metadata for all three fields. 50/50 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

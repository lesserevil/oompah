---
id: OOMPAH-39
type: task
status: In Progress
priority: 1
title: Create and verify the v1.0.0-draft release
parent: OOMPAH-37
children: []
blocked_by:
- OOMPAH-38
labels: []
assignee: null
created_at: '2026-06-22T01:17:37.381380Z'
updated_at: '2026-06-22T15:10:02.731003Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d93a474e-7278-42e3-8e42-5c7e48f07b49
---
## Summary

Plan: plans/oompah-1.0-release.md#release-execution-and-verification

WHAT TO DO
Create or force-move v1.0.0-draft, run the CLI Release workflow, and verify the draft artifacts from GitHub.

HOW TO VERIFY
The draft GitHub Release contains expected wheel/source artifacts, generated notes, and install commands. Re-running after force-moving the draft tag updates the draft artifacts cleanly.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 15:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 15:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 15:05
---
UNDERSTANDING: Not a duplicate. OOMPAH-39 is step E2 in the 1.0 release plan (plans/oompah-1.0-release.md). All other release tasks are distinct: OOMPAH-38=E1 (cut branch+quality gate), OOMPAH-40=E3 (fix findings), OOMPAH-41=E4 (final tag), OOMPAH-42=E5 (smoke checks). No other task covers 'Create and verify v1.0.0-draft'. Proceeding with duplicate investigation complete; will now check OOMPAH-38 blocker status before executing E2 work.
---
author: oompah
created: 2026-06-22 15:10
---
DISCOVERY: Not a duplicate. OOMPAH-39 is step E2 (Create and verify v1.0.0-draft release). Key finding: release/1.0 was created from epic-OOMPAH-27 but is missing commit dae18fd4 (OOMPAH-19: Support force-movable v1.0.0-draft release tag in validation). Without this, render_cli_release_notes.py fails with ValueError when tag=v1.0.0-draft != v1.0.0. Both file versions on release/1.0 (scripts/render_cli_release_notes.py=9d06fd44, tests/test_cli_release_packaging.py=0262d1be) exactly match the pre-state of dae18fd4, so cherry-pick will apply cleanly. Plan: (1) cherry-pick dae18fd4 onto release/1.0, (2) push release/1.0, (3) create+push v1.0.0-draft tag, (4) wait for CLI Release workflow, (5) verify draft artifacts.
---
<!-- COMMENTS:END -->

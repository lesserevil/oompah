---
id: OOMPAH-158
type: bug
status: In Progress
priority: null
title: Make GitHub intake import parsing tolerant of Markdown issue bodies
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-26T22:14:16.817361Z'
updated_at: '2026-06-27T03:21:03.800378Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d235d15f-5aac-41e6-88ea-173e7fae4689
---
## Summary

GitHub issue intake should preserve and parse structured Markdown issue bodies so imported tasks expose a non-empty description and required-field validation sees Summary, work details, and acceptance criteria content.
## Problem
GitHub issue intake can import a well-structured GitHub issue into a native oompah task, but the resulting task/detail API may expose a null or empty normalized description and stale intake metadata that incorrectly marks required fields as missing.

Observed example: NVIDIA-Omniverse/trickle#268 imports as TRICKLE-8. The GitHub issue body includes a Summary, required quiet-install behavior, Acceptance criteria, and Notes. Direct validation of both the GitHub body and the imported markdown body passes, but TRICKLE-8 remains Proposed with intake missing_fields: acceptance_criteria, problem_statement, work_description, and the detail API reports description: null.

## Steps to Reproduce
1. Enable GitHub issue intake for the trickle project.
2. Import GitHub issue NVIDIA-Omniverse/trickle#268.
3. Inspect TRICKLE-8 in the dashboard or via /api/v1/issues/TRICKLE-8/detail?project_id=proj-3e4e9214.
4. Compare the intake summary with the original GitHub issue body.

## Actual Behavior
The imported task is marked as missing acceptance_criteria, problem_statement, and work_description even though the GitHub issue body contains those sections/content. The dashboard/detail API shows description as null, making the intake UI misleading.

## Expected Behavior
GitHub intake import should preserve and parse Markdown issue bodies robustly enough that validation sees the user-provided Summary/problem, work description, and acceptance criteria. If the imported body is structurally wrapped, validation should still inspect the meaningful original content rather than treating the description as empty.

## Acceptance Criteria
- GitHub issue intake preserves imported Markdown bodies so the native task detail API exposes a non-null description or otherwise provides the validator with the original content.
- Intake validation for an issue shaped like NVIDIA-Omniverse/trickle#268 does not incorrectly report acceptance_criteria, problem_statement, or work_description as missing.
- Existing imported tasks can be revalidated or corrected when their stored body already contains the required information.
- Regression tests cover a GitHub issue body with Summary, behavior/work-description bullets, Acceptance criteria, and Notes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-27 03:20
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-27 03:21
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->

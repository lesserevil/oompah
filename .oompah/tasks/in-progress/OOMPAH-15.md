---
id: OOMPAH-15
type: bug
status: In Progress
priority: 1
title: Ensure auto-generated tasks pass intake validation
parent: null
children: []
blocked_by: []
labels:
- bug
- intake
- automation
- validation
- error-watcher
assignee: null
created_at: '2026-06-20T03:23:38.004425Z'
updated_at: '2026-06-20T03:45:55.878212Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7140460c-6e72-4f9f-b110-d0f59a8fec8c
---
## Summary

Auto-generated tasks must be created in a form that passes oompah intake validation. `OOMPAH-6` was auto-created by `error_watcher` for a GitHub API authentication failure, but it remained in Proposed with missing fields: `actual_behavior`, `expected_behavior`, and `reproduction_steps`.

Problem:
Auto-filed tasks currently capture raw error text and metadata, but do not reliably render the structured sections required by the intake validator. This creates Proposed tasks that require manual cleanup before they can enter Backlog, even though oompah itself generated the task and has enough context to describe the failure.

Steps to Reproduce:
1. Trigger an oompah-managed project tracker failure, such as a GitHub API authentication failure while fetching issues.
2. Let `error_watcher` auto-file the resulting task.
3. Open the generated task in the oompah UI.
4. Observe that the intake summary reports missing required fields.

Actual Behavior:
Oompah can auto-create a Proposed bug task that fails the deterministic intake validator and needs a human to rewrite it.

Expected Behavior:
Every task created by oompah automation should pass the same validation rules required of externally-created issues, or the generator should have a test-proven reason to keep it out of the task workflow.

Acceptance Criteria:
- ErrorWatcher-generated bug tasks include validator-recognized sections for Problem, Steps to Reproduce, Actual Behavior, Expected Behavior, and Acceptance Criteria.
- Auto-generated tasks from other task creation paths are audited or covered by a shared helper so they cannot regress into invalid Proposed tasks.
- A regression test reproduces the `OOMPAH-6` shape and verifies the generated task passes `validate_issue()`.
- Generated descriptions still include diagnostic metadata such as fingerprint, source project, tracker identity, and error class.
- No user-specific logins are hard-coded in tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-20 03:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-20 03:45
---
Understanding: OOMPAH-15 is NOT a duplicate. OOMPAH-6 is the motivating example (actual auth failure task auto-filed by error_watcher) — OOMPAH-15 is the systemic fix to make error_watcher generate properly-structured descriptions that pass intake validation. All other open/in-progress tasks (OOMPAH-11 through OOMPAH-14) cover different problems (template refresh, label preservation, dashboard actor resolution). Plan: (1) Find error_watcher code and how it generates task descriptions, (2) Find validate_issue() to understand required sections, (3) Fix error_watcher to generate structured descriptions with Problem/Steps to Reproduce/Actual Behavior/Expected Behavior/Acceptance Criteria sections, (4) Add regression test reproducing OOMPAH-6 shape.
---
<!-- COMMENTS:END -->

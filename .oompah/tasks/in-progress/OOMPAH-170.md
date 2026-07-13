---
id: OOMPAH-170
type: task
status: In Progress
priority: 2
title: Update epic workflow documentation for shared-only behavior
parent: OOMPAH-166
children: []
blocked_by:
- OOMPAH-168
labels: []
assignee: null
created_at: '2026-07-13T02:23:12.785814Z'
updated_at: '2026-07-13T05:02:45.685424Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1294e732-9900-4f2b-83de-75f7e7cffe9d
---
## Summary

Update user-facing docs, operator/configuration docs, generated project guidance, and relevant design plans so they describe only the shared epic workflow. Remove or clearly mark historical flat/stacked references where historical context is necessary. Update Mermaid diagrams to show the shared epic branch and landing flow. Update documentation tests or add coverage for generated guidance and remove stale strategy references from active documentation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 04:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 04:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:52
---
UNDERSTANDING: No duplicate found. OOMPAH-170 is a unique child of epic OOMPAH-166 covering the documentation layer. Siblings OOMPAH-167 (config), OOMPAH-168 (orchestration), OOMPAH-169 (UI) are all Done. Scope: update user-facing docs, operator docs, generated project guidance, design plans so they describe only shared epic workflow; remove/mark flat/stacked references; update Mermaid diagrams; add/update doc tests. Plan: (1) Find all docs with flat/stacked/strategy references, (2) Update them, (3) Find and update generated guidance templates, (4) Add doc coverage tests, (5) Run make test.
---
author: oompah
created: 2026-07-13 04:54
---
DISCOVERY: Found all locations needing updates. Primary target: docs/task-epic-workflow.md has stale flat/stacked references in: (1) Epic Planning section - 'stacked and shared projects'; (2) Epic Branch Strategies section - table with flat/stacked/shared rows; (3) Mermaid diagram with flat/stacked branches; (4) Review and Repair - 'stacked or shared epics'; (5) Closing and Rollup - 'stacked and shared epics' (2x). Secondary: tests/test_epic_strategy.py module docstring mentions 'stacked mode' and 'stacked + shared'. Also: plans/multi-branch-support.md line 123 references test_epic_strategy.py as 'Epic strategies' (minor stale context). The generated project guidance (oompah/agent_instructions.py OOMPAH_TASK_AGENT_INSTRUCTIONS) has no flat/stacked references - already clean. No new test file needed beyond updating the test docstring. No duplicate found - proceeding with implementation.
---
author: oompah
created: 2026-07-13 05:02
---
IMPLEMENTATION: Updated 5 files to describe only the shared epic workflow:
(1) docs/task-epic-workflow.md: Renamed 'Epic Branch Strategies' to 'Shared Epic Branch', replaced 3-row flat/stacked/shared table with a 2-row shared-only table, simplified Mermaid diagram to shared path only, updated 4 prose occurrences of 'stacked and/or shared' to 'shared'.
(2) docs/README.md: Updated table-of-contents entry for task-epic-workflow.md.
(3) plans/multi-branch-support.md: Updated annotation for test_epic_strategy.py from 'Epic strategies' to 'Epic shared workflow'.
(4) tests/test_epic_strategy.py: Rewrote module docstring to remove 'stacked mode' and 'stacked + shared' references.
(5) tests/test_agent_instructions.py: Added 3 new tests: test_oompah_task_instructions_no_flat_or_stacked_strategy, test_github_issues_instructions_no_flat_or_stacked_strategy, test_task_epic_workflow_doc_describes_shared_only_behavior.
---
author: oompah
created: 2026-07-13 05:02
---
VERIFICATION: All 7251 tests pass (make test). The 3 new doc-coverage tests pass: test_oompah_task_instructions_no_flat_or_stacked_strategy, test_github_issues_instructions_no_flat_or_stacked_strategy, test_task_epic_workflow_doc_describes_shared_only_behavior. Branch pushed to origin/epic-OOMPAH-166.
---
<!-- COMMENTS:END -->

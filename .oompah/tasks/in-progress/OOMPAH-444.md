---
id: OOMPAH-444
type: task
status: In Progress
priority: null
title: Deduplicate post-merge Needs Human recovery instructions
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-25T19:55:15.601730Z'
updated_at: '2026-07-25T19:55:24.066568Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

The merged-epic reconciliation pass currently calls mark_needs_human on every scheduler tick for a child that remains Needs Human without landing evidence, appending the identical actionable recovery instruction repeatedly (observed on EXOCOMP-66 and peers). Make this transition idempotent: if the child is already Needs Human and the same normalized instruction has already been posted, do not update status or add another comment; if the landing-evidence reason/instruction changes, post the changed actionable instruction once. Preserve first-transition behavior and the final-comment human-action contract. Add tests reproducing consecutive reconciliation ticks and changed-instruction behavior in tests/test_epic_strategy.py, then run focused and full Make quality gates.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-25 19:55
---
Reproduced in exocomp: merged-epic reconciliation appended the identical landing-evidence recovery instruction on each tick while the child remained Needs Human. Implementing durable tracker-comment dedup keyed by normalized instruction, with changed-instruction coverage.
---
<!-- COMMENTS:END -->

---
id: OOMPAH-187
type: task
status: In Progress
priority: 2
title: Keep Needs Human tasks visible in the in-flight dashboard filter
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T14:08:30.012087Z'
updated_at: '2026-07-13T14:10:48.930277Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 21966f80-2c3c-49b9-89a6-fc3854b2a4c9
---
## Summary

The dashboard In-flight only toggle currently treats Open, In Progress, Needs CI Fix, Needs Rebase, In Review, and open-review work as in flight, but hides Needs Human tasks. Update the canonical client-side in-flight predicate (including parent/ancestor visibility calculation and toggle tooltip/copy) so Needs Human is considered in flight and remains visible when the filter is enabled. Preserve existing terminal-task hiding behavior. Tests: extend tests/test_dashboard_hide_merged.py with a direct Needs Human case, an epic/parent visibility case, and a counter/hidden-state assertion; update the dashboard tooltip test to name Needs Human. Acceptance: with In-flight only enabled, OOMPAH-44/46/48-style Needs Human cards remain visible and their parent context remains visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 14:08
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-13 14:09
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-13 14:10
---
Understanding: The in-flight dashboard filter in dashboard.html hides 'Needs Human' tasks because (a) _isIndividuallyInFlight() at line 2868 only lists Open/In Progress/Needs CI Fix/Needs Rebase/In Review as in-flight, not Needs Human, and (b) applyHideMergedFilter() at line 2957 only passes through those same columns unconditionally. Fix plan: (1) add 'Needs Human' to _isIndividuallyInFlight check, (2) add 'Needs Human' to the column passthrough list, (3) update tooltip text to include Needs Human, (4) mirror both fixes in the Python test helpers, (5) add new tests: direct Needs Human visibility case, epic/parent visibility case, counter/hidden-state assertion, tooltip-names-Needs-Human assertion.
---
<!-- COMMENTS:END -->

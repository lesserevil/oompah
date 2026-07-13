---
id: OOMPAH-187
type: task
status: Merged
priority: 2
title: Keep Needs Human tasks visible in the in-flight dashboard filter
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T14:08:30.012087Z'
updated_at: '2026-07-13T16:49:58.129254Z'
work_branch: null
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/408
review_number: null
merged_at: null
oompah.agent_run_id: 21966f80-2c3c-49b9-89a6-fc3854b2a4c9
oompah.task_costs:
  total_input_tokens: 93
  total_output_tokens: 1978
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 93
      output_tokens: 1978
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 93
    output_tokens: 1978
    cost_usd: 0.0
    recorded_at: '2026-07-13T14:17:58.444080+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/408
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
author: oompah
created: 2026-07-13 14:17
---
Discovery & Implementation: Root cause found in dashboard.html. Three locations needed updating: (1) _isIndividuallyInFlight() at line 2868 - added 'Needs Human' to the in-flight state list; (2) applyHideMergedFilter() column passthrough list - added 'Needs Human' so the column bypasses the show-set filter entirely; (3) tooltip text - added 'Needs Human' to the description. Also extended _computeInFlightShowSet to add Rule 2: 'show an issue if its own subtree has in-flight work' (previously only showed children when ancestors were in-flight; now also shows parents/epics when they have in-flight descendants). Python test helpers and 7 new tests added in test_dashboard_hide_merged.py.
---
author: oompah
created: 2026-07-13 14:17
---
Verification: All 8000 tests pass (28 skipped, 0 failures). The 46 tests in test_dashboard_hide_merged.py all pass including the 7 new ones. Branch pushed to origin/OOMPAH-187.
---
author: oompah
created: 2026-07-13 14:17
---
Completion: Delivered the following changes to satisfy OOMPAH-187 acceptance criteria:

1. dashboard.html - _isIndividuallyInFlight(): Added 'Needs Human' to active-state list
2. dashboard.html - applyHideMergedFilter(): Added 'Needs Human' to column passthrough
3. dashboard.html - tooltip: Added 'Needs Human' to the list of in-flight states
4. dashboard.html - _computeInFlightShowSet(): Added Rule 2 (show if own subtree has in-flight work) so parent epics remain visible when they have Needs Human descendants
5. tests/test_dashboard_hide_merged.py: 7 new tests + Python helper updates

Needs Human tasks (OOMPAH-44/46/48-style) now remain visible with In-flight only enabled. Parent epics with Needs Human children remain visible. Counter does not count Needs Human tasks as hidden.
---
author: oompah
created: 2026-07-13 14:17
---
Added Needs Human to the in-flight predicate and column passthrough in dashboard.html. Updated tooltip text, extended _computeInFlightShowSet with parent-visibility rule, mirrored in Python test helpers, added 7 new tests. All 8000 tests pass.
---
author: oompah
created: 2026-07-13 14:17
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 51
- Tokens: 93 in / 2.0K out [2.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 1s
- Log: OOMPAH-187__20260713T140903Z.jsonl
---
<!-- COMMENTS:END -->

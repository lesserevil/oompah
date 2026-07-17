---
id: OOMPAH-218
type: task
status: Done
priority: null
title: Count incomplete-agent safety limit per focus
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-17T18:13:13.079649Z'
updated_at: '2026-07-17T18:15:16.383232Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 36e3b23e-d74e-4268-8630-029f8fa70c4c
---
## Summary

Update the completed-without-closing safety limit to count consecutive normal agent sessions for the same focus rather than all sessions on a task.

A successful focus handoff must reset the count for the next focus. Preserve the existing three-session limit when the same focus repeats. Add tests covering same-focus escalation to Needs Human, a focus transition resetting the counter, and a later repeat of the new focus counting independently. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-17 18:15
---
Implemented and pushed 64d68f5a. The incomplete-session safety count now tracks the last focus per task and resets when focus changes or a focus handoff succeeds. make test passed (9237 tests).
---
author: oompah
created: 2026-07-17 18:15
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-17 18:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 18:15
---
Run #1 [attempt=1, profile=default, role=— -> Claude/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 9s
---
author: oompah
created: 2026-07-17 18:15
---
Focus-scoped incomplete-session limit implemented in 64d68f5a; full test suite passed.
---
<!-- COMMENTS:END -->

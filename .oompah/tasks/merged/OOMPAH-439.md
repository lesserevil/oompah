---
id: OOMPAH-439
type: task
status: Merged
priority: null
title: Restrict Epic Planner routing to epics or explicit handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T15:59:50.769146Z'
updated_at: '2026-07-24T16:03:14.679119Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 916707ff-0426-4795-bb29-9b0ca988e585
---
## Summary

Prevent keyword-rich ordinary tasks from being routed to Epic Planner. Epic Planner must be eligible only when the issue type is epic or the task has an explicit needs:epic_planner label. Preserve explicit handoffs, and reactivate the Feature Developer focus in .oompah/foci.json so feature tasks have their normal route. Add regression coverage for non-epic keyword matches, explicit handoff override, and epic routing. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 16:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-24 16:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-24 16:00
---
Understanding: screening whether this Epic Planner routing fix duplicates prior work. I will search task history and project docs for Epic Planner eligibility, needs:epic_planner handoffs, and Feature Developer focus routing; inspect plausible tasks in full; then archive only if the same underlying work is already covered, otherwise hand off to implementation without code changes.
---
author: oompah
created: 2026-07-24 16:01
---
Deployed routing guard: Epic Planner now only selects true epics, unless explicitly requested with needs:epic_planner. Reactivated the local Feature Developer focus and added regression coverage for false-positive planning keywords, explicit handoffs, and ordinary epic routing. make test passed (12,314 tests). Commit 9af39f31f pushed to main.
---
author: oompah
created: 2026-07-24 16:02
---
Deployed routing guard: Epic Planner now only selects true epics, unless explicitly requested with needs:epic_planner. Reactivated the local Feature Developer focus and added regression coverage for false-positive planning keywords, explicit handoffs, and ordinary epic routing. make test passed (12,314 tests). Commit 9af39f31f pushed to main.
---
<!-- COMMENTS:END -->
